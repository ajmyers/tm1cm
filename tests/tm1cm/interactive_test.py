import os
import shutil

import pytest
import yaml

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm import tm1 as tm1_client
from tm1cm.application import LocalApplication
from tm1cm.interactive import Interactive
from tm1cm.scaffold import create_scaffold


def _project(path, with_data):
    """A scaffolded project, filtered to the test objects, holding them or empty."""
    create_scaffold(path)
    with open(os.path.join(path, 'config', 'default', 'tm1cm.yaml'), 'w') as fp:
        yaml.safe_dump(util.get_tm1cm_config(), fp)
    if with_data:
        shutil.copytree(os.path.join(util.get_local_config(), 'data'), os.path.join(path, 'data'), dirs_exist_ok=True)
    return path


@pytest.fixture
def shell(tmp_path, monkeypatch):
    """A shell over a folder of two projects: 'source', holding the test objects, and 'target', empty."""
    _project(str(tmp_path / 'source'), with_data=True)
    _project(str(tmp_path / 'target'), with_data=False)
    monkeypatch.setattr('builtins.input', lambda prompt='': 'y')
    shell = Interactive(str(tmp_path))
    shell.migrate = lambda: shell.onecmd('migrate source.local target.local')
    return shell


def test_finds_every_project_and_environment(shell, capsys):
    shell.onecmd('ls apps')

    assert set(capsys.readouterr().out.split()) == {'source.local', 'source.test', 'source.prod', 'target.local', 'target.test', 'target.prod'}


def test_finds_environments_of_one_project(tmp_path):
    shell = Interactive(_project(str(tmp_path / 'one'), with_data=False))

    assert set(shell.apps) == {'one.local', 'one.test', 'one.prod'}


def test_migrate_lists_operations_unstaged(shell, capsys):
    shell.migrate()
    shell.onecmd('ls')

    out = capsys.readouterr().out
    assert shell.operations
    assert shell.stage == []
    assert 'UPDATE_PROCESS: tm1cm.Core.Data.Generic View Export' in out


def test_add_and_rm_stage_by_pattern(shell):
    shell.migrate()

    shell.onecmd('add UPDATE_PROCESS:*')
    assert shell.stage and all(op.scope.type == 'process' for op in shell.stage)

    shell.onecmd('add UPDATE_CUBE:*')
    assert {op.scope.type for op in shell.stage} == {'process', 'cube'}
    assert shell.stage == sorted(shell.stage, key=lambda op: op.sort_order)

    shell.onecmd('rm UPDATE_PROCESS:*')
    assert {op.scope.type for op in shell.stage} == {'cube'}


def test_add_twice_stages_once(shell):
    shell.migrate()

    shell.onecmd('add UPDATE_PROCESS:*')
    staged = len(shell.stage)
    shell.onecmd('add UPDATE_PROCESS:*')

    assert len(shell.stage) == staged


def test_do_applies_only_staged(shell, tmp_path):
    shell.migrate()
    shell.onecmd('add UPDATE_PROCESS:*')
    shell.onecmd('do')

    target = LocalApplication(util.get_tm1cm_config(), str(tmp_path / 'target'))
    source = LocalApplication(util.get_tm1cm_config(), str(tmp_path / 'source'))
    assert target.processes.list(target) == source.processes.list(source)
    assert target.cubes.list(target) == []


def test_do_all_applies_everything(shell, tmp_path):
    shell.migrate()
    shell.onecmd('do all')

    target = LocalApplication(util.get_tm1cm_config(), str(tmp_path / 'target'))
    source = LocalApplication(util.get_tm1cm_config(), str(tmp_path / 'source'))
    for scope in source.scopes:
        assert scope.list(target) == scope.list(source), scope.type


def test_commands_before_migrate_say_so(shell, capsys):
    shell.onecmd('add *')
    shell.onecmd('rm *')

    assert capsys.readouterr().out.count('no migration defined') == 2


BACKUP = 'tm1cm.Test.Backup'
# What the backup process leaves behind, so the test can tell it ran
BACKUP_MARK = 'tm1cmBackupRan'


def _remote_project(path, connection, backup):
    """A project whose 'test' environment is the TM1 container, with a backup process configured."""
    _project(path, with_data=True)
    config = {**util.get_tm1cm_config(), 'backup_process': BACKUP, 'backup_on_migrate': backup['on'], 'backup_allow_override': backup['override']}
    with open(os.path.join(path, 'config', 'default', 'tm1cm.yaml'), 'w') as fp:
        yaml.safe_dump(config, fp)
    with open(os.path.join(path, 'config', 'test', 'connect.yaml'), 'w') as fp:
        yaml.safe_dump({'base_url': connection['base_url']}, fp)
    with open(os.path.join(path, 'config', 'test', 'credentials.yaml'), 'w') as fp:
        yaml.safe_dump({'user': connection['user'], 'password': connection['password']}, fp)
    return path


@pytest.fixture
def tm1(tm1_connection):
    session = tm1_client.connect(**tm1_connection)
    tm1_objects.delete_process(session, BACKUP)
    tm1_objects.create_process(session, BACKUP, prolog=f"DimensionCreate('{BACKUP_MARK}');")
    yield session
    tm1_objects.delete_dimension(session, BACKUP_MARK)
    tm1_objects.delete_process(session, BACKUP)
    session.logout()


@pytest.mark.requires_tm1
@pytest.mark.parametrize('backup, answers, ran', [
    ({'on': True, 'override': False}, ['y'], True),
    ({'on': False, 'override': False}, ['y'], False),
    ({'on': False, 'override': True}, ['y', 'y'], True),
    ({'on': True, 'override': True}, ['y', 'n'], False),
], ids=['configured on', 'configured off', 'override to on', 'override to off'])
def test_do_runs_backup_process_first(tmp_path, monkeypatch, tm1_connection, tm1, backup, answers, ran):
    project = _remote_project(str(tmp_path / 'proj'), tm1_connection, backup)
    replies = iter(answers)
    monkeypatch.setattr('builtins.input', lambda prompt='': next(replies))
    shell = Interactive(project)

    shell.onecmd('migrate proj.local proj.test')
    shell.onecmd('add UPDATE_PROCESS:*')
    shell.onecmd('do')

    assert tm1_objects.exists(tm1, f"/api/v1/Dimensions('{BACKUP_MARK}')") == ran
    assert 'tm1cm.Core.Data.Generic View Export' in tm1_objects.process_names(tm1)
    for name in tm1_objects.process_names(tm1):
        if name.startswith('tm1cm.Core'):
            tm1_objects.delete_process(tm1, name)


def test_migrate_unknown_app_reports_error(shell, capsys):
    shell.onecmd('migrate nope.local target.local')

    out = capsys.readouterr().out
    assert 'tm1cm: There is no app nope.local.' in out
    assert 'source.local' in out
    assert shell.migration is None


def test_the_shell_ends_at_the_end_of_its_input(tmp_path):
    import subprocess
    import sys

    from tm1cm.scaffold import create_scaffold

    project = str(tmp_path / 'project')
    create_scaffold(project)
    for commands in ['ls apps\n', 'ls apps\nexit\n', 'quit\n']:
        done = subprocess.run([sys.executable, '-m', 'tm1cm', '--log', str(tmp_path / 'tm1cm.log')], input=commands, cwd=project,
                              capture_output=True, text=True, timeout=60)

        assert done.returncode == 0, commands
        assert 'Unknown syntax' not in done.stdout
