"""Objects and elements whose names need escaping, through every type that names them in requests."""
import tempfile

import pytest

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.common import odata_key

# '#' ends a URL's path and '%' starts an escape; TM1 allows both in object names
D1, D2, SUB, CUBE, VIEW = 'tm1cmN D#1', 'tm1cmN D%2', 'tm1cmN s#1', 'tm1cmN c#1', 'tm1cmN v%1'
# Element names may also contain ', which OData escapes by doubling
ELEMENTS = ["e'1", 'e#2', 'e%3', 'e4']

NAMES = {
    'dimension': [D1, D2],
    'hierarchy': [(D1, D1), (D2, D2)],
    'subset': [(D1, D1, SUB)],
    'cube': [CUBE],
    'view': [(CUBE, VIEW)],
    'view_data': [(CUBE, VIEW)],
}


def test_odata_key():
    assert odata_key("Men's") == "Men%27%27s"
    assert odata_key('a#1 50%') == 'a%231%2050%25'


@pytest.fixture(scope='module')
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    session = app.session
    _clean(session)
    for name in [D1, D2]:
        tm1_objects.create_dimension(session, name, ELEMENTS)
    tm1_objects.create_subset(session, D1, SUB, ELEMENTS[:3])
    tm1_objects.create_cube(session, CUBE, [D1, D2])
    tm1_objects.create_native_view(session, CUBE, VIEW, rows=[(D1, ELEMENTS)], columns=[(D2, ["e'1", 'e#2'])])
    tm1_objects.write_values(session, CUBE, [D1, D2], {("e'1", "e'1"): 1, ('e#2', 'e#2'): 2, ('e%3', "e'1"): 3})
    yield app
    _clean(session)


def _clean(session):
    tm1_objects.delete_cube(session, CUBE)
    for name in [D1, D2]:
        tm1_objects.delete_dimension(session, name)


@pytest.mark.requires_tm1
@pytest.mark.parametrize('scope_type', NAMES)
def test_round_trip(remote, scope_type):
    """Get from TM1, write to and read from files, write back to TM1: nothing changes."""
    scope = {s.type: s for s in remote.scopes}[scope_type]
    names = NAMES[scope_type]
    local = LocalApplication(util.get_tm1cm_config(), tempfile.mkdtemp(prefix='tm1cm_test_'))

    got = dict(scope.get(names, remote))
    assert set(got) == set(names)

    for name, item in got.items():
        scope.update(name, item, local)
    from_files = dict(scope.get(names, local))
    assert from_files == got

    for name, item in from_files.items():
        scope.update(name, item, remote)
    assert dict(scope.get(names, remote)) == got


@pytest.mark.requires_tm1
@pytest.mark.parametrize('scope_type', ['view', 'subset'])
def test_delete(remote, scope_type):
    scope = {s.type: s for s in remote.scopes}[scope_type]
    for name in NAMES[scope_type]:
        scope.delete(name, remote)

    assert not set(NAMES[scope_type]) & set(scope.list(remote))
