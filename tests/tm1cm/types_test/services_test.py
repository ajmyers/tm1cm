"""Writes that take a path of their own through skipcheck-tm1's services, against TM1."""
import pytest

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm import tm1 as tm1_client
from tm1cm.application import RemoteApplication

DIMENSION = 'tm1cmSvc Dim'
PROCESSES = ['tm1cmSvc P1', 'tm1cmSvc P2']
CHORE = 'tm1cmSvc Chore'


@pytest.fixture(params=[False, True], ids=['sync', 'async'])
def remote(request, tm1_connection):
    """A connection, with and without async_requests_mode (each request run by TM1 asynchronously
    and polled)."""
    app = RemoteApplication(util.get_tm1cm_config(), None, {**tm1_connection, 'async_requests_mode': request.param})
    session = app.session
    _clean(session)
    yield app
    _clean(session)


def _clean(session):
    if tm1_client.chore_exists(session, CHORE):
        session.client.chores.delete(CHORE)
    for process in PROCESSES:
        tm1_objects.delete_process(session, process)
    tm1_objects.delete_dimension(session, DIMENSION)


def _hierarchy(elements, edges, attributes=()):
    return {'Name': DIMENSION,
            'Elements': [{'Name': e, 'Type': t, 'Attributes': {}} for e, t in elements],
            'Edges': [{'ParentName': p, 'ComponentName': c, 'Weight': w} for p, c, w in edges],
            'ElementAttributes': [{'Name': a, 'Type': 'String'} for a in attributes]}


def _edges(session):
    return sorted((e.parent_name, e.component_name) for e in session.client.edges.list(DIMENSION, DIMENSION))


@pytest.mark.requires_tm1
def test_element_attributes_are_added_and_deleted(remote):
    name = (DIMENSION, DIMENSION)
    elements = [('a', 'Numeric')]
    remote.hierarchies.update(name, _hierarchy(elements, [], ['Colour', 'Size']), remote)
    assert sorted(a for a, _ in tm1_client.element_attributes(remote.session, *name)) == ['Colour', 'Size']

    remote.hierarchies.update(name, _hierarchy(elements, [], ['Size', 'Weight']), remote)
    assert sorted(a for a, _ in tm1_client.element_attributes(remote.session, *name)) == ['Size', 'Weight']

    # Quietly, if it's gone already
    tm1_client.delete_element_attribute(remote.session, *name, 'Colour')
