import os
import shutil
import tempfile

import pytest

from tests.tm1cm import util
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.migration import Migration

PROCESS = 'tm1cm.Core.Data.Generic View Export'


@pytest.fixture
def config():
    return util.get_tm1cm_config()


@pytest.fixture
def source(config):
    return LocalApplication(config, util.get_local_config())


def _empty_local(config):
    return LocalApplication(config, tempfile.mkdtemp(prefix='tm1cm_test_'))


def _contents(app):
    """Every object in an application, by scope: what a migration should make equal."""
    return {scope.type: dict(scope.get(scope.list(app), app)) for scope in app.scopes}


def _apply(migration, target):
    operations = migration.operations
    for operation in operations:
        operation.do(target)
    return operations


def test_migrate_to_empty_local_creates_everything(config, source):
    target = _empty_local(config)

    operations = _apply(Migration(source, target), target)

    assert operations
    assert all(operation.operation == 'UPDATE' for operation in operations)
    assert _contents(target) == _contents(source)


def test_migrate_identical_has_no_operations(config, source):
    target = _empty_local(config)
    _apply(Migration(source, target), target)

    assert Migration(source, target).operations == []


def test_migrate_deletes_objects_missing_from_source(config, source):
    target = _empty_local(config)
    _apply(Migration(source, target), target)

    process_path = os.path.join(source.path, source.processes.path)
    os.remove(os.path.join(process_path, PROCESS + source.processes.ext))

    operations = Migration(source, target).operations

    assert [(op.operation, op.scope.type, op.name) for op in operations] == [('DELETE', 'process', PROCESS)]


def test_migrate_rename_deletes_old_name(config, source):
    """A renamed object is created under its new name and deleted under its old one.

    Git reports a file whose content barely changed as a rename, a single diff with the old path
    (a_path) and the new (b_path), rather than as a delete and an add.
    """
    target = _empty_local(config)
    _apply(Migration(source, target), target)

    renamed = 'tm1cm.Core.Data.Generic View Export Renamed'
    process_path = os.path.join(source.path, source.processes.path)
    shutil.move(os.path.join(process_path, PROCESS + source.processes.ext), os.path.join(process_path, renamed + source.processes.ext))

    operations = Migration(source, target).operations

    assert sorted((op.operation, op.name) for op in operations if op.scope.type == 'process') == [('DELETE', PROCESS), ('UPDATE', renamed)]

    for operation in operations:
        operation.do(target)

    assert set(target.processes.list(target)) == set(source.processes.list(source))


@pytest.mark.requires_tm1
def test_put_new_objects_to_empty_tm1(config, source, tm1_connection):
    """Every object type, new to the target, in one migration: dependencies must be created first.

    Issue #10: promoting objects that don't exist on the target failed.
    """
    target = RemoteApplication(config, None, tm1_connection)
    _clean(target)
    try:
        _apply(Migration(source, target), target)

        # At least: creating a cube also creates any dimensions it names that the source lacks
        for scope in source.scopes:
            assert set(scope.list(source)) <= set(scope.list(target)), scope.type
    finally:
        _clean(target)


def _clean(app):
    for scope in [app.applications, app.chores, app.processes, app.views, app.rules, app.cubes, app.subsets, app.hierarchies, app.dimensions]:
        for name in scope.list(app):
            scope.delete(name, app)
