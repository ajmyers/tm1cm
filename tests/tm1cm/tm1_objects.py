"""Builds TM1 objects for tests through tm1cm's own client and skipcheck-tm1's services."""
from skipcheck_tm1 import ODataPath

from tm1cm import tm1 as tm1_client

GENERATED = '#****Begin: Generated Statements***\r\n#****End: Generated Statements****\r\n'


def create_dimension(tm1, name, elements=(), element_type='Numeric'):
    tm1_client.create_dimension(tm1, {'Name': name, 'Hierarchies': [
        {'Name': name, 'Elements': [{'Name': e, 'Type': element_type} for e in elements], 'Edges': []}]})


def delete_dimension(tm1, name):
    if tm1_client.dimension_exists(tm1, name):
        tm1.client.dimensions.delete(name)


def _hierarchy(dimension, hierarchy=None):
    return ODataPath.of('Dimensions').key(dimension).nav('Hierarchies').key(hierarchy or dimension)


def _element(dimension, element):
    return str(_hierarchy(dimension).nav('Elements').key(element))


def create_subset(tm1, dimension, name, elements):
    body = {'Name': name, 'Hierarchy@odata.bind': str(_hierarchy(dimension)),
            'Elements@odata.bind': [_element(dimension, e) for e in elements]}
    tm1.client.subsets.create(dimension, dimension, tm1_client.PUBLIC_SUBSETS, body)


def create_cube(tm1, name, dimensions):
    tm1_client.create_cube(tm1, {'Name': name, 'Dimensions': [{'Name': d} for d in dimensions]})


def delete_cube(tm1, name):
    if tm1_client.cube_exists(tm1, name):
        tm1.client.cubes.delete(name)


def _selection(dimension, subset):
    """subset: a list of element names (an anonymous subset), or a named subset's name."""
    if isinstance(subset, str):
        return {'Subset@odata.bind': str(_hierarchy(dimension).nav('Subsets').key(subset))}
    return {'Subset': {'Hierarchy@odata.bind': str(_hierarchy(dimension)),
                       'Elements@odata.bind': [_element(dimension, e) for e in subset]}}


def create_native_view(tm1, cube, name, rows=(), columns=(), titles=()):
    """rows and columns: (dimension, subset); titles: (dimension, subset, selected element)."""
    body = {'@odata.type': '#ibm.tm1.api.v1.NativeView', 'Name': name,
            'Rows': [_selection(d, s) for d, s in rows],
            'Columns': [_selection(d, s) for d, s in columns],
            'Titles': [{**_selection(d, s), 'Selected@odata.bind': _element(d, e)} for d, s, e in titles]}
    tm1.client.views.create(cube, tm1_client.PUBLIC_VIEWS, body)


def create_mdx_view(tm1, cube, name, mdx):
    body = {'@odata.type': '#ibm.tm1.api.v1.MDXView', 'Name': name, 'MDX': mdx}
    tm1.client.views.create(cube, tm1_client.PUBLIC_VIEWS, body)


def write_values(tm1, cube, dimensions, values):
    """values: {(element, ...): value}, elements in dimensions' order."""
    updates = [{'Tuple@odata.bind': [_element(d, e) for d, e in zip(dimensions, elements)], 'Value': value}
               for elements, value in values.items()]
    tm1.client.cells.update_cells(cube, updates)


def create_process(tm1, name, prolog=''):
    tm1_client.create_or_update_process(tm1, {
        'Name': name, 'PrologProcedure': GENERATED + prolog, 'MetadataProcedure': GENERATED,
        'DataProcedure': GENERATED, 'EpilogProcedure': GENERATED, 'HasSecurityAccess': False,
        'UIData': 'CubeAction=1511\fDataAction=1503\fCubeLogChanges=0\f', 'DataSource': {'Type': 'None'},
        'Parameters': [], 'Variables': [], 'VariablesUIData': []})


def process_names(tm1):
    return [p.name for p in tm1.client.processes.list(tm1_client.names_query())]


def delete_process(tm1, name):
    if tm1_client.process_exists(tm1, name):
        tm1.client.processes.delete(name)


def create_folder(tm1, path, name):
    tm1_client.create_application(tm1, path, {'@odata.type': '#ibm.tm1.api.v1.Folder', 'Name': name})


def create_process_reference(tm1, path, name, process):
    tm1_client.create_application(tm1, path, {'@odata.type': 'tm1.ProcessReference', 'Name': name,
                                              'Process@odata.bind': str(ODataPath.of('Processes').key(process))})


def write_value(tm1, cube, dimensions, elements, value):
    write_values(tm1, cube, dimensions, {tuple(elements): value})
