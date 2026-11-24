"""How tm1cm logs in to TM1: every way TM1 and Cognos offer, worked out when the settings don't say.

The settings in connect.yaml and credentials.yaml choose, in this order:

1. ``cam_passport``: logs in with that passport.
2. ``gateway``: a passport from a CAM gateway with Windows single sign-on. Through
   requests_negotiate_sspi when it's installed, as TM1py did; otherwise through the browser,
   which does the Windows sign-on itself.
3. ``auth``: ``basic`` (TM1's own security), ``cam`` (a user and password in a CAM namespace) or
   ``browser`` (signing in to the namespace in a browser window, for a CAM passport).
4. A ``password``: TM1's own security, or CAM with ``namespace``, exactly as tm1cm 0.9 and 1.0
   logged in. Nothing is asked of any server first.
5. Otherwise tm1cm asks TM1 (its 401 says Basic, or CAM with Cognos's address) and then Cognos
   (whether the namespace prompts for a password or sends a browser to sign in), with
   unauthenticated requests (tm1cm.discovery). Without a namespace, Cognos's namespaces are listed
   and the user picks one. ``dispatcher`` gives Cognos's address when TM1's isn't reachable.

What's missing is asked for in the terminal: the user, the password (and again when TM1 refuses a
typed one), the namespace. Without a terminal (CI, a scheduled run) nothing is asked: a password
that isn't set is empty, as before, and anything else missing is an error saying which setting to
add.

The browser sign-in (tm1cm.browser) opens Cognos's own login in a private profile of a
Chromium-based browser, and reads the cam_passport cookie Cognos sets. A hidden window is tried
first, which is enough while the provider remembers the user, even without a terminal. When the
browser can't sign in, the user can log in with a user and password instead, paste a passport,
try again, or cancel. Passports are kept in memory for the run, and fetched again once when TM1
refuses one.
"""
import getpass
import logging
import os
import sys
from dataclasses import dataclass

from skipcheck_tm1 import auth

from tm1cm import browser
from tm1cm import discovery
from tm1cm.errors import Cancelled
from tm1cm.errors import CERTIFICATE_HINT
from tm1cm.errors import ConfigError
from tm1cm.errors import LoginError
from tm1cm.errors import LoginRejected
from tm1cm.errors import ServerUnreachable
from tm1cm.errors import secret

logger = logging.getLogger(__name__)

METHODS = ('basic', 'cam', 'browser')
# How often a typed password may be refused before giving up
ATTEMPTS = 3

# Passports from browser sign-ins, by login address, for the rest of the run
_passports = {}


def forget_passports():
    _passports.clear()


@dataclass(frozen=True)
class Method:
    # "basic", "cam", "browser", "passport" (cam_passport), "pasted" (a passport the user pasted)
    # or "gateway"
    kind: str
    # Cognos's address, for "browser"
    dispatcher: str = ''
    namespace: str = ''


class Terminal:
    """The user at a terminal, when there is one."""

    def __init__(self, stdin=None, stderr=None):
        self._stdin = stdin
        self._stderr = stderr

    @property
    def stdin(self):
        return self._stdin or sys.stdin

    @property
    def stderr(self):
        return self._stderr or sys.stderr

    def available(self):
        try:
            return self.stdin.isatty()
        except (AttributeError, ValueError):
            return False

    def say(self, text):
        print(text, file=self.stderr, flush=True)

    def ask(self, caption):
        if self._stdin is None:
            # input(), not sys.stdin.readline(): it reads no further than the line, so what's
            # typed next is left for getpass, which reads the terminal itself
            try:
                return input(caption)
            except EOFError:
                raise Cancelled('Cancelled.') from None
        self.stderr.write(caption)
        self.stderr.flush()
        line = self.stdin.readline()
        if not line:
            raise Cancelled('Cancelled.')
        return line.rstrip('\r\n')

    def ask_secret(self, caption):
        try:
            return getpass.getpass(caption, stream=self.stderr)
        except EOFError:
            raise Cancelled('Cancelled.') from None

    def choose(self, caption, options):
        """The index of the option the user picks, or None to cancel."""
        self.say(caption)
        for number, option in enumerate(options, 1):
            self.say(f'  {number}. {option}')
        while True:
            answer = self.ask(f'Choose 1-{len(options)} (Enter to cancel): ').strip()
            if not answer:
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1


def can_open_window(platform=None, env=None):
    """Whether a browser window can be shown: always on Windows and macOS; elsewhere, with a display."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    if platform.startswith('win') or platform == 'darwin':
        return True
    return bool(env.get('DISPLAY') or env.get('WAYLAND_DISPLAY'))


def profile_folder(platform=None, env=None, home=None):
    """The browser profile sign-ins use: tm1cm's own, in the user's cache folder, never their own
    browser profile."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = home or os.path.expanduser('~')
    if platform.startswith('win'):
        base = os.path.join(env.get('LOCALAPPDATA') or os.path.join(home, 'AppData', 'Local'), 'tm1cm', 'Cache')
    elif platform == 'darwin':
        base = os.path.join(home, 'Library', 'Caches', 'tm1cm')
    else:
        base = os.path.join(env.get('XDG_CACHE_HOME') or os.path.join(home, '.cache'), 'tm1cm')
    return os.path.join(base, 'browser-profile')


def sign_in(url, settings, terminal, root):
    """A CAM passport from a browser sign-in at ``url``: a hidden window first, then, when there's
    someone to sign in and a screen to sign in on, a window."""
    setting = settings.get('browser') or None
    executable = browser.find_browser(setting)
    if executable is None:
        raise browser.BrowserError(
            'No Chrome, Edge, Brave or Chromium was found{}. Install one, or set browser in connect.yaml to its path.'.format(
                f' at "{setting}"' if setting else ''))
    window = terminal.available() and can_open_window()
    logger.info(f'Signing in through the browser at {url}')
    return browser.read_cookie(executable, profile_folder(), url, window=window,
                               on_window=lambda: terminal.say(f'Sign in in the browser window to connect to TM1 at {root}.'))


def _sspi():
    try:
        import requests
        from requests_negotiate_sspi import HttpNegotiateAuth
    except ImportError:
        return None
    return requests, HttpNegotiateAuth


def gateway_passport(gateway, namespace, verify, sspi):
    """A CAM passport from a CAM gateway with Windows SSO, as TM1py got it."""
    requests, negotiate = sspi
    response = requests.get(gateway, auth=negotiate(), verify=verify, params={'CAMNamespace': namespace})
    if response.status_code != 200:
        raise LoginError(f'The CAM gateway at {gateway} refused the Windows sign-on (HTTP {response.status_code}).')
    if 'cam_passport' not in response.cookies:
        raise LoginError(f'The CAM gateway at {gateway} gave no cam_passport cookie.')
    return response.cookies['cam_passport']


def _password(settings):
    import base64

    password = settings.get('password')
    if password and str(settings.get('decode_b64', False)).strip().upper() == 'TRUE':
        password = base64.b64decode(password).decode('utf-8')
    return secret(str(password)) if password else None


class Login:
    """The login for one TM1 server: :meth:`authenticator` for each attempt, and
    :meth:`rejected` when TM1 refuses one, which says whether to try again."""

    def __init__(self, settings, root, verify, terminal=None, http=None, sign_in=None, sspi=None):
        self.settings = settings
        self.root = root
        self.verify = verify
        self.terminal = terminal or Terminal()
        self._http = http
        # Looked up when used, not bound here, so tests can stand in for the browser and SSPI
        self._sign_in = sign_in or (lambda *args: globals()['sign_in'](*args))
        self._sspi = sspi or (lambda: globals()['_sspi']())
        self.method = None
        self._user = str(settings.get('user') or '') or None
        self._password = _password(settings)
        # A user with an empty password logged in under 1.0 without being asked anything: so with
        # a user and no password, the empty one is tried first, and asked for only if TM1 refuses it
        self._empty_first = self._user is not None and self._password is None
        self._tried_empty = False
        self._typed = False
        self._attempts = 1
        self._pasted = None
        self._signed_in_again = False
        self._challenge = None
        secret(settings.get('cam_passport'))

    # --- Working out the method --------------------------------------------------------------

    def _probe(self, what, step):
        """Runs a probe, turning a server that can't be reached into ServerUnreachable."""
        import httpx2

        try:
            return step()
        except httpx2.TransportError as e:
            hint = CERTIFICATE_HINT if 'CERTIFICATE_VERIFY_FAILED' in str(e) else None
            raise ServerUnreachable(f"Couldn't reach {what}: {e}", hint) from e

    def _tm1_challenge(self):
        if self._challenge is None:
            http = self._http or discovery.client(self.verify)
            self._challenge = self._probe(f'TM1 at {self.root}', lambda: discovery.challenge(self.root, self.verify, http))
        return self._challenge

    def _dispatcher(self):
        configured = str(self.settings.get('dispatcher') or '')
        if configured:
            return configured
        try:
            return self._tm1_challenge().dispatcher
        except discovery.DiscoveryError as e:
            raise LoginError(f"Couldn't work out where Cognos is for TM1 at {self.root}: {e}",
                             "Set namespace in credentials.yaml, or dispatcher (Cognos's address) in connect.yaml.") from e

    def _choose_namespace(self, dispatcher):
        import httpx2

        if not dispatcher:
            raise LoginError(f"TM1 at {self.root} uses CAM security, and didn't say where Cognos is.",
                             'Set namespace in credentials.yaml, or dispatcher (Cognos\'s address) in connect.yaml.')
        try:
            options = discovery.namespaces(dispatcher, self.verify, self._http)
        except (discovery.DiscoveryError, httpx2.HTTPError) as e:
            raise LoginError(f"TM1 at {self.root} uses CAM security, and Cognos at {dispatcher} didn't list its namespaces: {e}",
                             'Set namespace in credentials.yaml, or dispatcher (Cognos\'s address, if TM1\'s isn\'t reachable from here) '
                             'in connect.yaml.') from e
        if len(options) == 1:
            return options[0]
        if not options:
            raise LoginError(f'TM1 at {self.root} uses CAM security, and Cognos lists no namespaces.', 'Set namespace in credentials.yaml.')
        if not self.terminal.available():
            raise LoginError(f'TM1 at {self.root} uses CAM security: say which namespace to log in to.',
                             f'Set namespace in credentials.yaml to one of: {", ".join(options)}.')
        index = self.terminal.choose(f'TM1 at {self.root} uses CAM security. Which namespace do you log in to?', options)
        if index is None:
            raise Cancelled('Cancelled.')
        return options[index]

    def _password_or_browser(self, dispatcher, namespace):
        """"cam" or "browser", as Cognos says the namespace logs on; "cam" when it can't be asked."""
        import httpx2

        if not dispatcher:
            return Method('cam', namespace=namespace)
        try:
            kind = discovery.login_kind(dispatcher, namespace, self.verify, self._http)
        except (discovery.DiscoveryError, httpx2.HTTPError) as e:
            logger.info(f"Couldn't ask Cognos at {dispatcher} how {namespace} logs on ({e}): logging in with a password. "
                        "If Cognos is at another address from here, set dispatcher in connect.yaml.")
            return Method('cam', dispatcher, namespace)
        return Method('browser' if kind == 'browser' else 'cam', dispatcher, namespace)

    def resolve(self):
        """The method, from the settings, or else from TM1 and Cognos."""
        settings = self.settings
        namespace = str(settings.get('namespace') or '')
        if settings.get('cam_passport'):
            return Method('passport')
        if settings.get('gateway'):
            return Method('gateway', namespace=namespace)

        method = str(settings.get('auth') or '').strip().lower()
        if method and method not in METHODS:
            raise ConfigError(f'auth is "{settings.get("auth")}" in connect.yaml or credentials.yaml.',
                              f'Set it to one of {", ".join(METHODS)}, or remove it to have tm1cm work it out.')
        if method == 'basic':
            return Method('basic')
        if method == 'cam':
            return Method('cam', namespace=namespace or self._choose_namespace(self._dispatcher()))
        if method == 'browser':
            dispatcher = self._dispatcher()
            if not dispatcher:
                raise LoginError(f"TM1 at {self.root} didn't say where Cognos is, to sign in through the browser.",
                                 "Set dispatcher in connect.yaml to Cognos's address.")
            return Method('browser', dispatcher, namespace or self._choose_namespace(dispatcher))

        if self._password:
            # Settled by the settings: as tm1cm always logged in, asking nothing first
            return Method('cam', namespace=namespace) if namespace else Method('basic')

        try:
            found = self._tm1_challenge()
        except discovery.DiscoveryError as e:
            logger.info(f"Couldn't work out how to log in to {self.root} ({e}): logging in with the settings as they are")
            return Method('cam', namespace=namespace) if namespace else Method('basic')
        if found.kind == 'basic' and not namespace:
            return Method('basic')
        dispatcher = str(settings.get('dispatcher') or '') or found.dispatcher
        namespace = namespace or self._choose_namespace(dispatcher)
        return self._password_or_browser(dispatcher, namespace)

    # --- Credentials -------------------------------------------------------------------------

    def describe(self):
        user = self._user or '?'
        method = self.method
        if method is not None and method.kind == 'cam' and method.namespace:
            user = f'{method.namespace}\\{user}'
        return f'{user} at {self.root}'

    def _credentials(self):
        if not self._user:
            if not self.terminal.available():
                raise LoginError(f'No user to log in to TM1 at {self.root} as.', 'Set user in credentials.yaml.')
            self._user = self.terminal.ask(f'TM1 user for {self.root}: ').strip()
            if not self._user:
                raise Cancelled('Cancelled.')
        if self._password is None:
            if self._empty_first and not self._tried_empty:
                self._tried_empty = True
                return self._user, ''
            if self.terminal.available():
                self._password = secret(self.terminal.ask_secret(f'Password for {self.describe()}: '))
                self._typed = True
            else:
                # No one to ask: an empty password, as tm1cm always sent
                return self._user, ''
        return self._user, self._password

    def _login_url(self):
        if self.method.kind == 'gateway':
            return discovery.gateway_login_url(str(self.settings['gateway']), self.method.namespace)
        return discovery.browser_login_url(self.method.dispatcher, self.method.namespace)

    def _browser_passport(self):
        url = self._login_url()
        if url not in _passports:
            try:
                _passports[url] = secret(self._sign_in(url, self.settings, self.terminal, self.root))
            except browser.SignInCancelled as e:
                raise Cancelled('Sign-in cancelled: the browser window was closed.') from e
        return url

    def _fallback(self, error):
        """The browser couldn't sign in: offers the other ways in, or says what to set."""
        reason = str(error)
        if isinstance(error, browser.SignInNeedsUser) and self.terminal.available():
            reason = "the sign-in needs you, and there's no display here for a browser window"
        if not self.terminal.available():
            raise LoginError(f"Couldn't sign in to TM1 at {self.root} through the browser: {reason}",
                             'Run tm1cm once from a terminal to sign in, set cam_passport in credentials.yaml, or, for a namespace '
                             'that also takes a password, set auth: cam with user and password.') from error
        index = self.terminal.choose(f"The browser sign-in didn't work: {reason}\nHow do you want to log in?", [
            'With a user and password (for a namespace that also takes one)',
            'Paste a CAM passport (the cam_passport cookie of a browser signed in to Cognos)',
            'Try the browser again',
            'Cancel',
        ])
        if index == 0:
            self.method = Method('cam', self.method.dispatcher, self.method.namespace or str(self.settings.get('namespace') or ''))
        elif index == 1:
            self._pasted = secret(self.terminal.ask_secret('CAM passport: ').strip())
            self.method = Method('pasted')
        elif index != 2:
            raise Cancelled('Cancelled.') from error

    def authenticator(self):
        """skipcheck-tm1's authenticator for the next attempt, asking what's missing."""
        if self.method is None:
            self.method = self.resolve()
            logger.info(f'Logging in to {self.root} with {self.method.kind}')
        while True:
            kind = self.method.kind
            if kind == 'passport':
                return auth.cam_passport(str(self.settings['cam_passport']))
            if kind == 'pasted':
                return auth.cam_passport(self._pasted)
            if kind == 'gateway':
                sspi = self._sspi()
                if sspi is not None:
                    return auth.cam_passport(secret(gateway_passport(str(self.settings['gateway']), self.method.namespace, self.verify, sspi)))
            if kind in ('gateway', 'browser'):
                try:
                    url = self._browser_passport()
                except browser.BrowserError as e:
                    self._fallback(e)
                    continue
                return auth.cam_passport(lambda: _passports[url])
            user, password = self._credentials()
            if kind == 'cam':
                return auth.cam_namespace(user, password, self.method.namespace)
            return auth.basic(user, password)

    def rejected(self):
        """TM1 refused the last attempt: whether to try again (with a new password, or a new
        passport), having said so."""
        kind = self.method.kind
        if kind in ('basic', 'cam') and self._tried_empty and not self._typed and self.terminal.available():
            # The empty password was refused: now ask for it
            return True
        if kind in ('basic', 'cam') and self._typed and self._attempts < ATTEMPTS:
            self._attempts += 1
            self._password = None
            self.terminal.say('TM1 refused the login. Try again.')
            return True
        if kind in ('browser', 'gateway') and not self._signed_in_again and self._uses_browser():
            self._signed_in_again = True
            _passports.pop(self._login_url(), None)
            self.terminal.say('TM1 refused the passport from the browser sign-in: signing in again.')
            return True
        return False

    def _uses_browser(self):
        return self.method.kind == 'browser' or self._sspi() is None

    def rejection(self):
        """The error for a login TM1 refused, saying what to check."""
        kind = self.method.kind
        if kind == 'passport':
            return LoginRejected(f'TM1 at {self.root} refused the cam_passport in credentials.yaml.',
                                 'A passport expires. Set a fresh one, or remove cam_passport to sign in through the browser.')
        if kind == 'pasted':
            return LoginRejected(f'TM1 at {self.root} refused the CAM passport that was pasted.', 'Copy a fresh one, or sign in another way.')
        if kind in ('browser', 'gateway'):
            return LoginRejected(f'TM1 at {self.root} refused the passport from Cognos.',
                                 'Check that the user you signed in as may use this TM1 server, and that TM1 and Cognos agree '
                                 '(TM1\'s ClientCAMURI).')
        if self._typed:
            return LoginRejected(f'TM1 refused the login for {self.describe()} {ATTEMPTS} times.')
        checks = 'user, password and namespace' if kind == 'cam' else 'user and password'
        return LoginRejected(f'TM1 refused the login for {self.describe()}.', f'Check {checks} in credentials.yaml.')
