"""The tm1cm command (tm1cm.__main__.start): its messages, exit codes and log, without a TM1."""
import os
import socket
import zipfile

import pytest
import yaml
from skipcheck_tm1 import errors as tm1_errors

from tests.tm1cm import fake_servers
from tm1cm import __main__ as cli
from tm1cm import errors
from tm1cm import scaffold
from tm1cm.tm1 import Tm1RestError

REAL_REPORT = errors.report


@pytest.fixture(autouse=True)
def logs(tmp_path, monkeypatch):
    """Runs in its own folder, so the log lands there; tm1cm's handlers are removed afterwards."""
    monkeypatch.chdir(tmp_path)
    # The real report: every run here has a log file, in the test's folder
    monkeypatch.setattr(errors, 'report', REAL_REPORT)
    yield
    cli.close_logger()


@pytest.fixture
def project(tmp_path):
    path = str(tmp_path / 'project')
    scaffold.create_scaffold(path)
    return path


def write(project, environment, name, settings):
    with open(os.path.join(project, 'config', environment, name + '.yaml'), 'w') as fp:
        yaml.safe_dump(settings, fp)


def run(capsys, *args):
    code = cli.start(list(args))
    return code, capsys.readouterr().err


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def test_scaffold_succeeds(tmp_path, capsys):
    code, err = run(capsys, '--mode', 'scaffold', '--path', str(tmp_path / 'new'))

    assert code == errors.OK
    assert os.path.isfile(tmp_path / 'new' / 'config' / 'default' / 'connect.yaml')


def test_scaffold_over_a_folder_is_a_config_error(tmp_path, capsys):
    code, err = run(capsys, '--mode', 'scaffold', '--path', str(tmp_path))

    assert code == errors.CONFIG
    assert 'already exists' in err and 'likely a bug' not in err


def test_a_folder_that_isnt_a_project(tmp_path, capsys):
    code, err = run(capsys, '--mode', 'get', '--path', str(tmp_path))

    assert code == errors.CONFIG
    assert 'is not a tm1cm project' in err and '--mode scaffold' in err


def test_an_environment_the_project_lacks_lists_those_it_has(project, capsys):
    code, err = run(capsys, '--mode', 'get', '--path', project, '--environment', 'staging')

    assert code == errors.CONFIG
    assert 'no environment staging' in err and 'prod, test' in err


def test_no_server_says_which_file_to_fix(project, capsys):
    code, err = run(capsys, '--mode', 'get', '--path', project, '--environment', 'test')

    assert code == errors.CONFIG
    assert 'No TM1 server is set.' in err and os.path.join('config', 'test') in err.replace('/', os.sep)


def test_invalid_yaml_names_the_file(project, capsys):
    with open(os.path.join(project, 'config', 'test', 'connect.yaml'), 'w') as fp:
        fp.write('base_url: [unclosed\n')

    code, err = run(capsys, '--mode', 'get', '--path', project, '--environment', 'test')

    assert code == errors.CONFIG
    assert 'connect.yaml is not valid YAML' in err


def test_tm1_out_of_reach(project, capsys):
    write(project, 'test', 'connect', {'base_url': f'http://127.0.0.1:{free_port()}'})
    write(project, 'test', 'credentials', {'user': 'admin', 'password': 'apple'})

    code, err = run(capsys, '--mode', 'get', '--path', project, '--environment', 'test')

    assert code == errors.UNREACHABLE
    assert "Couldn't reach TM1" in err


def test_a_refused_login_with_the_report_in_the_log_and_no_password_anywhere(project, tmp_path, capsys):
    server = fake_servers.FakeTm1(fake_servers.basic('admin', 'right-password'))
    try:
        write(project, 'test', 'connect', {'base_url': server.root})
        write(project, 'test', 'credentials', {'user': 'admin', 'password': 'wrong-password'})
        code, err = run(capsys, '--mode', 'get', '--path', project, '--environment', 'test')
    finally:
        server.stop()

    assert code == errors.LOGIN
    assert 'TM1 refused the login for admin' in err
    log = tmp_path / 'project.log'
    assert f'The full report is in {log}' in err
    text = log.read_text(encoding='utf-8')
    assert 'tm1cm error report' in text and 'LoginRejected' in text
    assert 'wrong-password' not in text + err


def test_an_unexpected_error_is_a_bug_and_debug_shows_its_traceback(project, monkeypatch, capsys):
    def broken(*args):
        raise KeyError('Dimensions')
    monkeypatch.setattr(cli, 'main', broken)

    code, err = run(capsys, '--mode', 'get', '--path', project)
    assert code == errors.BUG
    assert 'This is likely a bug.' in err and 'Traceback' not in err

    code, err = run(capsys, '--mode', 'get', '--path', project, '--debug')
    assert 'Traceback' in err


def test_ctrl_c_is_a_cancel(project, monkeypatch, capsys):
    def interrupted(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, 'main', interrupted)

    code, err = run(capsys, '--mode', 'get', '--path', project)

    assert code == errors.CANCELLED
    assert 'Cancelled.' in err


class FakeOperation:
    def __init__(self, name, error=None):
        self.name, self.error, self.done = name, error, False

    def __str__(self):
        return self.name

    def do(self, target):
        if self.error:
            raise self.error
        self.done = True


def test_failed_operations_are_summarised_after_doing_the_rest(project, monkeypatch, capsys):
    class Session:
        base_url = 'http://tm1:1'
    ops = [FakeOperation('UPDATE_CUBE: a'), FakeOperation('UPDATE_CUBE: b', Tm1RestError(400, 'Invalid dimension', 'PATCH', '/x')),
           FakeOperation('UPDATE_CUBE: c')]

    class Migration:
        def __init__(self, source, target):
            self.operations = ops
    monkeypatch.setattr(cli.tm1_client, 'connect', lambda **kwargs: Session())
    monkeypatch.setattr(cli, 'Migration', Migration)

    code, err = run(capsys, '--mode', 'put', '--path', project, '--environment', 'test')

    assert code == errors.TM1
    assert '1 of 3 operations failed' in err and 'UPDATE_CUBE: b: TM1 refused PATCH (400): Invalid dimension' in err
    assert ops[0].done and ops[2].done


def test_the_log_is_named_after_the_project_in_the_current_folder(tmp_path):
    assert cli.setup_logger(None, str(tmp_path / 'proj') + os.sep, False, stream=False) == str(tmp_path / 'proj.log')
    assert cli.setup_logger(str(tmp_path / 'my.log'), None, False, stream=False) == str(tmp_path / 'my.log')
    assert cli.setup_logger(None, None, False, stream=False).endswith('.log')
    assert cli.setup_logger(None, None, False, file=False, stream=False) is None


def test_a_log_that_cant_be_written_is_said_and_not_fatal(tmp_path, capsys):
    assert cli.setup_logger(str(tmp_path / 'no' / 'such' / 'folder' / 'x.log'), None, False, stream=False) is None
    assert 'could not write the log file' in capsys.readouterr().err


def test_scaffold_from_inside_a_sublime_package(tmp_path, monkeypatch):
    """When tm1cm runs from a .sublime-package (a zip), its templates are read from the zip."""
    include = os.path.join(os.path.dirname(scaffold.__file__), 'include')
    package = tmp_path / 'TM1.sublime-package'
    with zipfile.ZipFile(package, 'w') as zf:
        for name in ['.gitignore', 'connect.yaml', 'credentials.yaml', 'tm1cm.yaml']:
            zf.write(os.path.join(include, name), f'tm1cm/include/{name}')
    monkeypatch.setattr(scaffold, '__file__', os.path.join(str(package), 'tm1cm', 'scaffold.py'))

    scaffold.create_scaffold(str(tmp_path / 'proj'))

    with open(os.path.join(include, 'connect.yaml'), 'rb') as fp:
        connect = fp.read()
    for environment in ['default', 'test', 'prod']:
        with open(tmp_path / 'proj' / 'config' / environment / 'connect.yaml', 'rb') as fp:
            assert fp.read() == connect
    assert (tmp_path / 'proj' / '.gitignore').is_file()
    assert (tmp_path / 'proj' / 'config' / 'default' / 'tm1cm.yaml').is_file()


# --- --connect --------------------------------------------------------------------------------

@pytest.mark.parametrize('text, setting', [
    ('base_url=https://tm1:8010', ('base_url', 'https://tm1:8010')),
    ('verify=true', ('verify', True)),
    ('port=8010', ('port', 8010)),
    ('user=', ('user', '')),
    ('namespace= LDAP ', ('namespace', 'LDAP')),
    ('password=a=b:c', ('password', 'a=b:c')),
    ('session_context=[nightly]', ('session_context', '[nightly]')),
], ids=['text', 'bool', 'number', 'empty', 'spaces', '= and : in the value', 'YAML list kept as text'])
def test_a_connect_setting_reads_its_value_as_yaml_would(text, setting):
    assert cli.connect_setting(text) == setting


@pytest.mark.parametrize('text, message', [
    ('base_url', 'is not KEY=VALUE'),
    ('=x', 'is not KEY=VALUE'),
    ('pasword=apple', '"pasword" is not a connection setting'),
])
def test_a_connect_setting_that_isnt_one_is_refused_with_exit_code_2(tmp_path, capsys, text, message):
    with pytest.raises(SystemExit) as exited:
        cli.start(['--mode', 'get', '--path', str(tmp_path), '--connect', text])

    assert exited.value.code == errors.CONFIG
    err = capsys.readouterr().err
    assert message in err and 'apple' not in err


def test_connect_settings_win_over_the_files(project, capsys):
    server = fake_servers.FakeTm1(fake_servers.basic('admin', 'apple'))
    try:
        write(project, 'test', 'connect', {'base_url': f'http://127.0.0.1:{free_port()}'})
        write(project, 'test', 'credentials', {'user': 'someone', 'password': 'wrong-password'})
        code, err = run(capsys, '--mode', 'get', '--path', project, '--environment', 'test',
                        '--connect', f'base_url={server.root}', '-c', 'user=admin', '-c', 'password=apple')
    finally:
        server.stop()

    # Logged in with the overrides: the fake TM1 answers no more than that (its 404s end the run)
    assert server.logins == [fake_servers.basic('admin', 'apple')]
    assert 'apple' not in err


def test_connect_settings_reach_every_environment_of_the_shell(project):
    from tm1cm.interactive import Interactive

    write(project, 'test', 'connect', {'base_url': 'https://test:1'})
    shell = Interactive(project, {'base_url': 'https://other:2', 'verify': True})

    for name in ['project.test', 'project.prod']:
        assert shell.apps[name]._session_config['base_url'] == 'https://other:2'
        assert shell.apps[name]._session_config['verify'] is True


@pytest.mark.parametrize('error, code', [
    (tm1_errors.Tm1TransportError(tm1_errors.Tm1TransportError.Phase.CONNECT, True, 'GET', 'https://tm1:1/api/v1/x', None),
     errors.UNREACHABLE),
    (Tm1RestError(401, '', 'GET', '/x'), errors.LOGIN),
], ids=['unreachable', 'login refused'])
def test_tm1_gone_or_refusing_the_login_stops_the_run(project, monkeypatch, capsys, error, code):
    if code == errors.LOGIN:
        # As tm1.Rest raises it: TM1's refusal of the re-login, wrapped
        try:
            try:
                raise tm1_errors.Tm1ApiError.of_kind(401, tm1_errors.Tm1ErrorKind.CREDENTIAL_REJECTED, None, 'GET', '/x')
            except tm1_errors.Tm1ApiError as cause:
                raise error from cause
        except Tm1RestError as e:
            error = e

    class Session:
        base_url = 'http://tm1:1'
    ops = [FakeOperation('UPDATE_CUBE: a'), FakeOperation('UPDATE_CUBE: b', error), FakeOperation('UPDATE_CUBE: c')]

    class Migration:
        def __init__(self, source, target):
            self.operations = ops
    monkeypatch.setattr(cli.tm1_client, 'connect', lambda **kwargs: Session())
    monkeypatch.setattr(cli, 'Migration', Migration)

    got, err = run(capsys, '--mode', 'put', '--path', project, '--environment', 'test')

    assert got == code, err
    assert ops[0].done and not ops[2].done


@pytest.mark.parametrize('text, setting', [
    ('password=0777', ('password', '0777')),
    ('password=null', ('password', 'null')),
    ('password=1_000', ('password', '1_000')),
    ('user=on', ('user', 'on')),
    ('cam_passport=12:30:00', ('cam_passport', '12:30:00')),
    ('namespace=yes', ('namespace', 'yes')),
    ('port=8010', ('port', 8010)),
    ('ssl=false', ('ssl', False)),
    ('verify=/etc/ca.pem', ('verify', '/etc/ca.pem')),
])
def test_text_settings_are_kept_as_typed(text, setting):
    assert cli.connect_setting(text) == setting
