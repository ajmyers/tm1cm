"""tm1cm's connection to TM1, on skipcheck-tm1.

tm1cm 0.9 talked to TM1 through TM1py. 1.0 uses skipcheck-tm1, but keeps TM1py's behaviour where
users can see it:

- The connection settings are TM1py's keyword arguments, read from connect.yaml and
  credentials.yaml, and resolved the way TM1py resolved them (see :func:`connect`).
- Requests are the ones TM1py sent, with the same bodies (processes, chores, dimensions,
  hierarchies, cubes, applications, cellsets), so what lands on TM1 is unchanged.
- Responses are asked for without OData metadata, as TM1py asked, so no etags reach the files.

Most of tm1cm sends its own requests through :class:`Rest`; the operations TM1py did in several
requests, or whose payload it shaped, are the functions further down.
"""
import base64
import collections.abc
import datetime
import json
import logging
from urllib.parse import quote

from skipcheck_tm1 import Tm1Session
from skipcheck_tm1 import Tm1Timeouts
from skipcheck_tm1 import auth
from skipcheck_tm1 import errors

logger = logging.getLogger(__name__)

# What TM1py sent: JSON without OData metadata (no @odata.etag in responses), or plain text
ACCEPT = 'application/json;odata.metadata=none,text/plain'
JSON_CONTENT_TYPE = 'application/json; odata.streaming=true; charset=utf-8'
BINARY_CONTENT_TYPE = 'application/octet-stream; odata.streaming=true'
API = '/api/v1/'


def key(name):
    """name as a quoted OData key's content in a URL: ' doubled, then percent-encoded (TM1py's format_url)."""
    return quote(str(name).replace("'", "''"), safe='')


class Tm1RestError(Exception):
    """TM1 refused a request (TM1py's TM1pyRestException): its status, and TM1's answer."""

    def __init__(self, status_code, text, method, url):
        super().__init__(f'Text: {text!r} - Status Code: {status_code} - {method} {url}')
        self.status_code = status_code
        self.text = text
        self.method = method
        self.url = url


class Response:
    """A reply, with the parts of requests.Response that tm1cm reads."""

    def __init__(self, reply):
        self.status_code = reply.status
        self.headers = reply.headers
        self.content = reply.content
        self._reply = reply

    @property
    def text(self):
        return self.content.decode('utf-8') if isinstance(self.content, bytes) else self.content

    def json(self):
        return json.loads(self.text)


class Rest:
    """TM1's REST API, request by request: urls as TM1py took them ('/api/v1/Cubes'), bodies as
    JSON text or bytes."""

    def __init__(self, session):
        self._session = session

    def request(self, method, url, data=None, headers=None):
        path = url[len(API):] if url.startswith(API) else url.lstrip('/')
        content = data.encode('utf-8') if isinstance(data, str) else data
        # As TM1py: JSON's content type on every request, even an action with no body, which TM1
        # refuses without it
        sent_headers = {'Content-Type': JSON_CONTENT_TYPE, **(headers or {})}
        try:
            return Response(self._session.request(method, path, content=content, headers=sent_headers, accept=ACCEPT))
        except errors.Tm1ApiError as e:
            text = e.error.message if getattr(e, 'error', None) else str(e)
            raise Tm1RestError(e.status, text, method, url) from e

    def GET(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def POST(self, url, data='', **kwargs):
        return self.request('POST', url, data, **kwargs)

    def PATCH(self, url, data='', **kwargs):
        return self.request('PATCH', url, data, **kwargs)

    def PUT(self, url, data='', **kwargs):
        return self.request('PUT', url, data, **kwargs)

    def DELETE(self, url, data='', **kwargs):
        return self.request('DELETE', url, data, **kwargs)

    def exists(self, url):
        """Whether GET url finds something (404 is no; any other refusal is an error)."""
        try:
            self.GET(url)
            return True
        except Tm1RestError as e:
            if e.status_code == 404:
                return False
            raise


class Tm1:
    """A connection to one TM1 server: :attr:`rest` for requests, and :attr:`base_url`."""

    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url
        self.rest = Rest(session)
        self._version = None

    @property
    def version(self):
        if self._version is None:
            self._version = self.rest.GET('/api/v1/Configuration/ProductVersion/$value').text
        return self._version

    def logout(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.logout()


# TM1py keyword arguments that skipcheck-tm1 manages itself, or that only tuned TM1py's HTTP stack
_IGNORED = {'tcp_keepalive', 'connection_pool_size', 'logging', 're_connect_on_session_timeout', 'cancel_at_timeout'}

# Every connection setting tm1cm reads from connect.yaml and credentials.yaml (and --connect)
SETTINGS = {
    'base_url', 'address', 'port', 'ssl', 'user', 'password', 'namespace', 'cam_passport', 'gateway', 'decode_b64',
    'verify', 'async_requests_mode', 'session_context', 'impersonate', 'timeout', 'auth', 'dispatcher', 'browser',
    'integrated_login', 'proxies',
} | _IGNORED


def _bool(value):
    if isinstance(value, str):
        return value.strip().upper() == 'TRUE'
    return bool(value)


def connect(terminal=None, **kwargs):
    """Connects with TM1py's keyword arguments, as users' connect.yaml and credentials.yaml hold
    them (see :func:`session_builder`), and logs in, so bad settings fail here, as with TM1py.

    How to log in, and what to ask the user, is :class:`tm1cm.login.Login`'s: a password typed in
    the terminal is asked for again when TM1 refuses it, and a passport from a browser sign-in is
    fetched again once. ``terminal`` is who to ask (by default, the one tm1cm runs in, if any).
    """
    from tm1cm import errors as tm1cm_errors
    from tm1cm.login import Login

    builder, root, async_requests = session_builder(**kwargs)
    logger.debug(f'Connecting with {tm1cm_errors.redact_settings(kwargs)}')
    signer = Login(kwargs, root, _verify(kwargs), terminal)
    while True:
        with tm1cm_errors.doing(f'logging in to TM1 at {root}'):
            authenticator = signer.authenticator()
        session = builder.copy().authenticator(authenticator).build()
        if async_requests:
            session = session.with_async(1.0)
        tm1 = Tm1(session, root)
        try:
            version = tm1.version
        except errors.Tm1TransportError as e:
            tm1.logout()
            hint = tm1cm_errors.CERTIFICATE_HINT if tm1cm_errors._untrusted(e) else \
                'Check base_url (or address, port and ssl) in connect.yaml, and that the server is running.'
            raise tm1cm_errors.ServerUnreachable(f"Couldn't reach TM1 at {root}: {e.__cause__ or e}", hint) from e
        except Tm1RestError as e:
            tm1.logout()
            refused = tm1cm_errors._find(e, errors.Tm1AuthenticationError)
            if refused is None or refused.kind != errors.Tm1ErrorKind.CREDENTIAL_REJECTED:
                raise
            if signer.rejected():
                continue
            raise signer.rejection() from e
        tm1cm_errors.connected(root, version)
        logger.info(f'Connected to TM1 {version} at {root} as {authenticator.describe()}')
        return tm1


def _verify(kwargs):
    """verify as TM1py took it: not checked unless set; True, False, 'True', 'False', or a CA bundle's path."""
    verify = kwargs.get('verify', False)
    if isinstance(verify, str) and verify.strip().upper() in ('TRUE', 'FALSE'):
        verify = verify.strip().upper() == 'TRUE'
    return verify


def session_builder(**kwargs):
    """A skipcheck-tm1 session builder, the server's root, and whether to use async requests, from
    TM1py's keyword arguments. Nothing is sent to TM1.

    Resolved as TM1py resolved them:

    - base_url is the server's root, and requests go to base_url + /api/v1 (the README's
      https://host:10000, or IBM Cloud's https://.../tm1/api/tm1). Without it, address, port and
      ssl (true unless set) make the root.
    - user and password log in with TM1 security; with namespace, through CAM; cam_passport
      with a passport. The builder holds these; :func:`connect` replaces them with what
      :class:`tm1cm.login.Login` works out, which also covers gateway, auth and the browser.
      decode_b64 means password is base64.
    - verify: certificates are not checked unless set, as TM1py didn't (see :func:`_verify`).
    - async_requests_mode, session_context, impersonate and timeout (seconds per request) as TM1py.
    """
    from tm1cm.errors import ConfigError

    if kwargs.get('integrated_login') and _bool(kwargs['integrated_login']):
        raise ConfigError('integrated_login (Windows integrated security) is not supported by tm1cm 1.0.',
                          'Use user and password, with namespace for CAM; or gateway, auth: browser, or cam_passport.')
    if kwargs.get('proxies'):
        raise ConfigError('proxies is not supported by tm1cm 1.0.', 'Set HTTPS_PROXY or HTTP_PROXY in the environment instead.')
    for name in sorted(_IGNORED & set(kwargs)):
        logger.debug(f'Connection setting {name} is ignored: skipcheck-tm1 manages it')

    if kwargs.get('base_url'):
        root = str(kwargs['base_url']).rstrip('/')
    elif kwargs.get('port'):
        ssl = _bool(kwargs.get('ssl', True))
        address = kwargs.get('address') or 'localhost'
        root = f"http{'s' if ssl else ''}://{address}:{kwargs.get('port')}"
    else:
        raise ConfigError('No TM1 server is set.', 'Set base_url (or address and port) in connect.yaml.')

    builder = Tm1Session.builder().base_url(root + API)

    password = _password(kwargs)
    verify = _verify(kwargs)

    if kwargs.get('cam_passport'):
        builder = builder.authenticator(auth.cam_passport(kwargs['cam_passport']))
    elif kwargs.get('namespace'):
        builder = builder.authenticator(auth.cam_namespace(kwargs.get('user') or '', password or '', kwargs['namespace']))
    else:
        builder = builder.basic_auth(kwargs.get('user') or '', password)

    builder = builder.verify(verify).session_context(str(kwargs.get('session_context') or 'tm1cm'))
    if kwargs.get('impersonate'):
        builder = builder.impersonate(kwargs['impersonate'])
    if kwargs.get('timeout') is not None:
        builder = builder.timeouts(Tm1Timeouts.DEFAULTS.with_request(float(kwargs['timeout'])))

    return builder, root, _bool(kwargs.get('async_requests_mode', False))


def _password(kwargs):
    password = kwargs.get('password')
    if password and _bool(kwargs.get('decode_b64', False)):
        password = base64.b64decode(password).decode('utf-8')
    return password


# --- Dimensions, hierarchies and elements --------------------------------------------------------

def dimension_body(item):
    """A dimension as TM1py's Dimension.body wrote it."""
    name = item['Name']
    return {
        'Name': name,
        'UniqueName': f'[{name}]',
        'Attributes': {'Caption': name},
        'Hierarchies': [hierarchy_body(h) for h in item.get('Hierarchies', []) if h['Name'].replace(' ', '').lower() != 'leaves'],
    }


def hierarchy_body(item):
    """A hierarchy as TM1py's Hierarchy.body wrote it: elements and edges, without attributes (TM1
    can't create those in the same request)."""
    edges = CaseAndSpaceInsensitiveTuplesDict()
    for edge in item.get('Edges', []):
        edges[(edge['ParentName'], edge['ComponentName'])] = edge['Weight']
    elements = CaseAndSpaceInsensitiveTuplesDict()
    for element in item.get('Elements', []):
        elements[(element['Name'],)] = {'Name': element['Name'], 'Type': element['Type']}
    return {
        'Name': item['Name'],
        'Elements': list(elements.values()),
        'Edges': [{'ParentName': parent, 'ComponentName': component, 'Weight': weight} for (parent, component), weight in edges.items()],
    }


def create_dimension(tm1, item):
    tm1.rest.POST('/api/v1/Dimensions', json.dumps(dimension_body(item), ensure_ascii=False))


def create_hierarchy(tm1, dimension, item):
    tm1.rest.POST(f"/api/v1/Dimensions('{key(dimension)}')/Hierarchies", json.dumps(hierarchy_body(item), ensure_ascii=False))


def element_names(tm1, dimension, hierarchy):
    url = f"/api/v1/Dimensions('{key(dimension)}')/Hierarchies('{key(hierarchy)}')/Elements?$select=Name"
    return [e['Name'] for e in tm1.rest.GET(url).json()['value']]


def element_attributes(tm1, dimension, hierarchy):
    """(name, type) of each element attribute."""
    url = f"/api/v1/Dimensions('{key(dimension)}')/Hierarchies('{key(hierarchy)}')/ElementAttributes"
    return [(a['Name'], a['Type']) for a in tm1.rest.GET(url).json()['value']]


def create_element(tm1, dimension, hierarchy, name, element_type):
    url = f"/api/v1/Dimensions('{key(dimension)}')/Hierarchies('{key(hierarchy)}')/Elements"
    tm1.rest.POST(url, json.dumps({'Name': name, 'Type': element_type}, ensure_ascii=False))


def delete_element(tm1, dimension, hierarchy, name):
    tm1.rest.DELETE(f"/api/v1/Dimensions('{key(dimension)}')/Hierarchies('{key(hierarchy)}')/Elements('{key(name)}')")


def create_element_attribute(tm1, dimension, hierarchy, name, attribute_type):
    url = f"/api/v1/Dimensions('{key(dimension)}')/Hierarchies('{key(hierarchy)}')/ElementAttributes"
    tm1.rest.POST(url, json.dumps({'Name': name, 'Type': attribute_type}, ensure_ascii=False))


def delete_element_attribute(tm1, dimension, hierarchy, name):
    """As TM1py's: through the attributes dimension, and quietly if it isn't there."""
    attributes = '}ElementAttributes_'
    url = f"/api/v1/Dimensions('{key(attributes + dimension)}')/Hierarchies('{key(attributes + hierarchy)}')/Elements('{key(name)}')"
    try:
        tm1.rest.DELETE(url)
    except Tm1RestError as e:
        if e.status_code != 404:
            raise


# --- Cubes ---------------------------------------------------------------------------------------

def cube_dimensions(tm1, cube):
    response = tm1.rest.GET(f"/api/v1/Cubes('{key(cube)}')?$expand=Dimensions($select=Name)")
    dimensions = [d['Name'] for d in response.json()['Dimensions']]
    # As TM1py: a server with EnableSandboxDimension=T lists Sandboxes first, which isn't the cube's own
    if dimensions and _lower_and_drop_spaces(dimensions[0]) == 'sandboxes':
        dimensions = dimensions[1:]
    return dimensions


def create_cube(tm1, item):
    """A cube as TM1py's Cube.body wrote it."""
    body = {'Name': item['Name'], 'Dimensions@odata.bind': [f"Dimensions('{key(d['Name'])}')" for d in item['Dimensions']]}
    if item.get('Rules'):
        body['Rules'] = item['Rules']
    tm1.rest.POST('/api/v1/Cubes', json.dumps(body, ensure_ascii=False))


def update_rules(tm1, cube, rules):
    tm1.rest.PATCH(f"/api/v1/Cubes('{key(cube)}')", json.dumps({'Rules': rules}, ensure_ascii=False))


# --- Processes -----------------------------------------------------------------------------------

def process_body(item, version):
    """A process as TM1py's Process.body wrote it: the data source holds only its type's fields."""
    source = item.get('DataSource', {}) or {}
    source_type = source.get('Type', '')

    def ds(field):
        return source.get(field, '')

    body = {
        'Name': item['Name'],
        'PrologProcedure': item['PrologProcedure'],
        'MetadataProcedure': item['MetadataProcedure'],
        'DataProcedure': item['DataProcedure'],
        'EpilogProcedure': item['EpilogProcedure'],
        'HasSecurityAccess': item['HasSecurityAccess'],
        'UIData': item['UIData'],
        'DataSource': {},
        'Parameters': item['Parameters'],
        'Variables': item['Variables'],
        'VariablesUIData': item['VariablesUIData'],
    }
    if source_type == 'ASCII':
        body['DataSource'] = {
            'Type': source_type,
            'asciiDecimalSeparator': ds('asciiDecimalSeparator'),
            'asciiDelimiterChar': ds('asciiDelimiterChar'),
            'asciiDelimiterType': ds('asciiDelimiterType'),
            'asciiHeaderRecords': ds('asciiHeaderRecords'),
            'asciiQuoteCharacter': ds('asciiQuoteCharacter'),
            'asciiThousandSeparator': ds('asciiThousandSeparator'),
            'dataSourceNameForClient': ds('dataSourceNameForClient'),
            'dataSourceNameForServer': ds('dataSourceNameForServer'),
        }
        if ds('asciiDelimiterType') == 'FixedWidth':
            del body['DataSource']['asciiDelimiterChar']
    elif source_type == 'None':
        body['DataSource'] = {'Type': 'None'}
    elif source_type == 'ODBC':
        body['DataSource'] = {
            'Type': source_type,
            'dataSourceNameForClient': ds('dataSourceNameForClient'),
            'dataSourceNameForServer': ds('dataSourceNameForServer'),
            'userName': ds('userName'),
            'password': ds('password'),
            'query': ds('query'),
            'usesUnicode': ds('usesUnicode'),
        }
    elif source_type == 'TM1CubeView':
        body['DataSource'] = {
            'Type': source_type,
            'dataSourceNameForClient': ds('dataSourceNameForServer'),
            'dataSourceNameForServer': ds('dataSourceNameForServer'),
            'view': ds('view'),
        }
    elif source_type == 'TM1DimensionSubset':
        body['DataSource'] = {
            'Type': source_type,
            'dataSourceNameForClient': ds('dataSourceNameForServer'),
            'dataSourceNameForServer': ds('dataSourceNameForServer'),
            'subset': ds('subset'),
        }
    if int(version[0:2]) < 11:
        # TM1 10 doesn't know parameter types
        body['Parameters'] = [{k: v for k, v in p.items() if k != 'Type'} for p in body['Parameters']]
    return body


def create_or_update_process(tm1, item):
    body = json.dumps(process_body(item, tm1.version), ensure_ascii=False)
    if tm1.rest.exists(f"/api/v1/Processes('{key(item['Name'])}')"):
        tm1.rest.PATCH(f"/api/v1/Processes('{key(item['Name'])}')", body)
    else:
        tm1.rest.POST('/api/v1/Processes', body)


def execute_process(tm1, name):
    tm1.rest.POST(f"/api/v1/Processes('{key(name)}')/tm1.Execute", json.dumps({}))


# --- Chores --------------------------------------------------------------------------------------

def _start_time(text):
    """TM1py's ChoreStartTime: the start time as written, without seconds when they're 0."""
    if '+' in text:
        tz = '+' + text.split('+')[1]
    elif text.count('-') == 3:
        tz = '-' + text.split('-')[-1]
    else:
        tz = None

    def number(part):
        return int(part) if part else 0
    moment = datetime.datetime(number(text[0:4]), number(text[5:7]), number(text[8:10]),
                               number(text[11:13]), number(text[14:16]), number(text[17:19]))
    written = moment.strftime('%Y-%m-%dT%H:%M:%S' if moment.second else '%Y-%m-%dT%H:%M')
    return moment, written + (tz if tz else 'Z')


def _frequency(text):
    """TM1py's ChoreFrequency: each part zero-padded to 2 digits."""
    pos_dt = text.find('DT', 1)
    pos_h = text.find('H', pos_dt)
    pos_m = text.find('M', pos_h)
    pos_s = len(text) - 1
    parts = (text[1:pos_dt], text[pos_dt + 2:pos_h], text[pos_h + 1:pos_m], text[pos_m + 1:pos_s])
    return 'P{}DT{}H{}M{}S'.format(*(str(p).zfill(2) for p in parts))


def _task_body(task):
    return {'Process@odata.bind': f"Processes('{key(task['Process']['Name'])}')",
            'Parameters': [{'Name': p['Name'], 'Value': p['Value']} for p in task['Parameters']]}


def chore_body(item):
    """A chore as TM1py's Chore.body wrote it."""
    _, start_time = _start_time(item['StartTime'])
    return {
        'Name': item['Name'],
        'StartTime': start_time,
        'DSTSensitive': item['DSTSensitive'],
        'Active': item['Active'],
        'ExecutionMode': item['ExecutionMode'],
        'Frequency': _frequency(item['Frequency']),
        'Tasks': [_task_body(task) for task in item['Tasks']],
    }


def create_or_update_chore(tm1, item):
    """As TM1py's ChoreService.update_or_create."""
    name = item['Name']
    url = f"/api/v1/Chores('{key(name)}')"
    body = chore_body(item)
    if not tm1.rest.exists(url):
        tm1.rest.POST('/api/v1/Chores', json.dumps(body, ensure_ascii=False))
    else:
        # Deactivated for the update, and activated again if it should be active
        tm1.rest.POST(url + '/tm1.Deactivate')
        tm1.rest.PATCH(url, json.dumps({k: v for k, v in body.items() if k != 'Tasks'}, ensure_ascii=False))
        count = int(tm1.rest.GET(url + '/Tasks/$count').text)
        for step, task in enumerate(item['Tasks']):
            if step >= count:
                tm1.rest.POST(url + '/Tasks', json.dumps(_task_body(task), ensure_ascii=False))
                continue
            old = tm1.rest.GET(url + f'/Tasks({step})?$expand=*,Process($select=Name),Chore($select=Name)').json()
            old_parameters = [{'Name': p['Name'], 'Value': p['Value']} for p in old['Parameters']]
            if old['Process']['Name'] != task['Process']['Name'] or old_parameters != _task_body(task)['Parameters']:
                tm1.rest.PATCH(url + f'/Tasks({step})', json.dumps(_task_body(task), ensure_ascii=False))
        for _ in range(len(item['Tasks']), count):
            tm1.rest.DELETE(url + f"/Tasks({len(item['Tasks'])})")
    if item['DSTSensitive']:
        moment, _ = _start_time(item['StartTime'])
        tm1.rest.POST(url + '/tm1.SetServerLocalStartTime', json.dumps({
            'StartDate': f'{moment.year}-{moment.month}-{moment.day}',
            'StartTime': f'{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}'}))
    if item['Active']:
        tm1.rest.POST(url + '/tm1.Activate')


# --- Cells ---------------------------------------------------------------------------------------

def _lower_and_drop_spaces(text):
    return text.replace(' ', '').lower()


class CaseAndSpaceInsensitiveTuplesDict(collections.abc.MutableMapping):
    """TM1py's dict keyed by tuples of names: looked up ignoring case and spaces, as TM1 does, and
    ordered as set."""

    def __init__(self, data=None):
        self._store = {}
        self.update(data or {})

    def _key(self, names):
        return tuple(_lower_and_drop_spaces(n) for n in names)

    def __setitem__(self, names, value):
        self._store[self._key(names)] = (names, value)

    def __getitem__(self, names):
        return self._store[self._key(names)][1]

    def __delitem__(self, names):
        del self._store[self._key(names)]

    def __iter__(self):
        return (names for names, _ in self._store.values())

    def __len__(self):
        return len(self._store)

    def __repr__(self):
        return repr(dict(self.items()))


def create_cellset(tm1, mdx):
    return tm1.rest.POST('/api/v1/ExecuteMDX', json.dumps({'MDX': mdx}, ensure_ascii=False)).json()['ID']


def delete_cellset(tm1, cellset_id):
    tm1.rest.DELETE(f"/api/v1/Cellsets('{key(cellset_id)}')")


def _cells(tm1, cellset_id, cell_properties):
    """A cellset's cells, keyed by their elements' unique names in the cube's dimension order, as
    TM1py's execute_mdx and execute_view returned them. The cellset is deleted afterwards."""
    url = (f"/api/v1/Cellsets('{key(cellset_id)}')?$expand="
           'Cube($select=Name;$expand=Dimensions($select=Name)),'
           'Axes($expand=Tuples($expand=Members($select=UniqueName;$expand=Element($select=UniqueName)))),'
           f"Cells($select={','.join(cell_properties)})")
    try:
        raw = tm1.rest.GET(url).json()
    finally:
        delete_cellset(tm1, cellset_id)

    dimensions = [d['Name'] for d in raw['Cube']['Dimensions']]
    axes = [axis for axis in raw['Axes'] if axis and axis.get('Tuples')]
    result = CaseAndSpaceInsensitiveTuplesDict()
    for ordinal, cell in enumerate(raw['Cells']):
        ordinal = cell.get('Ordinal', ordinal)
        coordinates = []
        for axis_ordinal, axis in enumerate(axes):
            tuple_ordinal = ordinal
            for previous in axes[:axis_ordinal]:
                tuple_ordinal //= previous['Cardinality']
            members = axis['Tuples'][tuple_ordinal % axis['Cardinality']]['Members']
            coordinates.extend(m['Element']['UniqueName'] if m.get('Element') else m['UniqueName'] for m in members)
        ordered = tuple(c for dimension in dimensions for c in coordinates if c.startswith('[' + dimension + '].'))
        result[ordered] = cell
    return result


def execute_mdx(tm1, mdx, cell_properties):
    return _cells(tm1, create_cellset(tm1, mdx), cell_properties)


def execute_view(tm1, cube, view, cell_properties):
    cellset_id = tm1.rest.POST(f"/api/v1/Cubes('{key(cube)}')/Views('{key(view)}')/tm1.Execute").json()['ID']
    return _cells(tm1, cellset_id, cell_properties)


def execute_mdx_values(tm1, mdx):
    cellset_id = create_cellset(tm1, mdx)
    try:
        response = tm1.rest.GET(f"/api/v1/Cellsets('{key(cellset_id)}')?$expand=Cells($select=Value)")
    finally:
        delete_cellset(tm1, cellset_id)
    return [cell['Value'] for cell in response.json()['Cells']]


# --- Applications --------------------------------------------------------------------------------

# Each application type: the suffix of its entry's ID, and its @odata.type (TM1py's ApplicationTypes)
APPLICATION_TYPES = {
    'CHORE': ('.chore', 'tm1.ChoreReference'),
    'CUBE': ('.cube', 'tm1.CubeReference'),
    'DIMENSION': ('.dimension', 'tm1.DimensionReference'),
    'DOCUMENT': ('.blob', '#ibm.tm1.api.v1.Document'),
    'FOLDER': ('', '#ibm.tm1.api.v1.Folder'),
    'LINK': ('.extr', '#ibm.tm1.api.v1.Link'),
    'PROCESS': ('.process', 'tm1.ProcessReference'),
    'SUBSET': ('.subset', 'tm1.SubsetReference'),
    'VIEW': ('.view', 'tm1.ViewReference'),
}


def _contents(path):
    return "/api/v1/Contents('Applications')" + ''.join(f"/Contents('{key(p)}')" for p in path.split('/') if p.strip())


def application_url(path, application_type, name):
    suffix, _ = APPLICATION_TYPES[application_type]
    return _contents(path) + f"/Contents('{key(name + suffix)}')"


def application_exists(tm1, path, application_type, name):
    return tm1.rest.exists(application_url(path, application_type, name))


def get_application(tm1, path, application_type, name):
    """An application entry, as TM1py's application objects gave it: its body (@odata.type, Name,
    and its reference or URL), and a document's content."""
    url = application_url(path, application_type, name)
    _, odata_type = APPLICATION_TYPES[application_type]
    body = {'@odata.type': odata_type, 'Name': name}
    content = None
    if application_type == 'DOCUMENT':
        content = tm1.rest.GET(url + '/Document/Content').content
        tm1.rest.GET(url + '/Document')
    elif application_type == 'FOLDER':
        tm1.rest.GET(url)
    elif application_type == 'LINK':
        body['URL'] = tm1.rest.GET(url + '?$expand=*').json()['URL']
    elif application_type == 'SUBSET':
        subset = tm1.rest.GET(url + '?$expand=Subset($select=Name;$expand=Hierarchy($select=Name;$expand=Dimension($select=Name)))').json()['Subset']
        body['Subset@odata.bind'] = "Dimensions('{}')/Hierarchies('{}')/Subsets('{}')".format(
            key(subset['Hierarchy']['Dimension']['Name']), key(subset['Hierarchy']['Name']), key(subset['Name']))
    elif application_type == 'VIEW':
        view = tm1.rest.GET(url + '?$expand=View($select=Name;$expand=Cube($select=Name))').json()['View']
        body['View@odata.bind'] = "Cubes('{}')/Views('{}')".format(key(view['Cube']['Name']), key(view['Name']))
    else:
        reference = {'CHORE': ('Chore', 'Chores'), 'CUBE': ('Cube', 'Cubes'), 'DIMENSION': ('Dimension', 'Dimensions'),
                     'PROCESS': ('Process', 'Processes')}[application_type]
        target = tm1.rest.GET(url + f'?$expand={reference[0]}($select=Name)').json()[reference[0]]['Name']
        body[reference[0] + '@odata.bind'] = f"{reference[1]}('{key(target)}')"
    return body, content


def create_application(tm1, path, body, content=None):
    """Creates an entry from its body; a document's content goes in a second request."""
    tm1.rest.POST(_contents(path) + '/Contents', json.dumps(body, ensure_ascii=False))
    if body['@odata.type'] == APPLICATION_TYPES['DOCUMENT'][1]:
        url = _contents(path) + f"/Contents('{key(body['Name'] + '.blob')}')/Document/Content"
        tm1.rest.PUT(url, content, headers={'Content-Type': BINARY_CONTENT_TYPE})


def delete_application(tm1, path, application_type, name):
    tm1.rest.DELETE(application_url(path, application_type, name))


def rename_application(tm1, path, application_type, name, new_name):
    tm1.rest.POST(application_url(path, application_type, name) + '/tm1.Move', json.dumps({'Name': new_name}, ensure_ascii=False))
