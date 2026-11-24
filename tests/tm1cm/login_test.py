"""tm1cm.login: which way in each setting leads, what's asked, and what happens when TM1 refuses.

TM1 and Cognos are mocks that answer the probes as the real ones did (see discovery_test); the
browser sign-in is a stand-in, so these run anywhere. tm1_connect_test logs in for real, to a
fake TM1 over HTTP.
"""
import io

import httpx2
import pytest

from tests.tm1cm.discovery_test import mock
from tm1cm import browser
from tm1cm import errors
from tm1cm import login
from tm1cm.login import Login
from tm1cm.login import Method

ROOT = 'http://tm1:8010'


class FakeTerminal:
    """A user who answers from a script: ``answers`` for questions and choices, ``secrets`` for
    passwords and passports. ``present`` False: no terminal at all."""

    def __init__(self, answers=(), secrets=(), present=True):
        self.answers = list(answers)
        self.secrets = list(secrets)
        self.present = present
        self.said = []
        self.asked = []

    def available(self):
        return self.present

    def say(self, text):
        self.said.append(text)

    def ask(self, caption):
        self.asked.append(caption)
        return self.answers.pop(0)

    def ask_secret(self, caption):
        self.asked.append(caption)
        return self.secrets.pop(0)

    def choose(self, caption, options):
        self.asked.append(caption)
        self.said.extend(options)
        answer = self.answers.pop(0)
        return None if answer is None else int(answer)


NO_TERMINAL = FakeTerminal(present=False)


def no_probes():
    def refuse(request):
        raise AssertionError(f'probed {request.url}, though the settings say how to log in')
    return httpx2.Client(transport=httpx2.MockTransport(refuse))


class SignIns:
    """Stands in for the browser: the passports it gives, or the errors it raises, in turn."""

    def __init__(self, *results):
        self.results = list(results)
        self.urls = []

    def __call__(self, url, settings, terminal, root):
        self.urls.append(url)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


@pytest.fixture(autouse=True)
def fresh_passports():
    login.forget_passports()
    yield
    login.forget_passports()


def make(settings, terminal=NO_TERMINAL, http=None, sign_in=None, sspi=lambda: None):
    return Login(settings, ROOT, False, terminal, http=http or no_probes(), sign_in=sign_in or SignIns(), sspi=sspi)


# --- Settings that say how: logged in as before, without asking any server ----------------------

@pytest.mark.parametrize('settings, kind, authorization', [
    ({'user': 'admin', 'password': 'apple'}, 'basic', 'Basic admin'),
    ({'user': 'admin', 'password': 'apple', 'namespace': 'LDAP'}, 'cam', 'CAMNamespace LDAP/admin'),
    ({'cam_passport': 'abc123'}, 'passport', 'CAMPassport'),
    ({'auth': 'basic', 'user': 'admin', 'password': 'x'}, 'basic', 'Basic admin'),
    ({'auth': 'CAM', 'user': 'admin', 'password': 'x', 'namespace': 'LDAP'}, 'cam', 'CAMNamespace LDAP/admin'),
], ids=['password', 'password and namespace', 'cam_passport', 'auth basic', 'auth cam, in capitals'])
def test_settings_that_say_how_ask_no_server(settings, kind, authorization):
    signer = make(settings)

    assert signer.authenticator().describe() == authorization
    assert signer.method.kind == kind


def test_an_unknown_auth_is_a_config_error():
    with pytest.raises(errors.ConfigError, match='oidc'):
        make({'auth': 'oidc'}).authenticator()


def test_a_base64_password_is_decoded():
    signer = make({'user': 'admin', 'password': 'YXBwbGU=', 'decode_b64': True})

    assert signer.authenticator().authorization() == 'Basic ' + 'YWRtaW46YXBwbGU='


def test_a_password_without_a_terminal_is_empty_as_before():
    signer = make({'auth': 'basic', 'user': 'admin', 'password': ''})

    assert signer.authenticator().authorization() == 'Basic YWRtaW46'


# --- Asking for what's missing -----------------------------------------------------------------

def past_the_empty_password(signer):
    """A user and no password: the empty password goes first, as in 1.0; TM1 refuses it here."""
    assert signer.authenticator().authorization() == 'Basic YWRtaW46'
    assert signer.rejected()


def test_a_user_with_an_empty_password_logs_in_without_being_asked():
    terminal = FakeTerminal()
    for password in ['', None]:
        settings = {'auth': 'basic', 'user': 'admin'} if password is None else {'auth': 'basic', 'user': 'admin', 'password': password}
        signer = make(settings, terminal)

        assert signer.authenticator().authorization() == 'Basic YWRtaW46'
    assert terminal.asked == [] and terminal.said == []


def test_an_empty_password_tm1_refuses_is_asked_for_then_without_a_try_again():
    terminal = FakeTerminal(secrets=['apple'])
    signer = make({'auth': 'basic', 'user': 'admin', 'password': ''}, terminal)

    past_the_empty_password(signer)

    assert signer.authenticator().authorization() == 'Basic YWRtaW46YXBwbGU='
    assert terminal.said == []


def test_a_refused_empty_password_without_a_terminal_says_what_to_check():
    signer = make({'auth': 'basic', 'user': 'admin', 'password': ''})
    signer.authenticator()

    assert not signer.rejected()
    assert 'credentials.yaml' in signer.rejection().hint


def test_a_cam_user_with_an_empty_password_tries_it_first_in_the_namespace():
    terminal = FakeTerminal()
    signer = make({'auth': 'cam', 'user': 'admin', 'namespace': 'LDAP'}, terminal)

    assert signer.authenticator().describe() == 'CAMNamespace LDAP/admin'
    assert terminal.asked == []


def test_asks_for_the_password_when_none_is_set():
    terminal = FakeTerminal(secrets=['apple'])
    signer = make({'auth': 'basic', 'user': 'admin'}, terminal)

    past_the_empty_password(signer)
    assert signer.authenticator().authorization() == 'Basic YWRtaW46YXBwbGU='
    assert terminal.asked == [f'Password for admin at {ROOT}: ']


def test_asks_for_the_user_too_when_none_is_set():
    terminal = FakeTerminal(answers=['admin'], secrets=['apple'])
    signer = make({'auth': 'basic'}, terminal)

    assert signer.authenticator().describe() == 'Basic admin'


def test_no_user_without_a_terminal_says_which_setting_to_add():
    with pytest.raises(errors.LoginError) as raised:
        make({'auth': 'basic'}).authenticator()

    assert 'Set user in credentials.yaml' in raised.value.hint


def test_a_typed_password_is_asked_for_again_when_refused_up_to_three_times():
    terminal = FakeTerminal(secrets=['one', 'two', 'three'])
    signer = make({'auth': 'basic', 'user': 'admin'}, terminal)
    past_the_empty_password(signer)

    signer.authenticator()
    assert signer.rejected()
    assert signer.authenticator().authorization() == 'Basic ' + 'YWRtaW46dHdv'
    assert signer.rejected()
    signer.authenticator()
    assert not signer.rejected()
    assert '3 times' in signer.rejection().message


def test_a_password_from_the_file_is_not_retried():
    signer = make({'user': 'admin', 'password': 'apple', 'namespace': 'LDAP'})

    signer.authenticator()

    assert not signer.rejected()
    rejection = signer.rejection()
    assert isinstance(rejection, errors.LoginRejected)
    assert 'namespace' in rejection.hint and 'LDAP\\admin' in rejection.message


def test_the_password_is_never_in_a_message():
    terminal = FakeTerminal(secrets=['s3cr3t-pw'])
    signer = make({'auth': 'basic', 'user': 'admin'}, terminal)
    past_the_empty_password(signer)
    signer.authenticator()

    assert errors.redact('TM1 said s3cr3t-pw was wrong') == 'TM1 said *** was wrong'


# --- Working it out from TM1 and Cognos --------------------------------------------------------

def test_tm1s_own_security_is_found_and_the_password_asked_for():
    terminal = FakeTerminal(answers=['admin'], secrets=['apple'])
    signer = make({'user': '', 'password': '', 'namespace': ''}, terminal, http=mock(cam=False))

    assert signer.authenticator().describe() == 'Basic admin'


def test_a_password_namespace_asks_for_the_password():
    terminal = FakeTerminal(secrets=['apple'])
    signer = make({'user': 'admin', 'namespace': 'LDAP'}, terminal, http=mock())

    assert signer.authenticator().describe() == 'CAMNamespace LDAP/admin'
    assert signer.method == Method('cam', 'http://cognos:9300/bi/v1/disp', 'LDAP')


def test_a_browser_namespace_signs_in_through_the_browser():
    sign_ins = SignIns('passport-1')
    signer = make({'namespace': 'OIDC'}, FakeTerminal(), http=mock(), sign_in=sign_ins)

    authenticator = signer.authenticator()

    assert authenticator.authorization() == 'CAMPassport passport-1'
    assert sign_ins.urls == ['http://cognos:9300/bi/?CAMNamespace=OIDC']


def test_the_passport_is_kept_for_the_run():
    sign_ins = SignIns('passport-1')
    make({'namespace': 'OIDC'}, http=mock(), sign_in=sign_ins).authenticator()

    second = make({'namespace': 'OIDC'}, http=mock(), sign_in=sign_ins).authenticator()

    assert second.authorization() == 'CAMPassport passport-1'
    assert len(sign_ins.urls) == 1


def test_a_refused_passport_is_fetched_again_once():
    sign_ins = SignIns('old', 'new')
    signer = make({'namespace': 'OIDC'}, FakeTerminal(), http=mock(), sign_in=sign_ins)
    signer.authenticator()

    assert signer.rejected()
    assert signer.authenticator().authorization() == 'CAMPassport new'
    assert not signer.rejected()
    assert 'passport from Cognos' in signer.rejection().message


def test_without_a_namespace_the_user_picks_one_of_cognos():
    terminal = FakeTerminal(answers=['1'], secrets=['apple'])
    signer = make({'user': 'admin'}, terminal, http=mock())

    # Cognos lists OIDC (its default) first, then LDAP: the second is picked
    assert signer.authenticator().describe() == 'CAMNamespace LDAP/admin'
    assert terminal.said[:2] == ['OIDC', 'LDAP']


def test_without_a_namespace_or_terminal_the_namespaces_are_named():
    with pytest.raises(errors.LoginError) as raised:
        make({'user': 'admin'}, http=mock()).authenticator()

    assert 'OIDC, LDAP' in raised.value.hint


def test_the_dispatcher_setting_wins_over_tm1s():
    sign_ins = SignIns('p')
    make({'namespace': 'OIDC', 'dispatcher': 'http://cognos:9300/bi'}, http=mock(dispatcher='http://internal:9300/bi/v1/disp'),
         sign_in=sign_ins).authenticator()

    assert sign_ins.urls == ['http://cognos:9300/bi/?CAMNamespace=OIDC']


def test_auth_browser_signs_in_even_where_cognos_would_take_a_password():
    sign_ins = SignIns('p')
    make({'auth': 'browser', 'namespace': 'LDAP', 'user': 'admin', 'password': 'apple'}, http=mock(), sign_in=sign_ins).authenticator()

    assert sign_ins.urls == ['http://cognos:9300/bi/?CAMNamespace=LDAP']


def test_cognos_out_of_reach_falls_back_to_a_password():
    def handler(request):
        if request.url.host == 'cognos':
            raise httpx2.ConnectError('no route to cognos')
        return mock().get(str(request.url))
    terminal = FakeTerminal(secrets=['apple'])
    signer = make({'user': 'admin', 'namespace': 'LDAP'}, terminal, http=httpx2.Client(transport=httpx2.MockTransport(handler)))

    assert signer.authenticator().describe() == 'CAMNamespace LDAP/admin'


def test_tm1_out_of_reach_is_said_before_asking_anything():
    def handler(request):
        raise httpx2.ConnectError('connection refused')
    terminal = FakeTerminal()

    with pytest.raises(errors.ServerUnreachable, match='connection refused'):
        make({'user': 'admin'}, terminal, http=httpx2.Client(transport=httpx2.MockTransport(handler))).authenticator()
    assert terminal.asked == []


# --- When the browser can't sign in ------------------------------------------------------------

FAILED = browser.BrowserError('No Chrome, Edge, Brave or Chromium was found.')


def test_the_browser_failing_offers_a_user_and_password():
    terminal = FakeTerminal(answers=['0', 'admin'], secrets=['apple'])
    signer = make({'namespace': 'OIDC'}, terminal, http=mock(), sign_in=SignIns(FAILED))

    assert signer.authenticator().describe() == 'CAMNamespace OIDC/admin'
    assert 'No Chrome' in terminal.asked[0]


def test_the_browser_failing_offers_pasting_a_passport():
    terminal = FakeTerminal(answers=['1'], secrets=['  pasted-passport \n'])
    signer = make({'namespace': 'OIDC'}, terminal, http=mock(), sign_in=SignIns(FAILED))

    assert signer.authenticator().authorization() == 'CAMPassport pasted-passport'
    assert not signer.rejected()


def test_the_browser_failing_offers_trying_again():
    sign_ins = SignIns(FAILED, 'second-try')
    signer = make({'namespace': 'OIDC'}, FakeTerminal(answers=['2']), http=mock(), sign_in=sign_ins)

    assert signer.authenticator().authorization() == 'CAMPassport second-try'
    assert len(sign_ins.urls) == 2


@pytest.mark.parametrize('answer', ['3', None], ids=['Cancel', 'Enter'])
def test_the_browser_failing_can_be_cancelled(answer):
    signer = make({'namespace': 'OIDC'}, FakeTerminal(answers=[answer]), http=mock(), sign_in=SignIns(FAILED))

    with pytest.raises(errors.Cancelled):
        signer.authenticator()


def test_closing_the_sign_in_window_cancels():
    signer = make({'namespace': 'OIDC'}, FakeTerminal(), http=mock(), sign_in=SignIns(browser.SignInCancelled('closed')))

    with pytest.raises(errors.Cancelled, match='window was closed'):
        signer.authenticator()


def test_without_a_terminal_the_browser_failing_says_what_to_set():
    signer = make({'namespace': 'OIDC'}, http=mock(), sign_in=SignIns(browser.SignInNeedsUser('needs you')))

    with pytest.raises(errors.LoginError) as raised:
        signer.authenticator()
    assert 'cam_passport' in raised.value.hint


def test_with_a_terminal_but_no_display_the_reason_is_given():
    terminal = FakeTerminal(answers=['3'])
    signer = make({'namespace': 'OIDC'}, terminal, http=mock(), sign_in=SignIns(browser.SignInNeedsUser('needs you')))

    with pytest.raises(errors.Cancelled):
        signer.authenticator()
    assert 'no display' in terminal.asked[0]


# --- The CAM gateway ---------------------------------------------------------------------------

def test_a_gateway_signs_in_through_the_browser_without_sspi():
    sign_ins = SignIns('from-gateway')
    signer = make({'gateway': 'https://cognos/ibmcognos/cgi-bin/cognos.cgi', 'namespace': 'AD'}, sign_in=sign_ins)

    assert signer.authenticator().authorization() == 'CAMPassport from-gateway'
    assert sign_ins.urls == ['https://cognos/ibmcognos/cgi-bin/cognos.cgi?CAMNamespace=AD']


def test_a_gateway_uses_sspi_when_it_is_installed():
    asked = []

    class Response:
        status_code = 200
        cookies = {'cam_passport': 'from-sspi'}

    class Requests:
        @staticmethod
        def get(url, auth, verify, params):
            asked.append((url, params))
            return Response()

    signer = make({'gateway': 'https://cognos/gw', 'namespace': 'AD'}, sspi=lambda: (Requests, lambda: 'negotiate'))

    assert signer.authenticator().authorization() == 'CAMPassport from-sspi'
    assert asked == [('https://cognos/gw', {'CAMNamespace': 'AD'})]


# --- The terminal, the window and the profile ---------------------------------------------------

class Tty(io.StringIO):
    def isatty(self):
        return True


def test_the_terminal_asks_until_a_choice_is_valid():
    terminal = login.Terminal(stdin=Tty('9\nx\n2\n'), stderr=io.StringIO())

    assert terminal.available()
    assert terminal.choose('Which?', ['a', 'b']) == 1


def test_the_terminal_cancels_on_enter_and_end_of_input():
    assert login.Terminal(stdin=Tty('\n'), stderr=io.StringIO()).choose('Which?', ['a']) is None
    with pytest.raises(errors.Cancelled):
        login.Terminal(stdin=Tty(''), stderr=io.StringIO()).ask('User: ')


def test_no_terminal_when_stdin_is_not_one():
    assert not login.Terminal(stdin=io.StringIO('')).available()


@pytest.mark.parametrize('platform, env, expected', [
    ('win32', {}, True), ('darwin', {}, True), ('linux', {}, False),
    ('linux', {'DISPLAY': ':0'}, True), ('linux', {'WAYLAND_DISPLAY': 'wayland-0'}, True),
])
def test_a_window_needs_a_display_on_linux(platform, env, expected):
    assert login.can_open_window(platform, env) is expected


@pytest.mark.parametrize('platform, env, expected', [
    ('win32', {'LOCALAPPDATA': 'C:/Users/me/AppData/Local'}, 'C:/Users/me/AppData/Local/tm1cm/Cache/browser-profile'),
    ('darwin', {}, '/home/me/Library/Caches/tm1cm/browser-profile'),
    ('linux', {}, '/home/me/.cache/tm1cm/browser-profile'),
    ('linux', {'XDG_CACHE_HOME': '/var/cache/me'}, '/var/cache/me/tm1cm/browser-profile'),
])
def test_the_profile_is_tm1cms_own_in_the_users_cache(platform, env, expected):
    assert login.profile_folder(platform, env, home='/home/me').replace('\\', '/') == expected


def test_an_odd_answer_from_tm1_with_auth_set_is_a_login_error():
    def handler(request):
        return httpx2.Response(302, headers={'Location': 'http://elsewhere/'})
    http = httpx2.Client(transport=httpx2.MockTransport(handler))

    for auth in ['browser', 'cam']:
        with pytest.raises(errors.LoginError) as raised:
            make({'auth': auth}, http=http).authenticator()
        assert 'namespace' in raised.value.hint or 'dispatcher' in raised.value.hint
