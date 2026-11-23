import os
import shutil

import pytest
import yaml

from tests.tm1cm import util
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


def test_migrate_unknown_app_reports_error(shell, capsys):
    shell.onecmd('migrate nope.local target.local')

    assert 'Error occurred' in capsys.readouterr().out
    assert shell.migration is None
