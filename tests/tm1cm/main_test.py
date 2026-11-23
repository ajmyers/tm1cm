import os
import shutil

import pytest
import yaml

from tests.tm1cm import util
from tm1cm.__main__ import main
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.scaffold import create_scaffold


def test_scaffold_creates_project(tmp_path):
    project = str(tmp_path / 'project')

    main('scaffold', project, None)

    for path in ['.gitignore', 'data', 'config/default/connect.yaml', 'config/default/credentials.yaml',
                 'config/default/tm1cm.yaml', 'config/test/connect.yaml', 'config/prod/connect.yaml']:
        assert os.path.exists(os.path.join(project, path)), path


def test_scaffold_refuses_existing_path(tmp_path):
    with pytest.raises(ValueError):
        create_scaffold(str(tmp_path))


def _project(path, connection):
    """A scaffolded project for the test environment, filtered to the test objects."""
    create_scaffold(path)
    with open(os.path.join(path, 'config', 'default', 'tm1cm.yaml'), 'w') as fp:
        yaml.safe_dump(util.get_tm1cm_config(), fp)
    with open(os.path.join(path, 'config', 'test', 'connect.yaml'), 'w') as fp:
        yaml.safe_dump({'base_url': connection['base_url']}, fp)
    with open(os.path.join(path, 'config', 'test', 'credentials.yaml'), 'w') as fp:
        yaml.safe_dump({'user': connection['user'], 'password': connection['password']}, fp)
    return path


@pytest.fixture
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    _clean(app)
    yield app
    _clean(app)


def _clean(app):
    for scope in [app.applications, app.chores, app.processes, app.views, app.rules, app.cubes, app.subsets, app.hierarchies, app.dimensions]:
        for name in scope.list(app):
            scope.delete(name, app)


@pytest.mark.requires_tm1
def test_put_then_get_round_trips_project(tmp_path, tm1_connection, remote):
    config = util.get_tm1cm_config()
    pushed = _project(str(tmp_path / 'pushed'), tm1_connection)
    shutil.copytree(os.path.join(util.get_local_config(), 'data'), os.path.join(pushed, 'data'), dirs_exist_ok=True)

    main('put', pushed, 'test')

    fetched = _project(str(tmp_path / 'fetched'), tm1_connection)
    main('get', fetched, 'test')

    source = LocalApplication(config, pushed)
    result = LocalApplication(config, fetched)
    for scope in source.scopes:
        names = scope.list(source)
        # TM1 also has what creating a cube adds: dimensions it names that the project lacks
        assert set(names) <= set(scope.list(result)), scope.type
        assert dict(scope.get(names, result)) == dict(scope.get(names, source)), scope.type
