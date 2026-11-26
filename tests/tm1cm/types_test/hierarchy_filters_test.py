"""What a put of a hierarchy writes, and what it leaves as TM1 has it, when the config filters out
part of the hierarchy: its elements, edges, attributes or attribute values.

The rule, from tm1cm.yaml: what's filtered out is left as TM1 has it, and a hierarchy whose elements
are filtered out is put without them.
"""
import pytest

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm.application import RemoteApplication

DIM = 'tm1cmFlt Dim'
OTHER = 'tm1cmFlt Other'
NAME = (DIM, DIM)
OTHER_NAME = (OTHER, OTHER)

ELEMENTS = [('Total', 'Consolidated'), ('a', 'Numeric'), ('b', 'Numeric'), ('c', 'Numeric')]
EDGES = [('Total', 'a', 1), ('Total', 'b', 1), ('Total', 'c', 1)]
ATTRIBUTES = ['Colour', 'Size']
VALUES = {'a': {'Colour': 'red', 'Size': 'big'}}


@pytest.fixture
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    _clean(app.session)
    yield app
    _clean(app.session)


def _clean(session):
    for dimension in (DIM, OTHER):
        tm1_objects.delete_dimension(session, dimension)


def filtered(remote, **settings):
    """The same TM1, through a config that filters out what settings say."""
    return RemoteApplication({**util.get_tm1cm_config(), **settings}, remote.session)


def hierarchy(name, elements=ELEMENTS, edges=EDGES, attributes=ATTRIBUTES, values=VALUES):
    """A hierarchy as a file holds it."""
    return {'Name': name[1],
            'Elements': [{'Name': e, 'Type': t, 'Attributes': dict(values.get(e, {}))} for e, t in elements],
            'Edges': [{'ParentName': p, 'ComponentName': c, 'Weight': w} for p, c, w in edges],
            'ElementAttributes': [{'Name': a, 'Type': 'String'} for a in attributes]}


def put(app, name, item):
    app.hierarchies.update(name, item, app)


def seed(remote, *names):
    for name in names:
        put(remote, name, hierarchy(name))


def read(remote, name):
    """The hierarchy as TM1 has it, read with nothing filtered out."""
    return dict(remote.hierarchies.get([name], remote))[name]


def elements(remote, name):
    return sorted(e['Name'] for e in read(remote, name).get('Elements', []))


def edges(remote, name):
    return sorted((e['ParentName'], e['ComponentName'], float(e['Weight'])) for e in read(remote, name).get('Edges', []))


def attributes(remote, name):
    return sorted(a['Name'] for a in read(remote, name)['ElementAttributes'])


def values(remote, name, element):
    return next(e for e in read(remote, name)['Elements'] if e['Name'] == element).get('Attributes', {})


SEEDED_EDGES = sorted((p, c, float(w)) for p, c, w in EDGES)


# --- Edges ---------------------------------------------------------------------------------------

@pytest.mark.requires_tm1
def test_edges_excluded_ignores_the_files_edges(remote):
    """The file's edges and weights aren't written; the target keeps its own, and the elements are
    still written."""
    seed(remote, NAME)
    app = filtered(remote, exclude_dimension_hierarchy_edge=f'{DIM}/{DIM}')
    put(app, NAME, hierarchy(NAME, elements=ELEMENTS + [('d', 'Numeric')], edges=[('Total', 'a', 2), ('Total', 'd', 1)]))

    assert elements(remote, NAME) == ['Total', 'a', 'b', 'c', 'd']
    assert edges(remote, NAME) == SEEDED_EDGES


@pytest.mark.requires_tm1
def test_edges_excluded_drops_the_edges_of_removed_elements(remote):
    """An element the file drops is deleted, and its edges with it. The others stay."""
    seed(remote, NAME)
    app = filtered(remote, exclude_dimension_hierarchy_edge=f'{DIM}/{DIM}')
    put(app, NAME, hierarchy(NAME, elements=ELEMENTS[:3], edges=[]))

    assert elements(remote, NAME) == ['Total', 'a', 'b']
    assert edges(remote, NAME) == [('Total', 'a', 1.0), ('Total', 'b', 1.0)]


@pytest.mark.requires_tm1
def test_edges_included_replace_the_targets(remote):
    seed(remote, NAME)
    put(remote, NAME, hierarchy(NAME, edges=[('Total', 'a', 2), ('Total', 'b', 1)]))

    assert edges(remote, NAME) == [('Total', 'a', 2.0), ('Total', 'b', 1.0)]


@pytest.mark.requires_tm1
def test_edge_filter_applies_to_the_hierarchy_it_names(remote):
    seed(remote, NAME, OTHER_NAME)
    app = filtered(remote, exclude_dimension_hierarchy_edge=f'{DIM}/{DIM}')
    put(app, NAME, hierarchy(NAME, edges=[]))
    put(app, OTHER_NAME, hierarchy(OTHER_NAME, edges=[]))

    assert edges(remote, NAME) == SEEDED_EDGES
    assert edges(remote, OTHER_NAME) == []


# --- Elements ------------------------------------------------------------------------------------

@pytest.mark.requires_tm1
def test_element_filter_applies_to_the_hierarchy_it_names(remote):
    """With a hierarchy's elements excluded, its elements and edges stay. Another's are written."""
    seed(remote, NAME, OTHER_NAME)
    app = filtered(remote, exclude_dimension_hierarchy_element=f'{DIM}/{DIM}')
    put(app, NAME, hierarchy(NAME, elements=ELEMENTS[:1], edges=[]))
    put(app, OTHER_NAME, hierarchy(OTHER_NAME, elements=ELEMENTS[:1], edges=[]))

    assert elements(remote, NAME) == ['Total', 'a', 'b', 'c']
    assert edges(remote, NAME) == SEEDED_EDGES
    assert elements(remote, OTHER_NAME) == ['Total']
    assert edges(remote, OTHER_NAME) == []


@pytest.mark.requires_tm1
def test_elements_excluded_writes_no_attribute_values(remote):
    """The file's values for elements that are filtered out aren't written."""
    seed(remote, NAME)
    app = filtered(remote, exclude_dimension_hierarchy_element=f'{DIM}/{DIM}')
    put(app, NAME, hierarchy(NAME, values={'a': {'Colour': 'blue', 'Size': 'small'}}))

    assert values(remote, NAME, 'a') == {'Colour': 'red', 'Size': 'big'}


# --- Attributes and their values -----------------------------------------------------------------

@pytest.mark.requires_tm1
def test_attributes_excluded_are_neither_deleted_nor_created(remote):
    seed(remote, NAME)
    app = filtered(remote, exclude_dimension_hierarchy_attribute=[f'{DIM}/{DIM}/Colour', f'{DIM}/{DIM}/Shape'])
    put(app, NAME, hierarchy(NAME, attributes=['Size', 'Shape'], values={}))

    assert attributes(remote, NAME) == ATTRIBUTES


@pytest.mark.requires_tm1
def test_attributes_included_are_deleted_and_created(remote):
    seed(remote, NAME)
    put(remote, NAME, hierarchy(NAME, attributes=['Size', 'Shape'], values={}))

    assert attributes(remote, NAME) == ['Shape', 'Size']


@pytest.mark.requires_tm1
def test_attribute_values_excluded_are_not_written(remote):
    seed(remote, NAME)
    app = filtered(remote, exclude_dimension_hierarchy_attribute_value=f'{DIM}/{DIM}/Colour')
    put(app, NAME, hierarchy(NAME, values={'a': {'Colour': 'blue', 'Size': 'small'}}))

    assert values(remote, NAME, 'a') == {'Colour': 'red', 'Size': 'small'}


# --- get -----------------------------------------------------------------------------------------

@pytest.mark.requires_tm1
def test_get_leaves_out_what_is_excluded(remote):
    seed(remote, NAME)
    app = filtered(remote, exclude_dimension_hierarchy_edge=f'{DIM}/{DIM}',
                   exclude_dimension_hierarchy_attribute=f'{DIM}/{DIM}/Size',
                   exclude_dimension_hierarchy_attribute_value=f'{DIM}/{DIM}/Colour')
    item = dict(app.hierarchies.get([NAME], app))[NAME]

    assert 'Edges' not in item or item['Edges'] == []
    assert [a['Name'] for a in item['ElementAttributes']] == ['Colour']
    assert all(not e.get('Attributes') for e in item['Elements'])


@pytest.mark.requires_tm1
def test_get_with_elements_excluded_leaves_out_elements_and_edges(remote):
    seed(remote, NAME)
    app = filtered(remote, exclude_dimension_hierarchy_element=f'{DIM}/{DIM}')
    item = dict(app.hierarchies.get([NAME], app))[NAME]

    assert not item.get('Elements') and not item.get('Edges')
    assert sorted(a['Name'] for a in item['ElementAttributes']) == ATTRIBUTES
