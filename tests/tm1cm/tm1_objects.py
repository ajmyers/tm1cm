"""Builds TM1 objects for tests through tm1cm's own client (TM1py's objects and services, before 1.0)."""
import json

from tm1cm import tm1 as tm1_client
from tm1cm.tm1 import key

GENERATED = '#****Begin: Generated Statements***\r\n#****End: Generated Statements****\r\n'


def exists(tm1, url):
    return tm1.rest.exists(url)


def create_dimension(tm1, name, elements=(), element_type='Numeric'):
    tm1_client.create_dimension(tm1, {'Name': name, 'Hierarchies': [
        {'Name': name, 'Elements': [{'Name': e, 'Type': element_type} for e in elements], 'Edges': []}]})


def delete_dimension(tm1, name):
    if tm1.rest.exists(f"/api/v1/Dimensions('{key(name)}')"):
        tm1.rest.DELETE(f"/api/v1/Dimensions('{key(name)}')")


def _hierarchy_bind(dimension, hierarchy=None):
    return f"Dimensions('{key(dimension)}')/Hierarchies('{key(hierarchy or dimension)}')"


def create_subset(tm1, dimension, name, elements):
    body = {'Name': name, 'Hierarchy@odata.bind': _hierarchy_bind(dimension),
            'Elements@odata.bind': [_hierarchy_bind(dimension) + f"/Elements('{key(e)}')" for e in elements]}
    tm1.rest.POST(f"/api/v1/Dimensions('{key(dimension)}')/Hierarchies('{key(dimension)}')/Subsets", json.dumps(body))


def create_cube(tm1, name, dimensions):
    tm1_client.create_cube(tm1, {'Name': name, 'Dimensions': [{'Name': d} for d in dimensions]})


def delete_cube(tm1, name):
    if tm1.rest.exists(f"/api/v1/Cubes('{key(name)}')"):
        tm1.rest.DELETE(f"/api/v1/Cubes('{key(name)}')")


def _selection(dimension, subset):
    """subset: a list of element names (an anonymous subset), or a named subset's name."""
    if isinstance(subset, str):
        return {'Subset@odata.bind': _hierarchy_bind(dimension) + f"/Subsets('{key(subset)}')"}
    return {'Subset': {'Hierarchy@odata.bind': _hierarchy_bind(dimension),
                       'Elements@odata.bind': [_hierarchy_bind(dimension) + f"/Elements('{key(e)}')" for e in subset]}}


def create_native_view(tm1, cube, name, rows=(), columns=(), titles=()):
    """rows and columns: (dimension, subset); titles: (dimension, subset, selected element)."""
    body = {'@odata.type': '#ibm.tm1.api.v1.NativeView', 'Name': name,
            'Rows': [_selection(d, s) for d, s in rows],
            'Columns': [_selection(d, s) for d, s in columns],
            'Titles': [{**_selection(d, s), 'Selected@odata.bind': _hierarchy_bind(d) + f"/Elements('{key(e)}')"} for d, s, e in titles]}
    tm1.rest.POST(f"/api/v1/Cubes('{key(cube)}')/Views", json.dumps(body))


def create_mdx_view(tm1, cube, name, mdx):
    body = {'@odata.type': '#ibm.tm1.api.v1.MDXView', 'Name': name, 'MDX': mdx}
    tm1.rest.POST(f"/api/v1/Cubes('{key(cube)}')/Views", json.dumps(body))


def write_values(tm1, cube, dimensions, values):
    """values: {(element, ...): value}, elements in dimensions' order."""
    updates = [{'Cells': [{'Tuple@odata.bind': [_hierarchy_bind(d) + f"/Elements('{key(e)}')" for d, e in zip(dimensions, elements)]}],
                'Value': value} for elements, value in values.items()]
    tm1.rest.POST(f"/api/v1/Cubes('{key(cube)}')/tm1.Update", json.dumps(updates))


def create_process(tm1, name, prolog=''):
    tm1_client.create_or_update_process(tm1, {
        'Name': name, 'PrologProcedure': GENERATED + prolog, 'MetadataProcedure': GENERATED,
        'DataProcedure': GENERATED, 'EpilogProcedure': GENERATED, 'HasSecurityAccess': False,
        'UIData': 'CubeAction=1511\fDataAction=1503\fCubeLogChanges=0\f', 'DataSource': {'Type': 'None'},
        'Parameters': [], 'Variables': [], 'VariablesUIData': []})


def process_names(tm1):
    return [p['Name'] for p in tm1.rest.GET('/api/v1/Processes?$select=Name').json()['value']]


def delete_process(tm1, name):
    if tm1.rest.exists(f"/api/v1/Processes('{key(name)}')"):
        tm1.rest.DELETE(f"/api/v1/Processes('{key(name)}')")


def create_folder(tm1, path, name):
    tm1_client.create_application(tm1, path, {'@odata.type': '#ibm.tm1.api.v1.Folder', 'Name': name})


def create_process_reference(tm1, path, name, process):
    tm1_client.create_application(tm1, path, {'@odata.type': 'tm1.ProcessReference', 'Name': name,
                                              'Process@odata.bind': f"Processes('{key(process)}')"})


def write_value(tm1, cube, dimensions, elements, value):
    write_values(tm1, cube, dimensions, {tuple(elements): value})
