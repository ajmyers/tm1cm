"""Views shaped the ways users build them, round-tripped TM1 -> files -> TM1.

The checked-in test views cover a named subset and an MDX-expression subset. These add a static
element list on an axis, a title with a selected element, and an MDX view, on cubes whose names
need URL-encoding.
"""
import tempfile

import pytest
from TM1py.Objects import AnonymousSubset
from TM1py.Objects import Cube
from TM1py.Objects import Dimension
from TM1py.Objects import Element
from TM1py.Objects import Hierarchy
from TM1py.Objects import MDXView
from TM1py.Objects import NativeView
from TM1py.Objects import Subset

from tests.tm1cm import util
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication

DIMENSIONS = ['tm1cmV_D1', 'tm1cmV_D2', 'tm1cmV_D3']


@pytest.fixture(scope='module')
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    session = app.session
    for name in DIMENSIONS:
        if not session.dimensions.exists(name):
            session.dimensions.create(Dimension(name, [Hierarchy(name, name, elements=[Element(f'e{i}', 'Numeric') for i in range(5)])]))
            session.dimensions.subsets.create(Subset('named', name, name, elements=['e1', 'e2']), private=False)
    yield app
    for name in DIMENSIONS:
        session.dimensions.delete(name)


@pytest.mark.requires_tm1
@pytest.mark.parametrize('cube', ['tm1cmV Cube', 'tm1cmV A&B', 'tm1cmV #1'])
def test_view_shapes_round_trip(remote, cube):
    session = remote.session
    session.cubes.create(Cube(cube, DIMENSIONS))
    try:
        native = NativeView(cube, 'native')
        native.add_row(DIMENSIONS[0], AnonymousSubset(DIMENSIONS[0], DIMENSIONS[0], elements=['e0', 'e3']))
        native.add_column(DIMENSIONS[1], Subset('named', DIMENSIONS[1], DIMENSIONS[1]))
        native.add_title(DIMENSIONS[2], 'e4', AnonymousSubset(DIMENSIONS[2], DIMENSIONS[2], elements=['e1', 'e4']))
        session.cubes.views.create(native, private=False)
        mdx = f'SELECT {{[{DIMENSIONS[0]}].[e1]}} ON 0, {{[{DIMENSIONS[1]}].[e2]}} ON 1 FROM [{cube}] WHERE ([{DIMENSIONS[2]}].[e3])'
        session.cubes.views.create(MDXView(cube, 'mdx', mdx), private=False)

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
        session.cubes.delete(cube)
