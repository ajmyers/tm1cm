"""tm1cm.browser: finding a browser on each platform, and reading a cookie from it. Ported from
Sublime-TM1's tests of the same module.

The tests that start a browser run wherever one is installed, as on GitHub's runners (Chrome);
elsewhere they're skipped.
"""

import os
import subprocess
import threading
import time

import pytest

from tests.tm1cm.fake_servers import LoginServer
from tm1cm import browser
from tm1cm.browser import Browser
from tm1cm.browser import SignInCancelled
from tm1cm.browser import find_browser
from tm1cm.browser import read_cookie

# Finding one


def test_windows_prefers_the_registered_app_paths():
    registered = {'chrome.exe': r'D:\Apps\Chrome\chrome.exe'}
    path = find_browser(platform='win32', env={}, exists=lambda p: p == registered['chrome.exe'],
                        app_path=registered.get)
    assert path == r'D:\Apps\Chrome\chrome.exe'


def test_windows_finds_edge_where_windows_puts_it():
    edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    path = find_browser(platform='win32', env={'ProgramFiles(x86)': r'C:\Program Files (x86)'},
                        exists=lambda p: p == edge, app_path=lambda name: None)
    assert path == edge


def test_macos_looks_in_applications_and_the_users_own():
    chrome = '/Users/me/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    assert find_browser(platform='darwin', exists=lambda p: p == chrome, home='/Users/me') == chrome
    edge = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
    assert find_browser(platform='darwin', exists=lambda p: p == edge, home='/Users/me') == edge


def test_linux_looks_on_the_path():
    on_path = {'chromium': '/usr/bin/chromium'}
    assert find_browser(platform='linux', which=on_path.get) == '/usr/bin/chromium'
    assert find_browser(platform='linux', which=lambda name: None) is None


def test_the_users_setting_wins():
    assert find_browser(setting='/opt/b/browser', exists=lambda p: p == '/opt/b/browser') == '/opt/b/browser'
    assert find_browser(setting='my-chrome', exists=lambda p: False, which={'my-chrome': '/u/my-chrome'}.get) \
        == '/u/my-chrome'


# Using one


def processes_using(profile):
    """The browser processes still running with this profile, where that can be asked."""
    import subprocess

    if os.name != 'posix':
        return []
    time.sleep(0.5)
    listing = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True).stdout
    return [line for line in listing.splitlines() if str(profile) in line]


EXECUTABLE = find_browser()
needs_browser = pytest.mark.skipif(EXECUTABLE is None, reason='no Chromium-based browser installed')
TRANSPORTS = ['port'] + (['pipe'] if os.name == 'posix' else [])


@pytest.fixture(scope='module', autouse=True)
def started_once(tmp_path_factory):
    """Start the browser once, with time to spare, before any test that times its start.

    A fresh CI runner's first start of Chrome can take more than the 15 to 30 s tm1cm gives it
    (its files not yet in the page cache, font caches still to build): the first two tests then
    failed on a slow runner while every later start was quick. That measures the runner, not
    tm1cm, so the cold start happens here.
    """
    if EXECUTABLE is None:
        return
    profile = str(tmp_path_factory.mktemp('started-once'))
    try:
        subprocess.run([EXECUTABLE, '--user-data-dir=' + profile, '--no-first-run', '--headless=new',
                        '--dump-dom', 'about:blank'],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except subprocess.TimeoutExpired:
        pass  # Warm enough or not, the tests say what's wrong


@pytest.fixture
def server():
    s = LoginServer()
    yield s
    s.stop()


@needs_browser
@pytest.mark.parametrize('transport', TRANSPORTS)
def test_reads_an_httponly_cookie_from_a_hidden_window_and_closes_the_browser(server, tmp_path, transport):
    seen = []
    original = Browser.__init__

    def keep(self, *args, **kwargs):
        original(self, *args, **kwargs)
        seen.append(self)

    browser_init = pytest.MonkeyPatch()
    browser_init.setattr(Browser, '__init__', keep)
    try:
        value = read_cookie(EXECUTABLE, str(tmp_path / 'profile'), server.url, transport=transport)
    finally:
        browser_init.undo()
    assert value == 'MTsxMDE6passport'
    assert len(seen) == 1 and not seen[0].running()
    assert not processes_using(tmp_path / 'profile')


@needs_browser
@pytest.mark.parametrize('transport', TRANSPORTS)
def test_reads_only_the_cookie_asked_for_on_the_host_asked_for(server, tmp_path, transport):
    b = Browser(EXECUTABLE, str(tmp_path / 'profile'), server.url, hidden=True, transport=transport)
    try:
        assert browser.wait_for_cookie(b, 'cam_passport', '127.0.0.1', 15) == 'MTsxMDE6passport'
        assert b.cookie('cam_passport', 'cognos.example.com') is None
        assert b.cookie('missing', '127.0.0.1') is None
    finally:
        b.close()


@needs_browser
@pytest.mark.parametrize('transport', TRANSPORTS)
def test_a_window_closed_before_signing_in_is_a_cancel(tmp_path, transport):
    slow = LoginServer(delay=30)
    b = Browser(EXECUTABLE, str(tmp_path / 'profile'), slow.url, hidden=True, transport=transport)
    try:
        # Only the main process, as a crash would: its helpers must not outlive close()
        threading.Timer(1.0, lambda: os.kill(b._pid, 9)).start()
        with pytest.raises(SignInCancelled):
            browser.wait_for_cookie(b, 'cam_passport', '127.0.0.1', 20)
    finally:
        b.close()
        slow.stop()
    assert not processes_using(tmp_path / 'profile')


@needs_browser
@pytest.mark.skipif(os.name != 'posix', reason='permissions are POSIX')
def test_the_profile_is_private(server, tmp_path):
    profile = tmp_path / 'profile'
    read_cookie(EXECUTABLE, str(profile), server.url, transport='pipe')
    assert (profile.stat().st_mode & 0o777) == 0o700


@needs_browser
@pytest.mark.skipif(os.name != 'posix', reason='the pipe transport is POSIX')
def test_the_pipe_works_from_a_fresh_process(server, tmp_path):
    # A fresh process's pipes land on descriptors 3 and 4, where the browser expects its own:
    # the case pytest, with many files open, never hits
    import subprocess
    import sys

    script = 'from tm1cm.browser import read_cookie; print(read_cookie({exe!r}, {profile!r}, {url!r}, transport="pipe"))'.format(
        exe=EXECUTABLE, profile=str(tmp_path / 'profile'), url=server.url)
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=60)
    assert result.stdout.strip() == 'MTsxMDE6passport', result.stderr[-2000:]


class SilentEndpoint:
    """A debugging endpoint that completes the WebSocket handshake and then says nothing, or hangs up."""

    def __init__(self, hang_up=False):
        import socket

        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.hang_up = hang_up
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        connection, _ = self.listener.accept()
        request = b''
        while b'\r\n\r\n' not in request:
            request += connection.recv(1024)
        connection.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n')
        if self.hang_up:
            connection.close()
        else:
            time.sleep(10)


def test_a_browser_that_stops_answering_times_out_rather_than_seeming_closed():
    # socket.timeout is an OSError: it mustn't be mistaken for the browser closing (Windows)
    channel = browser._WebSocket(SilentEndpoint().port, '/devtools/browser/x')
    with pytest.raises(TimeoutError):
        channel.receive(timeout=0.5)


def test_a_browser_that_hangs_up_is_closed():
    channel = browser._WebSocket(SilentEndpoint(hang_up=True).port, '/devtools/browser/x')
    with pytest.raises(SignInCancelled):
        channel.receive(timeout=5)


@needs_browser
@pytest.mark.parametrize('transport', TRANSPORTS)
def test_a_failure_after_the_browser_started_leaves_no_browser(server, tmp_path, transport, monkeypatch):
    def fails(self, name, host=None):
        raise browser.BrowserError('a step after the start failed')

    monkeypatch.setattr(Browser, 'forget_cookie', fails)
    with pytest.raises(browser.BrowserError, match='after the start'):
        Browser(EXECUTABLE, str(tmp_path / 'profile'), server.url, hidden=True, transport=transport)
    assert not processes_using(tmp_path / 'profile')


@needs_browser
def test_only_the_hidden_window_when_there_is_no_one_to_sign_in(tmp_path):
    provider = LoginServer(needs_user=True)
    try:
        with pytest.raises(browser.SignInNeedsUser):
            read_cookie(EXECUTABLE, str(tmp_path / 'profile'), provider.url, window=False, silent_timeout=8)
    finally:
        provider.stop()
    assert not processes_using(tmp_path / 'profile')


@needs_browser
@pytest.mark.skipif(os.name != 'posix', reason='the pipe transport is POSIX')
def test_the_pipe_works_where_python_cant_start_a_session(server, tmp_path, monkeypatch):
    # Some Python builds refuse posix_spawn's setsid: the browser gets a process group instead
    spawn = os.posix_spawn
    calls = []

    def without_setsid(*args, **kwargs):
        calls.append(kwargs)
        if kwargs.get('setsid'):
            raise NotImplementedError('posix_spawn: setsid unavailable on this platform')
        return spawn(*args, **kwargs)

    monkeypatch.setattr(os, 'posix_spawn', without_setsid)
    assert read_cookie(EXECUTABLE, str(tmp_path / 'profile'), server.url, transport='pipe') == 'MTsxMDE6passport'
    assert any(call.get('setpgroup') == 0 for call in calls)
    assert not processes_using(tmp_path / 'profile')


@needs_browser
def test_a_browser_that_quits_as_it_starts_is_a_failure_not_a_cancel(tmp_path):
    # A second browser on a profile in use hands over to the first and quits at once
    profile = str(tmp_path / 'profile')
    first = Browser(EXECUTABLE, profile, 'about:blank', hidden=True)
    try:
        with pytest.raises(browser.BrowserError) as raised:
            read_cookie(EXECUTABLE, profile, 'about:blank', window=False, silent_timeout=5)
    finally:
        first.close()
    assert not isinstance(raised.value, SignInCancelled)
    assert 'quit' in str(raised.value)
