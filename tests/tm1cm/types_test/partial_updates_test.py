"""How a put writes the objects it updates in part, or only under some conditions: subsets, cubes,
dimensions, view data, rules and chores.

Each test builds its own objects (tm1cmPart ...) and checks what TM1 holds after the put.
"""
import logging

import pytest
from skipcheck_tm1.errors import Tm1ApiError

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm import tm1 as tm1_client
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication

D1 = 'tm1cmPart D1'
D2 = 'tm1cmPart D2'
D3 = 'tm1cmPart D3'
CUBE = 'tm1cmPart Cube'
VIEW = 'tm1cmPart View'
SUBSET = 'tm1cmPart Subset'
CHORE = 'tm1cmPart Chore'
PROCESS = 'tm1cmPart Process'
MISSING = 'tm1cmPart Missing'


@pytest.fixture
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    _clean(app.session)
    tm1_objects.create_dimension(app.session, D1, ['a', 'b', 'c'])
    tm1_objects.create_dimension(app.session, D2, ['x', 'y'])
    tm1_objects.create_dimension(app.session, D3, ['p'])
    yield app
    _clean(app.session)


def _clean(session):
    if tm1_client.chore_exists(session, CHORE):
        session.client.chores.delete(CHORE)
    tm1_objects.delete_process(session, PROCESS)
    for cube in (CUBE, MISSING):
        tm1_objects.delete_cube(session, cube)
    for dimension in (D1, D2, D3):
        tm1_objects.delete_dimension(session, dimension)


def value(remote, cube, d1, d2):
    """The value at (d1, d2) of cube, whose dimensions are D1 then the second."""
    second = D2 if d2 in ('x', 'y') else D3
    mdx = f'SELECT {{[{second}].[{second}].[{d2}]}} ON 0, {{[{D1}].[{D1}].[{d1}]}} ON 1 FROM [{cube}]'
    return tm1_client.execute_mdx_values(remote.session, mdx)[0]


def cube_dimensions(remote):
    return tm1_client.cube_dimensions(remote.session, CUBE)


def rules(remote):
    """The cube's rules: a get leaves out a cube with none."""
    return dict(remote.rules.get([CUBE], remote)).get(CUBE, '')


def cube(*dimensions):
    return {'Name': CUBE, 'Dimensions': [{'Name': d} for d in dimensions]}


# --- Subsets -------------------------------------------------------------------------------------

SUBSET_NAME = (D1, D1, SUBSET)


def subset(remote):
    return dict(remote.subsets.get([SUBSET_NAME], remote))[SUBSET_NAME]


def static(*elements):
    return {'Name': SUBSET, 'Alias': '', 'Expression': None, 'Elements': [{'Name': e} for e in elements]}


def dynamic(mdx):
    return {'Name': SUBSET, 'Alias': '', 'Expression': mdx}


def through_a_file(remote, tmp_path, item):
    """item, written to a file and read back, as a put reads it."""
    local = LocalApplication(remote.config, str(tmp_path / 'local'))
    remote.subsets.update(SUBSET_NAME, item, local)
    return dict(remote.subsets.get([SUBSET_NAME], local))[SUBSET_NAME]


@pytest.mark.requires_tm1
def test_static_subset_becomes_dynamic(remote):
    tm1_objects.create_subset(remote.session, D1, SUBSET, ['a', 'b'])
    mdx = f'{{[{D1}].[{D1}].[c]}}'
    remote.subsets.update(SUBSET_NAME, dynamic(mdx), remote)

    assert subset(remote).get('Expression') == mdx


@pytest.mark.requires_tm1
def test_dynamic_subset_becomes_static(remote):
    remote.subsets.update(SUBSET_NAME, dynamic(f'{{[{D1}].[{D1}].[c]}}'), remote)
    remote.subsets.update(SUBSET_NAME, static('a', 'b'), remote)

    got = subset(remote)
    assert not got.get('Expression')
    assert [e['Name'] for e in got['Elements']] == ['a', 'b']


@pytest.mark.requires_tm1
def test_static_subset_is_changed(remote):
    tm1_objects.create_subset(remote.session, D1, SUBSET, ['a', 'b'])
    remote.subsets.update(SUBSET_NAME, static('c', 'a'), remote)

    assert [e['Name'] for e in subset(remote)['Elements']] == ['c', 'a']


@pytest.mark.requires_tm1
def test_static_subset_emptied_in_its_file_is_emptied(remote, tmp_path):
    """A static subset with no elements is written to its file without them, and a put of that
    file empties the target's."""
    tm1_objects.create_subset(remote.session, D1, SUBSET, ['a', 'b'])
    remote.subsets.update(SUBSET_NAME, through_a_file(remote, tmp_path, static()), remote)

    got = subset(remote)
    assert not got.get('Expression')
    assert got.get('Elements', []) == []


# --- Cubes and dimensions ------------------------------------------------------------------------


@pytest.mark.requires_tm1
def test_cube_with_the_same_dimensions_is_left_as_it_is(remote):
    tm1_objects.create_cube(remote.session, CUBE, [D1, D2])
    tm1_objects.write_value(remote.session, CUBE, [D1, D2], ['a', 'x'], 5)
    tm1_client.update_rules(remote.session, CUBE, "SKIPCHECK;\n['c'] = N: 1;")

    remote.cubes.update(CUBE, cube(D1, D2), remote)

    assert value(remote, CUBE, 'a', 'x') == 5
    assert "['c'] = N: 1;" in rules(remote)


@pytest.mark.requires_tm1
def test_cube_with_other_dimensions_is_deleted_and_recreated(remote, caplog):
    """Intended: the cube is recreated with the file's dimensions, and its data and rules go with
    the old one. A warning says so."""
    tm1_objects.create_cube(remote.session, CUBE, [D1, D2])
    tm1_objects.write_value(remote.session, CUBE, [D1, D2], ['a', 'x'], 5)
    tm1_client.update_rules(remote.session, CUBE, "SKIPCHECK;\n['c'] = N: 1;")

    with caplog.at_level(logging.WARNING):
        remote.cubes.update(CUBE, cube(D1, D3), remote)

    assert cube_dimensions(remote) == [D1, D3]
    assert value(remote, CUBE, 'a', 'p') in (0, None)
    assert rules(remote) == ''
    assert any(f'Deleting cube {CUBE}' in record.getMessage() for record in caplog.records)


@pytest.mark.requires_tm1
def test_cube_with_its_dimensions_reordered_is_recreated(remote):
    tm1_objects.create_cube(remote.session, CUBE, [D1, D2])
    remote.cubes.update(CUBE, cube(D2, D1), remote)

    assert cube_dimensions(remote) == [D2, D1]


@pytest.mark.requires_tm1
def test_new_cube_creates_its_missing_dimensions(remote):
    tm1_objects.delete_dimension(remote.session, D3)
    remote.cubes.update(CUBE, cube(D1, D3), remote)

    assert cube_dimensions(remote) == [D1, D3]


@pytest.mark.requires_tm1
def test_existing_dimension_is_left_as_it_is(remote):
    remote.dimensions.update(D1, {'Name': D1}, remote)

    assert sorted(tm1_client.element_names(remote.session, D1, D1)) == ['a', 'b', 'c']


# --- View data -----------------------------------------------------------------------------------

VIEW_NAME = (CUBE, VIEW)


def with_view(remote):
    tm1_objects.create_cube(remote.session, CUBE, [D1, D2])
    tm1_objects.create_native_view(remote.session, CUBE, VIEW, rows=[(D1, ['a', 'b'])], columns=[(D2, ['x'])])
    tm1_objects.write_values(remote.session, CUBE, [D1, D2], {('a', 'x'): 1, ('b', 'x'): 2, ('c', 'x'): 3})


def view_data(remote, **values):
    """The view's data as a file holds it, with values (element of D1: value) changed."""
    rows = dict(remote.views_data.get([VIEW_NAME], remote))[VIEW_NAME]
    for row in rows:
        element = row[0].rsplit('.[', 1)[1].rstrip(']')
        if element in values:
            row[-1] = values[element]
    return rows


@pytest.mark.requires_tm1
def test_view_data_is_written_and_cleared(remote):
    """The view's cells end up as the file has them; an empty value clears the cell."""
    with_view(remote)
    remote.views_data.update(VIEW_NAME, view_data(remote, a='', b='7'), remote)

    assert value(remote, CUBE, 'a', 'x') in (0, None)
    assert value(remote, CUBE, 'b', 'x') == 7


@pytest.mark.requires_tm1
def test_view_data_leaves_cells_outside_the_view(remote):
    with_view(remote)
    remote.views_data.update(VIEW_NAME, view_data(remote, a='', b=''), remote)

    assert value(remote, CUBE, 'c', 'x') == 3
    assert value(remote, CUBE, 'a', 'y') in (0, None)


@pytest.mark.requires_tm1
def test_unchanged_view_data_writes_nothing(remote, monkeypatch):
    """On a server with the sandbox dimension too, whose cells TM1 keys with a sandbox member that
    the file's rows don't have."""
    with_view(remote)
    item = view_data(remote)
    writes = []
    monkeypatch.setattr(remote.session.client.cells, 'update_cells', lambda *args, **kwargs: writes.append(args))

    remote.views_data.update(VIEW_NAME, item, remote)

    assert writes == []


@pytest.mark.requires_tm1
def test_view_data_skips_rule_derived_cells(remote):
    with_view(remote)
    tm1_client.update_rules(remote.session, CUBE, "['b'] = N: 9;")
    item = view_data(remote, a='4')
    # As a file from another server, where the cell isn't rule-derived, holds it
    item.append([f'[{D1}].[{D1}].[b]', f'[{D2}].[{D2}].[x]', '7'])

    remote.views_data.update(VIEW_NAME, item, remote)

    assert value(remote, CUBE, 'a', 'x') == 4
    assert value(remote, CUBE, 'b', 'x') == 9


# --- Rules ---------------------------------------------------------------------------------------


@pytest.mark.requires_tm1
def test_rules_of_a_cube_not_on_tm1_do_nothing(remote):
    remote.rules.update(MISSING, "SKIPCHECK;\n['c'] = N: 1;", remote)

    assert not tm1_client.cube_exists(remote.session, MISSING)


# --- Chores --------------------------------------------------------------------------------------


def chore(*processes, active=True):
    return {'Name': CHORE, 'StartTime': '2022-02-13T20:00:00+00:00', 'DSTSensitive': False, 'Active': active,
            'ExecutionMode': 'SingleCommit', 'Frequency': 'PT24H',
            'Tasks': [{'Step': step, 'Process': {'Name': p}, 'Parameters': []} for step, p in enumerate(processes)]}


def tasks(remote):
    return [t['Process']['Name'] for t in dict(remote.chores.get([CHORE], remote))[CHORE]['Tasks']]


@pytest.mark.requires_tm1
def test_chore_with_a_missing_process_is_refused(remote):
    with pytest.raises(Tm1ApiError):
        remote.chores.update(CHORE, chore(MISSING), remote)


@pytest.mark.requires_tm1
def test_active_chore_stays_active_when_a_task_is_refused(remote):
    """A put that fails on a task leaves an active chore active, with the tasks it had."""
    tm1_objects.create_process(remote.session, PROCESS)
    remote.chores.update(CHORE, chore(PROCESS), remote)
    assert remote.session.client.chores.get(CHORE).active

    with pytest.raises(Tm1ApiError):
        remote.chores.update(CHORE, chore(PROCESS, MISSING), remote)

    assert remote.session.client.chores.get(CHORE).active
    assert tasks(remote) == [PROCESS]
