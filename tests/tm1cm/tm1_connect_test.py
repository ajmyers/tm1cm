"""tm1cm.tm1.connect: logging in over HTTP to a fake TM1, trying again where a person can, and
saying what went wrong where they can't. The browser test signs in for real, in a hidden window,
at a fake Cognos login."""
import socket

import pytest

from tests.tm1cm import fake_servers
from tests.tm1cm.browser_test import needs_browser
from tests.tm1cm.login_test import FakeTerminal
from tm1cm import errors
from tm1cm import login
from tm1cm import tm1


@pytest.fixture(autouse=True)
def fresh_passports():
    login.forget_passports()
    yield
    login.forget_passports()


@pytest.fixture
def tm1_basic():
    server = fake_servers.FakeTm1(fake_servers.basic('admin', 'apple'))
    yield server
    server.stop()


def test_logs_in_with_the_password_in_the_file(tm1_basic):
    with tm1.connect(terminal=FakeTerminal(present=False), base_url=tm1_basic.root, user='admin', password='apple') as session:
        assert session.version == fake_servers.VERSION
    assert errors._servers[tm1_basic.root] == fake_servers.VERSION


def test_a_typed_password_tm1_refuses_is_asked_for_again(tm1_basic):
    terminal = FakeTerminal(secrets=['wrong', 'apple'])

    with tm1.connect(terminal=terminal, base_url=tm1_basic.root, auth='basic', user='admin'):
        pass

    # The empty password first, as 1.0 sent it, then what was typed
    assert tm1_basic.logins == [fake_servers.basic('admin', ''), fake_servers.basic('admin', 'wrong'), fake_servers.basic('admin', 'apple')]
    assert 'TM1 refused the login. Try again.' in terminal.said


def test_tm1s_own_security_is_found_and_asked_for(tm1_basic):
    terminal = FakeTerminal(answers=['admin'], secrets=['apple'])

    with tm1.connect(terminal=terminal, base_url=tm1_basic.root, user='', password='', namespace=''):
        pass

    assert tm1_basic.logins == [fake_servers.basic('admin', 'apple')]


def test_a_refused_password_from_the_file_says_what_to_check(tm1_basic):
    with pytest.raises(errors.LoginRejected) as raised:
        tm1.connect(terminal=FakeTerminal(present=False), base_url=tm1_basic.root, user='admin', password='pear')

    assert raised.value.exit_code == errors.LOGIN
    assert 'credentials.yaml' in raised.value.hint
    assert len(tm1_basic.logins) == 1


def test_a_server_that_isnt_there_is_unreachable():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]

    with pytest.raises(errors.ServerUnreachable) as raised:
        tm1.connect(terminal=FakeTerminal(present=False), base_url=f'http://127.0.0.1:{port}', user='admin', password='apple')
    assert raised.value.exit_code == errors.UNREACHABLE
    assert 'connect.yaml' in raised.value.hint


@needs_browser
def test_signs_in_through_the_browser_and_logs_in_with_the_passport(tmp_path, monkeypatch):
    cognos = fake_servers.LoginServer()
    tm1_cam = fake_servers.FakeTm1('CAMPassport MTsxMDE6passport', cam=True)
    monkeypatch.setattr(login, 'profile_folder', lambda: str(tmp_path / 'profile'))
    try:
        dispatcher = cognos.url.rstrip('/') + '/v1/disp'
        # No terminal: only the hidden window, which is enough when the sign-in needs no one
        with tm1.connect(terminal=FakeTerminal(present=False), base_url=tm1_cam.root, auth='browser', namespace='OIDC',
                         dispatcher=dispatcher):
            pass
    finally:
        cognos.stop()
        tm1_cam.stop()
    assert tm1_cam.logins == ['CAMPassport MTsxMDE6passport']
    assert errors.redact('passport MTsxMDE6passport') == 'passport ***'
