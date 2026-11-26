"""Logging in to a real TM1 in CAM security, through a real Cognos and browser.

The cam fixture (tests/conftest.py, tests/tm1cm/cam_stack.py) starts the stack in Docker: Keycloak,
Cognos and a TM1 in CAM security. That needs a TM1 source and a Cognos source, such as
COGNOS_PRIVATE_IMAGE; without them these tests skip. Or point them at a stack started some other
way: TM1_CAM_URL names its TM1 (its REST URL, http://host:port/api/v1/), with CAM_NAMESPACE (one
that signs in in the browser), CAM_USER and CAM_PASSWORD, and COGNOS_URL when TM1's ClientCAMURI
isn't reachable from here. For a namespace that takes a password, set CAM_PASSWORD_NAMESPACE,
CAM_PASSWORD_USER and CAM_PASSWORD_PASSWORD too. skipcheck-tm1's pa-setup starts such a stack
(cognos.oidc, cam.namespace oidc), as Sublime-TM1's live tests use.

A real browser (hidden) opens Cognos's login for the namespace; the test fills in Keycloak's form
in it, as the user would, and everything else is the real flow.
"""
import json
import os
import time
from urllib.parse import urlsplit

import pytest
import yaml

from tests.tm1cm import util
from tests.tm1cm.login_test import FakeTerminal
from tm1cm import __main__ as cli
from tm1cm import browser
from tm1cm import discovery
from tm1cm import errors
from tm1cm import login
from tm1cm import tm1
from tm1cm.scaffold import create_scaffold

# The real sign-in, before the fixture below stands in for the user
REAL_SIGN_IN = login.sign_in
NO_BROWSER = '/nonexistent/chrome'
EXECUTABLE = browser.find_browser()
pytestmark = pytest.mark.skipif(EXECUTABLE is None, reason='no Chromium-based browser installed')

FILL_KEYCLOAK = '''(function () {
  var form = document.getElementById('kc-form-login');
  if (!form) return false;
  document.getElementById('username').value = %s;
  document.getElementById('password').value = %s;
  form.submit();
  return true;
})()'''


# The stack the tests run against: set by the autouse fixture below, from the cam fixture
CAM = None


def root():
    return CAM.root


def settings(**more):
    return {'base_url': root(), 'namespace': CAM.namespace, 'dispatcher': CAM.dispatcher, **more}


def needs_a_password_namespace():
    if not CAM.password_namespace:
        pytest.skip('no password namespace: set CAM_PASSWORD_NAMESPACE')


def sign_in_as_the_user(url, settings, terminal, root):
    """login.sign_in, with the test filling in Keycloak's form as the user would."""
    b = browser.Browser(EXECUTABLE, login.profile_folder(), url, hidden=True)
    try:
        session = b.call('Target.attachToTarget', {'targetId': b._target, 'flatten': True})['sessionId']
        deadline = time.monotonic() + 60
        filled = False
        while time.monotonic() < deadline:
            if not filled:
                script = FILL_KEYCLOAK % (json.dumps(CAM.user), json.dumps(CAM.password))
                result = b.call('Runtime.evaluate', {'expression': script, 'returnByValue': True}, session)
                filled = result.get('result', {}).get('value') is True
            passport = b.cookie('cam_passport', urlsplit(url).hostname)
            if passport:
                return passport
            time.sleep(0.5)
        raise AssertionError('no cam_passport after signing in')
    finally:
        b.close()


@pytest.fixture(autouse=True)
def signs_in_as_the_user(cam, tmp_path, monkeypatch):
    global CAM
    CAM = cam
    monkeypatch.setattr(browser, 'COMMON_ARGS', browser.COMMON_ARGS + cam.browser_args)
    login.forget_passports()
    monkeypatch.setattr(login, 'profile_folder', lambda: str(tmp_path / 'profile'))
    monkeypatch.setattr(login, 'sign_in', sign_in_as_the_user)
    yield
    login.forget_passports()


def active_user(session):
    return session.client.users.active_user(select='Name').name


def test_the_namespace_is_found_to_sign_in_in_the_browser():
    signer = login.Login(settings(), root(), False, FakeTerminal(present=False))

    assert signer.resolve().kind == 'browser'


def test_connects_through_the_browser_with_nothing_but_the_namespace():
    with tm1.connect(terminal=FakeTerminal(present=False), **settings()) as session:
        assert active_user(session) == f'CAMID("{CAM.namespace}:u:{CAM.user}")'


def test_without_a_namespace_cognos_lists_them_and_one_is_picked(monkeypatch):
    found = login.Login({'base_url': root(), 'dispatcher': CAM.dispatcher}, root(), False, FakeTerminal(present=False))
    dispatcher = found._dispatcher()
    options = discovery.namespaces(dispatcher)
    assert CAM.namespace in options

    terminal = FakeTerminal(answers=[str(options.index(CAM.namespace))])
    with tm1.connect(terminal=terminal, base_url=root(), dispatcher=CAM.dispatcher) as session:
        assert CAM.user in active_user(session)


def test_get_through_the_browser_from_the_command_line(tmp_path, monkeypatch):
    project = str(tmp_path / 'project')
    create_scaffold(project)
    with open(os.path.join(project, 'config', 'default', 'tm1cm.yaml'), 'w') as fp:
        yaml.safe_dump(util.get_tm1cm_config(), fp)
    with open(os.path.join(project, 'config', 'test', 'connect.yaml'), 'w') as fp:
        yaml.safe_dump({k: v for k, v in settings().items() if k != 'namespace'}, fp)
    with open(os.path.join(project, 'config', 'test', 'credentials.yaml'), 'w') as fp:
        yaml.safe_dump({'namespace': CAM.namespace}, fp)
    monkeypatch.chdir(tmp_path)
    try:
        assert cli.start(['--mode', 'get', '--path', project, '--environment', 'test']) == errors.OK
    finally:
        cli.close_logger()
    assert os.path.isdir(os.path.join(project, 'data'))


def test_the_hidden_try_gives_up_quickly_when_the_provider_needs_the_user(tmp_path):
    # Keycloak keeps its login session in a cookie that ends with the browser, so a new browser
    # needs the user again: the hidden window should notice in seconds, not wait out its timeout
    signer = login.Login(settings(), root(), False, FakeTerminal(present=False))
    url = discovery.browser_login_url(signer.resolve().dispatcher, CAM.namespace)
    started = time.monotonic()
    with pytest.raises(browser.SignInNeedsUser):
        browser.read_cookie(EXECUTABLE, str(tmp_path / 'fresh-profile'), url, window=False)
    assert time.monotonic() - started < browser.SILENT_TIMEOUT + 10


def test_a_password_namespace_asks_for_the_password_and_again_when_refused():
    needs_a_password_namespace()
    terminal = FakeTerminal(secrets=['not-the-password', CAM.password_password])
    with tm1.connect(terminal=terminal, base_url=root(), dispatcher=CAM.dispatcher,
                     namespace=CAM.password_namespace, user=CAM.password_user) as session:
        assert CAM.password_user in active_user(session)
    assert 'TM1 refused the login. Try again.' in terminal.said


def no_browser(monkeypatch):
    """The real sign-in, with a browser setting that names no browser: it fails at once."""
    monkeypatch.setattr(login, 'sign_in', REAL_SIGN_IN)


def test_without_a_browser_a_user_and_password_logs_in_instead(monkeypatch):
    needs_a_password_namespace()
    no_browser(monkeypatch)
    terminal = FakeTerminal(answers=['0'], secrets=[CAM.password_password])

    with tm1.connect(terminal=terminal, base_url=root(), dispatcher=CAM.dispatcher, auth='browser',
                     browser=NO_BROWSER, namespace=CAM.password_namespace,
                     user=CAM.password_user) as session:
        assert CAM.password_user in active_user(session)
    assert any(NO_BROWSER in caption and 'How do you want to log in?' in caption for caption in terminal.asked)


def test_without_a_browser_a_pasted_passport_logs_in(monkeypatch):
    signer = login.Login(settings(), root(), False, FakeTerminal(present=False))
    url = discovery.browser_login_url(signer.resolve().dispatcher, CAM.namespace)
    passport = sign_in_as_the_user(url, settings(), None, root())
    no_browser(monkeypatch)
    terminal = FakeTerminal(answers=['1'], secrets=[passport])

    with tm1.connect(terminal=terminal, **settings(browser=NO_BROWSER)) as session:
        assert active_user(session) == f'CAMID("{CAM.namespace}:u:{CAM.user}")'
    assert 'CAM passport: ' in terminal.asked


def test_without_a_browser_cancelling_ends_the_run_as_a_cancel(monkeypatch):
    no_browser(monkeypatch)

    with pytest.raises(errors.Cancelled) as raised:
        tm1.connect(terminal=FakeTerminal(answers=[None]), **settings(browser=NO_BROWSER))
    assert raised.value.exit_code == errors.CANCELLED


def test_without_a_terminal_a_browser_that_fails_says_what_to_set(monkeypatch):
    no_browser(monkeypatch)

    with pytest.raises(errors.LoginError) as raised:
        tm1.connect(terminal=FakeTerminal(present=False), **settings(browser=NO_BROWSER))
    assert 'cam_passport' in raised.value.hint


def test_the_shell_signs_in_to_a_cam_environment_before_its_spinner_starts(tmp_path, monkeypatch):
    from tm1cm import interactive

    project = str(tmp_path / 'project')
    create_scaffold(project)
    with open(os.path.join(project, 'config', 'default', 'tm1cm.yaml'), 'w') as fp:
        yaml.safe_dump(util.get_tm1cm_config(), fp)
    with open(os.path.join(project, 'config', 'test', 'connect.yaml'), 'w') as fp:
        yaml.safe_dump({k: v for k, v in settings().items() if k != 'namespace'}, fp)
    with open(os.path.join(project, 'config', 'test', 'credentials.yaml'), 'w') as fp:
        yaml.safe_dump({'namespace': CAM.namespace}, fp)
    shell = interactive.Interactive(project)
    remote = shell.apps['project.test']
    connected_at_spinner = []
    monkeypatch.setattr(interactive.Spinner, 'start', lambda self: connected_at_spinner.append(remote._connected))
    monkeypatch.setattr(interactive.Spinner, 'stop', lambda self: None)

    # From TM1 to the project: nothing is written to TM1, and nothing is done without do
    shell.onecmd('migrate project.test project.local')

    assert connected_at_spinner == [True]
    assert shell.migration is not None
    assert CAM.user in active_user(remote.session)
