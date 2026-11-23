"""Views shaped the ways users build them, round-tripped TM1 -> files -> TM1.

The checked-in test views cover a named subset and an MDX-expression subset. These add a static
element list on an axis, a title with a selected element, and an MDX view, on cubes whose names
need URL-encoding.
"""
import tempfile

import pytest

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication

DIMENSIONS = ['tm1cmV_D1', 'tm1cmV_D2', 'tm1cmV_D3']


@pytest.fixture(scope='module')
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    session = app.session
    for name in DIMENSIONS:
        tm1_objects.delete_dimension(session, name)
        tm1_objects.create_dimension(session, name, [f'e{i}' for i in range(5)])
        tm1_objects.create_subset(session, name, 'named', ['e1', 'e2'])
    yield app
    for name in DIMENSIONS:
        tm1_objects.delete_dimension(session, name)


@pytest.mark.requires_tm1
@pytest.mark.parametrize('cube', ['tm1cmV Cube', 'tm1cmV A&B', 'tm1cmV #1'])
def test_view_shapes_round_trip(remote, cube):
    session = remote.session
    tm1_objects.create_cube(session, cube, DIMENSIONS)
    try:
        tm1_objects.create_native_view(session, cube, 'native', rows=[(DIMENSIONS[0], ['e0', 'e3'])], columns=[(DIMENSIONS[1], 'named')],
                                       titles=[(DIMENSIONS[2], ['e1', 'e4'], 'e4')])
        mdx = f'SELECT {{[{DIMENSIONS[0]}].[e1]}} ON 0, {{[{DIMENSIONS[1]}].[e2]}} ON 1 FROM [{cube}] WHERE ([{DIMENSIONS[2]}].[e3])'
        tm1_objects.create_mdx_view(session, cube, 'mdx', mdx)

        views = remote.views
        names = [name for name in views.list(remote) if name[0] == cube]
        assert sorted(names) == [(cube, 'mdx'), (cube, 'native')]
        got = dict(views.get(names, remote))
        assert got[(cube, 'native')]['@odata.type'] == '#ibm.tm1.api.v1.NativeView'
        assert got[(cube, 'mdx')]['@odata.type'] == '#ibm.tm1.api.v1.MDXView'

        local = LocalApplication(util.get_tm1cm_config(), tempfile.mkdtemp(prefix='tm1cm_test_'))
        for name, item in got.items():
            views.update(name, item, local)
        from_files = dict(views.get(names, local))
        assert from_files == got

        for name in names:
            views.delete(name, remote)
        for name, item in from_files.items():
            views.update(name, item, remote)
        assert dict(views.get(names, remote)) == got
    finally:
        tm1_objects.delete_cube(session, cube)
