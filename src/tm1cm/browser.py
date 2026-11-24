"""Reading Cognos's CAM passport from a browser window the user signs in in.

Ported from Sublime-TM1 (core/browser.py), with one addition: :func:`read_cookie` can be limited
to the hidden window (``window=False``), for runs with nobody to sign in.

TM1 in CAM security accepts a Cognos passport. Cognos's own login page does whatever its namespace
needs (a form, OpenID Connect through any provider, SAML, Kerberos), and leaves the passport in the
browser as the cam_passport cookie. The browser keeps cookies to itself, so this starts a
Chromium-based browser (Chrome, Edge, Brave, Chromium) with its DevTools protocol on, opens the
login, and reads that one cookie once it's there. Nothing on the server is changed or required.

Safety:
- The browser runs with its own profile, in a folder only the user can read, never the user's own
  profile. A provider remembers the user there, so later sign-ins are quick or invisible.
- On macOS and Linux the protocol runs over a pipe (--remote-debugging-pipe): no port is opened.
  On Windows, where Python can't hand a process those pipes, it runs over a port: random, on
  127.0.0.1 only, and open only while the sign-in runs.
- Only the cookie asked for, on the host asked for, is read.
- The browser is always closed: when the cookie arrives, on failure, on timeout, and when asked.
"""

import base64
import json
import os
import posixpath
import select
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

# Signing in may involve a password, a second factor and an approval on a phone
SIGN_IN_TIMEOUT = 300
# How long a hidden window gets to come back with a passport from a provider session still alive
SILENT_TIMEOUT = 10

COMMON_ARGS = ['--no-first-run', '--no-default-browser-check', '--disable-sync', '--disable-extensions',
               '--disable-background-networking', '--disable-component-update', '--password-store=basic',
               '--use-mock-keychain']


class BrowserError(Exception):
    """No browser to sign in with, or the browser failed."""


class SignInCancelled(BrowserError):
    """The user closed the sign-in window."""


class SignInTimedOut(BrowserError):
    """No passport came back in time."""


class NotAnswering(BrowserError):
    """The browser stopped answering on its debugging connection."""


class SignInNeedsUser(BrowserError):
    """Only the hidden window could be tried, and the sign-in needs the user."""


class DebuggingBlocked(BrowserError):
    """The browser started but never answered on its debugging connection: most often an
    organisation's browser policy (RemoteDebuggingAllowed) turning it off."""


# How long a browser has to answer its first command before it's taken not to be listening
START_TIMEOUT = 15
# How long any later command may take
CALL_TIMEOUT = 30


# Finding a browser

WINDOWS_APPS = ['msedge.exe', 'chrome.exe', 'brave.exe']
WINDOWS_PATHS = [
    ('ProgramFiles', r'Microsoft\Edge\Application\msedge.exe'),
    ('ProgramFiles(x86)', r'Microsoft\Edge\Application\msedge.exe'),
    ('ProgramFiles', r'Google\Chrome\Application\chrome.exe'),
    ('ProgramFiles(x86)', r'Google\Chrome\Application\chrome.exe'),
    ('LOCALAPPDATA', r'Google\Chrome\Application\chrome.exe'),
    ('ProgramFiles', r'BraveSoftware\Brave-Browser\Application\brave.exe'),
    ('LOCALAPPDATA', r'BraveSoftware\Brave-Browser\Application\brave.exe'),
    ('LOCALAPPDATA', r'Chromium\Application\chrome.exe'),
]
MAC_APPS = ['Google Chrome', 'Microsoft Edge', 'Brave Browser', 'Chromium', 'Vivaldi']
LINUX_COMMANDS = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge',
                  'microsoft-edge-stable', 'brave-browser', 'vivaldi']


def _windows_app_path(name):
    try:
        import winreg
    except ImportError:
        return None
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            key_path = 'Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\' + name
            with winreg.OpenKey(root, key_path) as key:
                return winreg.QueryValue(key, None)
        except OSError:
            continue
    return None


def find_browser(setting=None, platform=None, env=None, exists=os.path.exists, which=shutil.which,
                 app_path=_windows_app_path, home=None):
    """The path of a Chromium-based browser, or None. ``setting`` (the user's tm1_browser) wins."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    if setting:
        return setting if exists(setting) else which(setting)
    if platform.startswith('win'):
        for name in WINDOWS_APPS:
            path = app_path(name)
            if path and exists(path):
                return path
        for variable, tail in WINDOWS_PATHS:
            if env.get(variable):
                path = env[variable].rstrip('\\') + '\\' + tail
                if exists(path):
                    return path
        return None
    if platform == 'darwin':
        # posixpath, not os.path: the platform asked about needn't be the one running
        home = home or os.path.expanduser('~')
        for folder in ('/Applications', posixpath.join(home, 'Applications')):
            for app in MAC_APPS:
                path = posixpath.join(folder, app + '.app', 'Contents', 'MacOS', app)
                if exists(path):
                    return path
        return None
    for command in LINUX_COMMANDS:
        path = which(command)
        if path:
            return path
    return None


# Talking to it


class _Pipe:
    """The DevTools protocol over --remote-debugging-pipe: JSON messages ending in a NUL byte, the
    browser reading on its descriptor 3 and writing on 4."""

    def __init__(self, write_fd, read_fd):
        self._write, self._read = write_fd, read_fd
        self._buffer = b''

    def send(self, message):
        data = json.dumps(message).encode('utf-8') + b'\0'
        try:
            while data:
                data = data[os.write(self._write, data):]
        except OSError as e:
            raise SignInCancelled('The browser closed.') from e

    def receive(self, timeout=CALL_TIMEOUT):
        while b'\0' not in self._buffer:
            ready, _, _ = select.select([self._read], [], [], timeout)
            if not ready:
                raise TimeoutError('The browser did not answer in {} seconds.'.format(timeout))
            try:
                chunk = os.read(self._read, 65536)
            except OSError as e:
                raise SignInCancelled('The browser closed.') from e
            if not chunk:
                raise SignInCancelled('The browser closed.')
            self._buffer += chunk
        message, self._buffer = self._buffer.split(b'\0', 1)
        return json.loads(message)

    def close(self):
        for fd in (self._write, self._read):
            try:
                os.close(fd)
            except OSError:
                pass


class _WebSocket:
    """The DevTools protocol over the browser's debugging port: the least of a WebSocket client
    (RFC 6455), text frames only, on 127.0.0.1."""

    def __init__(self, port, path):
        self._socket = socket.create_connection(('127.0.0.1', port), timeout=SIGN_IN_TIMEOUT)
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        request = ('GET {} HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                   'Sec-WebSocket-Key: {}\r\nSec-WebSocket-Version: 13\r\n\r\n').format(path, port, key)
        self._socket.sendall(request.encode('ascii'))
        head = b''
        while b'\r\n\r\n' not in head:
            chunk = self._socket.recv(1)
            if not chunk:
                raise BrowserError('The browser closed its debugging connection.')
            head += chunk
        if b' 101 ' not in head.split(b'\r\n', 1)[0]:
            raise BrowserError("The browser refused its debugging connection: " + head.split(b'\r\n', 1)[0].decode())

    def _exactly(self, count):
        data = b''
        while len(data) < count:
            try:
                chunk = self._socket.recv(count - len(data))
            except TimeoutError:
                # socket.timeout is TimeoutError, an OSError: not to be taken for a closed browser
                raise
            except OSError as e:
                # Windows resets the connection when the browser is killed (WinError 10054)
                raise SignInCancelled('The browser closed.') from e
            if not chunk:
                raise SignInCancelled('The browser closed.')
            data += chunk
        return data

    def send(self, message):
        data = json.dumps(message).encode('utf-8')
        mask, size = os.urandom(4), len(data)
        if size < 126:
            head = struct.pack('!BB', 0x81, 0x80 | size)
        elif size < 65536:
            head = struct.pack('!BBH', 0x81, 0x80 | 126, size)
        else:
            head = struct.pack('!BBQ', 0x81, 0x80 | 127, size)
        try:
            self._socket.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        except OSError as e:
            raise SignInCancelled('The browser closed.') from e

    def receive(self, timeout=CALL_TIMEOUT):
        self._socket.settimeout(timeout)
        while True:
            try:
                first, second = self._exactly(2)
            except TimeoutError as e:
                raise TimeoutError('The browser did not answer in {} seconds.'.format(timeout)) from e
            size = second & 0x7f
            if size == 126:
                size = struct.unpack('!H', self._exactly(2))[0]
            elif size == 127:
                size = struct.unpack('!Q', self._exactly(8))[0]
            payload = self._exactly(size)
            opcode = first & 0x0f
            if opcode == 8:
                raise SignInCancelled('The browser closed.')
            if opcode == 1:
                return json.loads(payload)

    def close(self):
        try:
            self._socket.close()
        except OSError:
            pass


class Browser:
    """A browser started for one sign-in, with the DevTools protocol on."""

    def __init__(self, executable, profile, url, hidden, transport=None):
        self._lock = threading.Lock()
        self._next_id = 0
        os.makedirs(profile, exist_ok=True)
        if os.name == 'posix':
            os.chmod(profile, 0o700)
        transport = transport or ('port' if os.name == 'nt' else 'pipe')
        self.host = urlsplit(url).hostname
        self._hidden = hidden
        args = [executable, '--user-data-dir=' + profile] + COMMON_ARGS
        # Both start on a blank page, so a passport left in the profile is gone before the sign-in
        args += ['--headless=new', 'about:blank'] if hidden else ['--app=about:blank', '--window-size=520,720']
        self._channel = None
        self._pid = None
        self._process = None
        try:
            self._start(args, transport, profile, url)
        except BaseException:
            # Whatever failed once the browser was started, it doesn't outlive the failure
            self.close()
            raise

    def _start(self, args, transport, profile, url):
        if transport == 'pipe':
            self._start_with_pipe(args + ['--remote-debugging-pipe'])
        else:
            self._start_with_port(args + ['--remote-debugging-port=0'], profile)
        try:
            self.call('Browser.getVersion', timeout=START_TIMEOUT)
        except NotAnswering as e:
            raise DebuggingBlocked(
                "The browser started but didn't let TM1 read the sign-in: its debugging connection is "
                "probably turned off by your organisation's browser policy (RemoteDebuggingAllowed).") from e
        if self._hidden:
            self._target = self.call('Target.createTarget', {'url': 'about:blank'}).get('targetId')
        else:
            pages = [t for t in self.call('Target.getTargets').get('targetInfos', []) if t.get('type') == 'page']
            self._target = pages[0]['targetId'] if pages else self.call(
                'Target.createTarget', {'url': 'about:blank'}).get('targetId')
        self.forget_cookie('cam_passport')
        session = self.call('Target.attachToTarget', {'targetId': self._target, 'flatten': True})['sessionId']
        # Started from the page, which returns at once: Page.navigate waits for the first response,
        # and a slow server would hold the sign-in up
        self.call('Runtime.evaluate', {'expression': 'location.replace({})'.format(json.dumps(url))}, session)

    def _start_with_pipe(self, args):
        import fcntl

        def above_the_targets(fd):
            # The browser's ends must land on 3 and 4. A fresh process's pipes can already be 3 and
            # 4, and dup2(3, 3) leaves close-on-exec set, so the browser would start without them:
            # move them above 10 first, from where dup2 gives the browser clean copies
            moved = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 10)
            os.close(fd)
            return moved

        to_browser_read, to_browser_write = os.pipe()
        from_browser_read, from_browser_write = os.pipe()
        to_browser_read = above_the_targets(to_browser_read)
        from_browser_write = above_the_targets(from_browser_write)
        devnull = above_the_targets(os.open(os.devnull, os.O_RDWR))
        # posix_spawn, not subprocess's preexec_fn, which isn't safe in a threaded process (Sublime's
        # plugin host): its file actions put the pipes where the browser expects them, at 3 and 4
        actions = [(os.POSIX_SPAWN_DUP2, devnull, 0), (os.POSIX_SPAWN_DUP2, devnull, 1),
                   (os.POSIX_SPAWN_DUP2, devnull, 2), (os.POSIX_SPAWN_DUP2, to_browser_read, 3),
                   (os.POSIX_SPAWN_DUP2, from_browser_write, 4)]
        try:
            try:
                self._pid = os.posix_spawn(args[0], args, os.environ, file_actions=actions, setsid=True)
            except NotImplementedError:
                # Some Python builds can't start a session this way: a process group of its own
                # (whose ID is its PID, as a session's would be) lets close() end it all the same
                self._pid = os.posix_spawn(args[0], args, os.environ, file_actions=actions, setpgroup=0)
        finally:
            for fd in (to_browser_read, from_browser_write, devnull):
                os.close(fd)
        self._process = None
        self._channel = _Pipe(to_browser_write, from_browser_read)

    def _start_with_port(self, args, profile):
        port_file = os.path.join(profile, 'DevToolsActivePort')
        if os.path.exists(port_file):
            os.remove(port_file)
        flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        # Its own session on POSIX, so close() can end its helper processes with it
        self._process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, creationflags=flags,
                                         start_new_session=os.name == 'posix')
        self._pid = self._process.pid
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise BrowserError('The browser exited at start (code {}).'.format(self._process.returncode))
            try:
                with open(port_file, encoding='utf-8') as f:
                    lines = f.read().split('\n')
                if len(lines) >= 2 and lines[0].strip():
                    self._channel = _WebSocket(int(lines[0]), lines[1].strip())
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise BrowserError('The browser opened no debugging port.')

    def call(self, method, params=None, session=None, timeout=CALL_TIMEOUT):
        """A DevTools protocol command: to the browser, or to one page's ``session``."""
        with self._lock:
            self._next_id += 1
            ident = self._next_id
            message = {'id': ident, 'method': method, 'params': params or {}}
            if session:
                message['sessionId'] = session
            self._channel.send(message)
            while True:
                try:
                    message = self._channel.receive(timeout)
                except TimeoutError as e:
                    raise NotAnswering('The browser stopped answering ({}).'.format(method)) from e
                if message.get('id') == ident:
                    if 'error' in message:
                        raise BrowserError('{}: {}'.format(method, message['error'].get('message')))
                    return message.get('result', {})

    def cookie(self, name, host):
        """The value of the cookie named ``name`` that the browser would send to ``host``, or None."""
        for cookie in self.call('Storage.getCookies').get('cookies', []):
            domain = cookie.get('domain', '').lstrip('.')
            if cookie.get('name') == name and (host == domain or host.endswith('.' + domain)):
                return cookie.get('value')
        return None

    def forget_cookie(self, name, host=None):
        """Deletes the cookie from the profile, for the sign-in's host."""
        host = host or self.host
        stale = []
        for cookie in self.call('Storage.getCookies').get('cookies', []):
            domain = cookie.get('domain', '').lstrip('.')
            if cookie.get('name') == name and (host == domain or host.endswith('.' + domain)):
                stale.append({'name': name, 'value': '', 'domain': cookie['domain'], 'path': cookie.get('path', '/'),
                              'expires': 1})
        if stale:
            self.call('Storage.setCookies', {'cookies': stale})

    def page_url(self):
        """The address of the page the sign-in is on."""
        target_id = getattr(self, '_target', None)
        for target in self.call('Target.getTargets').get('targetInfos', []):
            # Hidden, the browser also has the blank page it started with: follow the sign-in's own
            if target.get('type') == 'page' and (target_id is None or target.get('targetId') == target_id):
                return target.get('url', '')
        return ''

    def _kill_tree(self):
        if os.name == 'posix':
            try:
                os.killpg(self._pid, 9)
            except (ProcessLookupError, PermissionError):
                pass
        else:
            if self.running():
                subprocess.run(['taskkill', '/T', '/F', '/PID', str(self._pid)], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, check=False)
        if self._process is not None and self._process.poll() is None:
            try:
                self._process.kill()
            except OSError:
                pass

    def running(self):
        if self._pid is None:
            return False
        if self._process is not None:
            return self._process.poll() is None
        try:
            pid, _ = os.waitpid(self._pid, os.WNOHANG)
            return pid == 0
        except ChildProcessError:
            return False

    def close(self):
        if self._channel is not None:
            try:
                self.call('Browser.close', timeout=5)
            except Exception:
                pass
            self._channel.close()
        if self._pid is None:
            return
        deadline = time.monotonic() + 5
        while self.running() and time.monotonic() < deadline:
            time.sleep(0.05)
        # Always end the whole group: the browser's helpers outlive a main process that crashed or
        # was killed, and would keep the profile (and the pipe) open
        self._kill_tree()
        if self._process is not None:
            self._process.wait(timeout=5)
        else:
            try:
                os.waitpid(self._pid, 0)
            except ChildProcessError:
                pass


# How long the hidden window may sit on another host's page (the provider's login) before that's
# taken to mean the user is needed
SETTLED = 2.0


def wait_for_cookie(browser, name, host, timeout, poll=0.5, give_up_when_user_needed=False, home=None):
    """The cookie once the browser has it, or None after ``timeout``. With
    ``give_up_when_user_needed``, also None once the page has settled away from ``home`` (the
    sign-in's host:port; ``host`` by default): a sign-in that needs no user goes straight back."""
    home = home or host
    deadline = time.monotonic() + timeout
    away_since, away_url = None, None
    while time.monotonic() < deadline:
        if not browser.running():
            raise SignInCancelled('The sign-in window was closed.')
        value = browser.cookie(name, host)
        if value:
            # Not left in the profile for the next sign-in to mistake for a new one
            try:
                browser.forget_cookie(name, host)
            except BrowserError:
                pass
            return value
        if give_up_when_user_needed:
            url = browser.page_url()
            # host and port: a provider can share Cognos's host name (cookies don't care about ports)
            if url.startswith('http') and urlsplit(url).netloc not in (home, host):
                if url != away_url:
                    away_since, away_url = time.monotonic(), url
                elif time.monotonic() - away_since >= SETTLED:
                    return None
            else:
                away_since, away_url = None, None
        time.sleep(poll)
    return None


def _start(executable, profile, url, hidden, transport):
    """A browser, started. One that quits as it starts failed: nobody closed a window, so it's no
    cancel (a second browser on a profile in use hands over to the first and quits, for one)."""
    try:
        return Browser(executable, profile, url, hidden=hidden, transport=transport)
    except SignInCancelled as e:
        raise BrowserError('The browser quit as soon as it started. Another tm1cm may be signing in with the same '
                           'browser profile: try again once it has finished.') from e


def read_cookie(executable, profile, url, name='cam_passport', host=None, hidden_first=True, transport=None,
                timeout=SIGN_IN_TIMEOUT, silent_timeout=SILENT_TIMEOUT, on_window=None, window=True):
    """Opens ``url`` and returns the cookie ``name`` once the browser has it for ``host`` (by
    default the URL's). Tries a hidden window first, which is enough when the provider still
    remembers the user; then, unless ``window`` is False, a window the user signs in in."""
    host = host or urlsplit(url).hostname
    if hidden_first:
        browser = _start(executable, profile, url, True, transport)
        try:
            value = wait_for_cookie(browser, name, host, silent_timeout, give_up_when_user_needed=True,
                                    home=urlsplit(url).netloc)
        except SignInCancelled:
            value = None
        finally:
            browser.close()
        if value:
            return value
    if not window:
        raise SignInNeedsUser('The sign-in needs you, and there is no window to sign in in.')
    if on_window is not None:
        on_window()
    browser = _start(executable, profile, url, False, transport)
    try:
        value = wait_for_cookie(browser, name, host, timeout)
    finally:
        browser.close()
    if not value:
        raise SignInTimedOut('No sign-in in {} seconds.'.format(timeout))
    return value
