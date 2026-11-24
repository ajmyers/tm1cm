"""tm1cm.files: get and put of the objects named by files, whatever tm1cm.yaml's filters select.

The unit tests stand in for TM1's lists of objects; the ones marked requires_tm1 get and put
against TM1 in Docker."""
import os
import shutil

import pytest
import yaml

from tests.tm1cm import util
from tm1cm import errors
from tm1cm import files
from tm1cm.__main__ import main
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.scaffold import create_scaffold

PROCESS = 'data/process/tm1cm.Core.Data.Generic View Export.process'
HIERARCHY = 'data/hierarchy/tm1cmTestCube01_Dim1/tm1cmTestCube01_Dim1.hierarchy'
SUBSET = 'data/subset/tm1cmTestCube01_Dim1/tm1cmTestCube01_Dim1/tm1cmTestSubset.subset'
VIEW_DATA = 'data/view_data/tm1cmTestCube01/tm1cmTestCube01_View1.view_data'
CUBE = 'data/cube/tm1cmTestCube01.cube'
DIMENSION = 'data/dimension/tm1cmTestCube01_Dim1.dimension'
REFERENCE = 'data/application/tm1cmTest/ProcessReferenceTest.application'
DOCUMENT = 'data/application/tm1cmTest/subfolder/subfolder2/BinaryReferenceTest.xlsx'


def excluding_everything():
    """Filters that select no object at all: what the files name is got or put regardless."""
    config = util.get_tm1cm_config()
    for scope in ['process', 'cube', 'rule', 'cube_view', 'cube_view_data', 'dimension', 'dimension_hierarchy',
                  'dimension_hierarchy_subset', 'application', 'chore']:
        config['include_' + scope] = ''
        config['exclude_' + scope] = '*'
    return config


class TM1Has:
    """Stands in for files.Names: the remote side has ``remote`` (by type), the local side what's on disk."""

    def __init__(self, **remote):
        self.remote = remote

    def of(self, scope, app):
        if isinstance(app, RemoteApplication):
            return self.remote.get(scope.type, [])
        return scope._list_local(app)


@pytest.fixture
def project():
    path = util.get_local_config()
    config = excluding_everything()
    return LocalApplication(config, path), RemoteApplication(config, session_config={'base_url': 'http://tm1:1'})


def described(ops):
    return [str(op) for op in ops]


def test_put_updates_the_objects_of_the_files_whatever_the_filters(project):
    local, remote = project

    ops = files.operations('put', local, remote, [PROCESS, HIERARCHY], TM1Has())

    assert described(ops) == ['UPDATE_PROCESS: tm1cm.Core.Data.Generic View Export',
                              'UPDATE_HIERARCHY: tm1cmTestCube01_Dim1:tm1cmTestCube01_Dim1']
    assert all(op.target is remote for op in ops)


def test_put_deletes_from_tm1_the_object_of_a_file_thats_gone(project):
    local, remote = project
    os.remove(os.path.join(local.path, PROCESS))

    ops = files.operations('put', local, remote, [PROCESS], TM1Has(process=['tm1cm.Core.Data.Generic View Export']))

    assert described(ops) == ['DELETE_PROCESS: tm1cm.Core.Data.Generic View Export']


def test_a_file_neither_side_has_is_skipped(project):
    local, remote = project

    assert files.operations('put', local, remote, ['data/process/Nothing.process'], TM1Has()) == []
    assert files.operations('get', local, remote, ['data/process/Nothing.process'], TM1Has()) == []


def test_get_writes_what_tm1_has_and_deletes_the_file_of_what_it_hasnt(project):
    local, remote = project

    ops = files.operations('get', local, remote, [PROCESS, CUBE], TM1Has(cube=['tm1cmTestCube01']))

    assert described(ops) == ['UPDATE_CUBE: tm1cmTestCube01', 'DELETE_PROCESS: tm1cm.Core.Data.Generic View Export']
    assert all(op.target is local for op in ops)
    assert ops[0].scope.app is remote


def test_tm1s_names_ignore_case(project):
    local, remote = project

    ops = files.operations('get', local, remote, [CUBE], TM1Has(cube=['TM1CMTESTCUBE01']))

    assert described(ops) == ['UPDATE_CUBE: tm1cmTestCube01']


def test_names_of_several_parts(project):
    local, remote = project

    ops = files.operations('put', local, remote, [SUBSET, VIEW_DATA], TM1Has())

    assert {op.name for op in ops} == {('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset'),
                                       ('tm1cmTestCube01', 'tm1cmTestCube01_View1')}


def test_applications_references_and_documents(project):
    local, remote = project

    ops = files.operations('put', local, remote, [REFERENCE, DOCUMENT], TM1Has())

    assert {op.name for op in ops} == {('tm1cmTest', 'ProcessReferenceTest', 'process'),
                                       ('tm1cmTest', 'subfolder', 'subfolder2', 'BinaryReferenceTest.xlsx', 'blob')}


def test_a_deleted_reference_is_found_in_tm1(project):
    local, remote = project
    os.remove(os.path.join(local.path, REFERENCE))

    ops = files.operations('put', local, remote, [REFERENCE], TM1Has(application=[('tm1cmTest', 'ProcessReferenceTest', 'process')]))

    assert described(ops) == ['DELETE_APPLICATION: tm1cmTest/ProcessReferenceTest']


def test_dependencies_first_and_each_object_once(project):
    local, remote = project

    ops = files.operations('put', local, remote, [CUBE, DIMENSION, CUBE], TM1Has())

    assert described(ops) == ['UPDATE_DIMENSION: tm1cmTestCube01_Dim1', 'UPDATE_CUBE: tm1cmTestCube01']


def test_paths_absolute_from_the_project_or_from_the_current_folder(project, monkeypatch):
    local, remote = project
    absolute = os.path.join(local.path, *PROCESS.split('/'))

    assert files.resolve(absolute, local.path) == absolute
    assert files.resolve(PROCESS, local.path) == absolute
    monkeypatch.chdir(os.path.join(local.path, 'data'))
    assert files.resolve(os.path.join('process', os.path.basename(absolute)), local.path) == absolute
    # Gone from both: taken from the project, as git prints the paths of deleted files
    assert files.resolve('data/process/Gone.process', local.path) == os.path.join(local.path, 'data', 'process', 'Gone.process')


@pytest.mark.parametrize('path, message', [
    ('/elsewhere/x.process', 'is not in the project'),
    ('config/default/connect.yaml', 'is not an object file'),
    ('data/process/Load.txt', 'is not a process file: they end in .process'),
    ('data/hierarchy/Region.hierarchy', 'they are data/hierarchy/<name>/<name>.hierarchy'),
])
def test_paths_that_arent_object_files_are_refused(project, path, message):
    local, _ = project

    with pytest.raises(errors.ConfigError, match=message):
        files.check([path], local)


def test_files_are_checked_before_connecting(tmp_path):
    path = str(tmp_path / 'p')
    create_scaffold(path)

    # No server is set either: the bad file is what's said
    with pytest.raises(errors.ConfigError, match='is not a process file'):
        main('put', path, 'test', paths=['data/process/Load.txt'])


def test_files_are_only_for_get_and_put(tmp_path):
    with pytest.raises(errors.ConfigError, match='Files are for get and put'):
        main('scaffold', str(tmp_path / 'p'), None, paths=[PROCESS])


def test_the_operations_carry_each_object_as_it_is(project, tmp_path):
    # Done to another project rather than TM1: the same get from one side and update of the other
    local, remote = project
    other = LocalApplication(local.config, str(tmp_path / 'other'))
    ops = files.operations('put', local, remote, [PROCESS, HIERARCHY, SUBSET, REFERENCE, DOCUMENT], TM1Has())

    for op in ops:
        op.do(other)

    for op in ops:
        assert dict(op.scope.get([op.name], other)) == dict(op.scope.get([op.name], local)), str(op)


# --- Against TM1 ----------------------------------------------------------------------------

def _project(path, connection, config):
    create_scaffold(path)
    with open(os.path.join(path, 'config', 'default', 'tm1cm.yaml'), 'w') as fp:
        yaml.safe_dump(config, fp)
    with open(os.path.join(path, 'config', 'test', 'connect.yaml'), 'w') as fp:
        yaml.safe_dump({'base_url': connection['base_url']}, fp)
    with open(os.path.join(path, 'config', 'test', 'credentials.yaml'), 'w') as fp:
        yaml.safe_dump({'user': connection['user'], 'password': connection['password']}, fp)
    return path


@pytest.fixture
def tm1(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    names = ['tm1cm.Core.Data.Generic View Export', 'tm1cm.Core.Data.Generic View Import']

    def clean():
        for name in names:
            if name in app.processes._list_remote(app):
                app.processes.delete(name, app)
    clean()
    yield app
    clean()


@pytest.mark.requires_tm1
def test_put_get_and_delete_one_process_the_filters_exclude(tmp_path, tm1_connection, tm1):
    config = excluding_everything()
    pushed = _project(str(tmp_path / 'pushed'), tm1_connection, config)
    shutil.copytree(os.path.join(util.get_local_config(), 'data'), os.path.join(pushed, 'data'), dirs_exist_ok=True)

    main('put', pushed, 'test', paths=[PROCESS])

    assert tm1.processes._list_remote(tm1) == ['tm1cm.Core.Data.Generic View Export']

    fetched = _project(str(tmp_path / 'fetched'), tm1_connection, config)
    main('get', fetched, 'test', paths=[PROCESS])

    local = LocalApplication(config, fetched)
    assert local.processes._list_local(local) == ['tm1cm.Core.Data.Generic View Export']
    assert dict(local.processes.get([PROCESS_NAME], local)) == dict(LocalApplication(config, pushed).processes.get([PROCESS_NAME]))

    os.remove(os.path.join(pushed, PROCESS))
    main('put', pushed, 'test', paths=[PROCESS])

    assert tm1.processes._list_remote(tm1) == []

    # The same file got again: TM1 hasn't got the process, so the file goes
    main('get', fetched, 'test', paths=[PROCESS])
    assert not os.path.exists(os.path.join(fetched, PROCESS))


PROCESS_NAME = 'tm1cm.Core.Data.Generic View Export'
