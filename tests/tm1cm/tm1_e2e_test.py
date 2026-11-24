"""#29's features end to end against TM1 in Docker: logging in to TM1's own security, the
command's exit codes and messages, --connect, and get and put of chosen files, the
git diff pipeline included. The CAM and browser paths are in live_cam_test."""
import os
import shutil
import subprocess

import pytest
import yaml

from tests.tm1cm import util
from tests.tm1cm.files_test import CUBE
from tests.tm1cm.files_test import DOCUMENT
from tests.tm1cm.files_test import HIERARCHY
from tests.tm1cm.files_test import PROCESS
from tests.tm1cm.files_test import REFERENCE
from tests.tm1cm.files_test import SUBSET
from tests.tm1cm.files_test import excluding_everything
from tests.tm1cm.login_test import FakeTerminal
from tests.tm1cm.main_test import _clean
from tm1cm import __main__ as cli
from tm1cm import errors
from tm1cm import login
from tm1cm import tm1
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.scaffold import create_scaffold

pytestmark = pytest.mark.requires_tm1

REAL_REPORT = errors.report
DIMENSIONS = ['data/dimension/tm1cmTestCube01_Dim1.dimension', 'data/dimension/tm1cmTestCube01_Dim2.dimension']
HIERARCHIES = [HIERARCHY, 'data/hierarchy/tm1cmTestCube01_Dim2/tm1cmTestCube01_Dim2.hierarchy']
OTHER_PROCESS = 'data/process/tm1cm.Core.Data.Generic View Import.process'


@pytest.fixture(autouse=True)
def runs_in_its_own_folder(tmp_path, monkeypatch, capsys):
    """The log lands in the test's folder, with the real error report; passports are forgotten.
    capsys first, so the captured stderr tm1cm logs to outlasts the other fixtures' teardowns."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(errors, 'report', REAL_REPORT)
    login.forget_passports()
    yield
    cli.close_logger()
    login.forget_passports()


@pytest.fixture
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    _clean(app)
    yield app
    # tm1cm's log handlers hold the test's captured stderr, closed by now
    cli.close_logger()
    _clean(app)


def project(path, config, connect=None, credentials=None, data=True):
    create_scaffold(path)
    for name, settings in [('tm1cm', config), ('connect', connect), ('credentials', credentials)]:
        if settings is not None:
            folder = 'default' if name == 'tm1cm' else 'test'
            with open(os.path.join(path, 'config', folder, name + '.yaml'), 'w') as fp:
                yaml.safe_dump(settings, fp)
    if data:
        shutil.copytree(os.path.join(util.get_local_config(), 'data'), os.path.join(path, 'data'), dirs_exist_ok=True)
    return path


def connected(path, connection, config):
    return project(path, config, {'base_url': connection['base_url']},
                   {'user': connection['user'], 'password': connection['password']})


def run(capsys, *args):
    code = cli.start(list(args))
    return code, capsys.readouterr().err


def log_text(folder):
    logs = [name for name in os.listdir(folder) if name.endswith('.log')]
    return ''.join(open(os.path.join(folder, name), encoding='utf-8').read() for name in logs)


# --- Logging in to TM1's own security ----------------------------------------------------------

def test_tm1s_own_security_is_found_and_a_refused_password_asked_for_again(tm1_connection):
    terminal = FakeTerminal(answers=[tm1_connection['user']], secrets=['not-the-password', tm1_connection['password']])

    with tm1.connect(terminal=terminal, base_url=tm1_connection['base_url']) as session:
        active = session.rest.GET('/api/v1/ActiveUser?$select=Name').json()['Name']

    assert active.lower() == tm1_connection['user'].lower()
    assert 'TM1 refused the login. Try again.' in terminal.said
    assert terminal.asked[0].startswith('TM1 user for')


def test_a_password_tm1_refuses_ends_the_run_with_the_login_code_and_no_password_in_sight(tmp_path, tm1_connection, capsys):
    path = project(str(tmp_path / 'project'), util.get_tm1cm_config(), {'base_url': tm1_connection['base_url']},
                   {'user': tm1_connection['user'], 'password': 'refused-by-tm1'})

    code, err = run(capsys, '--mode', 'get', '--path', path, '--environment', 'test')

    assert code == errors.LOGIN
    assert 'credentials.yaml' in err
    log = log_text(str(tmp_path))
    assert 'Traceback' in log and 'refused-by-tm1' not in log and 'refused-by-tm1' not in err


# --- --connect ---------------------------------------------------------------------------------

def test_get_with_every_setting_on_the_command_line(tmp_path, tm1_connection, remote, capsys):
    config = util.get_tm1cm_config()
    pushed = connected(str(tmp_path / 'pushed'), tm1_connection, config)
    cli.main('put', pushed, 'test')

    # No server and no user in the project at all: the command line gives them
    fetched = project(str(tmp_path / 'fetched'), config, data=False)
    code, err = run(capsys, '--mode', 'get', '--path', fetched, '--environment', 'test',
                    '-c', f'base_url={tm1_connection["base_url"]}', '-c', f'user={tm1_connection["user"]}',
                    '--connect', f'password={tm1_connection["password"]}')

    assert code == errors.OK, err
    source, result = LocalApplication(config, pushed), LocalApplication(config, fetched)
    names = source.processes.list(source)
    assert names and dict(source.processes.get(names)) == dict(result.processes.get(names, result))
    if tm1_connection['password']:
        assert tm1_connection['password'] not in err + log_text(str(tmp_path))


# --- Chosen files ------------------------------------------------------------------------------

def test_put_a_cube_its_dimensions_a_subset_and_applications_the_filters_exclude(tmp_path, tm1_connection, remote):
    config = excluding_everything()
    path = connected(str(tmp_path / 'project'), tm1_connection, config)

    chosen = [REFERENCE, DOCUMENT, SUBSET, CUBE, *HIERARCHIES, *DIMENSIONS, PROCESS]
    # In no particular order: dependencies go first
    cli.main('put', path, 'test', paths=chosen)

    assert remote.cubes.list(remote) == ['tm1cmTestCube01']
    assert sorted(remote.dimensions.list(remote)) == ['tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim2']
    assert remote.processes.list(remote) == ['tm1cm.Core.Data.Generic View Export']
    assert remote.cubes.list(remote) == ['tm1cmTestCube01']
    assert len(remote.applications.list(remote)) == 2

    # Got back into an empty project, each file is what was put
    fetched = connected(str(tmp_path / 'fetched'), tm1_connection, config)
    shutil.rmtree(os.path.join(fetched, 'data'))
    cli.main('get', fetched, 'test', paths=chosen)
    assert sorted(os.path.relpath(f, fetched).replace(os.sep, '/') for f in data_files(fetched)) == sorted(chosen)
    source, result = LocalApplication(config, path), LocalApplication(config, fetched)
    for scope in result.scopes:
        names = scope._list_local(result)
        assert dict(scope.get(names, result)) == dict(scope.get(names, source)), scope.type


def data_files(project):
    return [os.path.join(folder, name) for folder, _, names in os.walk(os.path.join(project, 'data')) for name in names]


def content(project, name):
    """A file's content: YAML parsed, so key order doesn't count; anything else as bytes."""
    with open(os.path.join(project, *name.split('/')), 'rb') as fp:
        data = fp.read()
    if name.endswith('.xlsx'):
        return data
    if name.endswith(('.process', '.rule')):
        return data.decode('utf-8')
    # An empty dimension file (None) and the {} a get writes for it both say nothing
    return yaml.safe_load(data) or {}


def test_get_of_one_file_leaves_the_rest_of_data_alone(tmp_path, tm1_connection, remote):
    config = util.get_tm1cm_config()
    pushed = connected(str(tmp_path / 'pushed'), tm1_connection, config)
    cli.main('put', pushed, 'test')
    # The project's hierarchy now differs from TM1's, and a subset file is gone
    fetched = connected(str(tmp_path / 'fetched'), tm1_connection, excluding_everything())
    os.remove(os.path.join(fetched, *SUBSET.split('/')))
    with open(os.path.join(fetched, *HIERARCHY.split('/')), 'w') as fp:
        fp.write('Elements: []\n')
    before = snapshot(fetched)

    cli.main('get', fetched, 'test', paths=[HIERARCHY])

    after = snapshot(fetched)
    changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    assert changed == [os.path.join(*HIERARCHY.split('/'))]
    assert content(fetched, HIERARCHY) == content(pushed, HIERARCHY)
    assert content(fetched, HIERARCHY)['Elements'] != []


def snapshot(path):
    files = {}
    for folder, _, names in os.walk(os.path.join(path, 'data')):
        for name in names:
            full = os.path.join(folder, name)
            with open(full, 'rb') as fp:
                files[os.path.relpath(full, path)] = fp.read().decode('utf-8', 'replace')
    return files


def test_a_put_tm1_refuses_lists_the_failure_after_the_rest_and_exits_5(tmp_path, tm1_connection, remote, capsys):
    path = connected(str(tmp_path / 'project'), tm1_connection, excluding_everything())
    # The subset's dimension isn't on TM1, and isn't among the files: TM1 refuses it
    code, err = run(capsys, '--mode', 'put', '--path', path, '--environment', 'test', SUBSET, PROCESS)

    assert code == errors.TM1, err
    assert '1 of 2 operations failed' in err and 'tm1cmTestSubset' in err
    # The rest was done
    assert remote.processes.list(remote) == ['tm1cm.Core.Data.Generic View Export']


def test_the_files_a_commit_changed_put_exactly_that_commit(tmp_path, tm1_connection, remote, capsys):
    config = excluding_everything()
    path = connected(str(tmp_path / 'project'), tm1_connection, config)
    cli.main('put', path, 'test', paths=[PROCESS, OTHER_PROCESS, *DIMENSIONS, *HIERARCHIES, SUBSET])

    def git(*args):
        return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@t', *args], cwd=path, check=True,
                              capture_output=True, text=True).stdout

    git('init', '-q')
    git('add', '-A')
    git('commit', '-q', '-m', 'before')
    os.remove(os.path.join(path, *OTHER_PROCESS.split('/')))
    subset = os.path.join(path, *SUBSET.split('/'))
    with open(subset, encoding='utf-8') as fp:
        body = yaml.safe_load(fp)
    body['Expression'] = '{ [tm1cmTestCube01_Dim1].[tm1cmTestCube01_Dim1].[Test Element 1] }'
    with open(subset, 'w', encoding='utf-8') as fp:
        yaml.safe_dump(body, fp)
    git('add', '-A')
    git('commit', '-q', '-m', 'after')

    # git diff -z --name-only HEAD~1 -- data | xargs -0 tm1cm --mode put ..., from the project
    changed = [name for name in git('diff', '-z', '--name-only', 'HEAD~1', '--', 'data').split('\0') if name]
    assert sorted(changed) == sorted([OTHER_PROCESS, SUBSET])
    os.chdir(path)
    code, err = run(capsys, '--mode', 'put', '--path', path, '--environment', 'test', *changed)

    assert code == errors.OK, err
    assert remote.processes.list(remote) == ['tm1cm.Core.Data.Generic View Export']
    fetched = connected(str(tmp_path / 'fetched'), tm1_connection, config)
    cli.main('get', fetched, 'test', paths=[SUBSET])
    assert content(fetched, SUBSET) == content(path, SUBSET)
    assert content(fetched, SUBSET)['Expression'] == body['Expression']
