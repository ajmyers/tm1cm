"""tm1cm's connection to TM1, on skipcheck-tm1.

tm1cm 0.9 talked to TM1 through TM1py. 1.0 uses skipcheck-tm1's services:

- The connection settings are TM1py's keyword arguments, read from connect.yaml and
  credentials.yaml, and resolved the way TM1py resolved them (see :func:`connect`).
- Reads and writes go through the services (``tm1.client.processes``, ``tm1.client.cubes`` …),
  with paths, keys and filters built by skipcheck-tm1, so names are escaped by construction.
  Reads come back as skipcheck-tm1's models and become TM1's JSON again with :func:`odata`.
- Write bodies are still the ones TM1py sent (processes, chores, dimensions, hierarchies, cubes,
  applications), so what lands on TM1 is unchanged.

The operations TM1py did in several requests, or whose payload it shaped, are the functions
further down.
"""
import base64
import collections.abc
import datetime
import logging
import re

from skipcheck_tm1 import Filter
from skipcheck_tm1 import ODataPath
from skipcheck_tm1 import ODataQuery
from skipcheck_tm1 import Tm1Client
from skipcheck_tm1 import Tm1Session
from skipcheck_tm1 import Tm1Timeouts
from skipcheck_tm1 import auth
from skipcheck_tm1 import errors
from skipcheck_tm1 import model
from skipcheck_tm1.odata import duration
from skipcheck_tm1.values import AttributeSet
from skipcheck_tm1.values import ContentPath
from skipcheck_tm1.values import ContentScope
from skipcheck_tm1.values import SubsetScope
from skipcheck_tm1.values import ViewScope

logger = logging.getLogger(__name__)

NotFound = errors.Tm1NotFoundError

PUBLIC_SUBSETS = SubsetScope.PUBLIC
PUBLIC_VIEWS = ViewScope.PUBLIC
PUBLIC_CONTENTS = ContentScope.PUBLIC

API = '/api/v1/'

# Filters are or'd together in as many requests as it takes to keep each URL to this length
MAX_URL = 6000


class Tm1:
    """A connection to one TM1 server: :attr:`client` for its services, and :attr:`base_url`."""

    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url
        self.client = Tm1Client.of(session)
        self._version = None

    @property
    def version(self):
        if self._version is None:
            self._version = str(self.session.version())
        return self._version

    def logout(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.logout()


def odata(read):
    """A model read from TM1 (or a list of them) as TM1's JSON, as tm1cm's files hold it.

    The models hold some values in their own types, so they come back as skipcheck-tm1 writes
    them: a chore's Frequency as PT24H rather than P01DT00H00M00S, an edge's Weight as 1.0. A
    value the model doesn't know (an enum member newer than skipcheck-tm1) can't be written back,
    and fails here, naming the object."""
    if isinstance(read, list):
        return [odata(r) for r in read]
    try:
        return read.to_odata()
    except ValueError as e:
        name = getattr(read, 'name', None)
        raise ValueError(f'Cannot read {type(read).__name__} {name!r} from TM1: {e}. '
                         'A newer skipcheck-tm1 may know the value') from e


def exists(read):
    """Whether read() finds something: a Tm1NotFoundError is no; any other refusal is an error."""
    try:
        read()
        return True
    except NotFound:
        return False


def names_query(**options):
    return ODataQuery.of(None, select='Name', **options)


def filtered(read, query, names):
    """read(query with a filter) for every name, the names' conditions (Name eq …) or'd together in as many
    requests as it takes to keep each query string to MAX_URL characters."""
    results = []
    batch = []

    def flush():
        if batch:
            results.extend(read(query.filter(Filter.or_(*batch))))

    for name in names:
        condition = model.Cube.NAME.eq(name)
        if batch and len(query.filter(Filter.or_(*batch, condition)).to_query_string()) > MAX_URL:
            flush()
            batch = []
        batch.append(condition)
    flush()
    return results


# TM1py keyword arguments that skipcheck-tm1 manages itself, or that only tuned TM1py's HTTP stack
_IGNORED = {'tcp_keepalive', 'connection_pool_size', 'logging', 're_connect_on_session_timeout', 'cancel_at_timeout'}

# Every connection setting tm1cm reads from connect.yaml and credentials.yaml (and --connect),
# with what it does: the docs' reference (docs-site) is written from these, and a setting
# without a description fails its build. Each is (the file it usually goes in, description).
SETTING_DOCS = {
    'base_url': ('connect', "The server's address, without /api/v1, which tm1cm adds: https://tm1.example.com:12354. "
                            'For Planning Analytics on IBM Cloud, the address up to the server: '
                            'https://mycompany.planning-analytics.ibmcloud.com/tm1/api/tm1.'),
    'address': ('connect', "The server's host name, used with port (and ssl) when base_url isn't set. localhost unless set."),
    'port': ('connect', "The server's HTTP port (HTTPPortNumber in its tm1s.cfg), used with address when base_url isn't set."),
    'ssl': ('connect', 'Whether address and port are reached over HTTPS: true unless set.'),
    'verify': ('connect', "Whether the server's certificate is checked: not unless set. true checks it against the system's "
                          "certificates; the path of a CA bundle checks it against that, for a server whose certificate it signs."),
    'async_requests_mode': ('connect', 'true for a server behind a gateway that times out long requests: TM1 is asked to '
                                       'answer them asynchronously, and tm1cm waits for the answer.'),
    'session_context': ('connect', "The name TM1 shows for tm1cm's sessions, in TM1top and Arc: tm1cm unless set."),
    'impersonate': ('connect', 'Another TM1 user to act as, for an admin user.'),
    'timeout': ('connect', 'How many seconds tm1cm waits for TM1 to answer a request.'),
    'auth': ('connect', 'How to log in, when tm1cm shouldn\'t work it out: basic (TM1\'s own security), cam (a user and '
                        'password in a CAM namespace) or browser (signing in to the namespace in a browser window).'),
    'dispatcher': ('connect', "Cognos's address, when the one TM1 gives (its ClientCAMURI) isn't reachable from where tm1cm "
                              'runs: https://cognos.example.com/ibmcognos/bi/v1/disp.'),
    'browser': ('connect', "The path of a Chromium-based browser for signing in, when tm1cm doesn't find Chrome, Edge, Brave "
                           'or Chromium itself.'),
    'user': ('credentials', 'The user to log in as. Asked for when it isn\'t set and there\'s a terminal.'),
    'password': ('credentials', "The user's password. Leave it out and tm1cm asks for it, so it isn't kept in a file. "
                                'An empty password is tried first, for a user that has one.'),
    'namespace': ('credentials', "The CAM namespace to log in to, for a server in CAM security. Without one, tm1cm lists "
                                 "Cognos's namespaces to pick from."),
    'cam_passport': ('credentials', 'A CAM passport (the cam_passport cookie of a browser signed in to Cognos) to log in '
                                    'with. With base_url, it is all tm1cm needs. A passport expires.'),
    'gateway': ('credentials', "A CAM gateway's address, for Windows single sign-on. With the requests_negotiate_sspi "
                               'package installed it signs on directly; otherwise through the browser.'),
    'decode_b64': ('credentials', 'true when password is base64-encoded.'),
    'integrated_login': ('credentials', 'Not supported: Windows integrated security straight to TM1 (security mode 3). '
                                        'Refused, with what to use instead.'),
    'proxies': ('connect', 'Not supported: set HTTPS_PROXY (or HTTP_PROXY) in the environment instead.'),
    **{name: ('connect', "Accepted from TM1py's settings, and ignored: skipcheck-tm1 manages it.") for name in sorted(_IGNORED)},
}
SETTINGS = set(SETTING_DOCS)


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
            hint = tm1cm_errors.CERTIFICATE_HINT if tm1cm_errors._untrusted(e) else tm1cm_errors.UNREACHABLE_HINT
            raise tm1cm_errors.ServerUnreachable(f"Couldn't reach TM1 at {root}: {e.__cause__ or e}", hint) from e
        except errors.Tm1ApiError as e:
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


def dimension_exists(tm1, name):
    return exists(lambda: tm1.client.dimensions.get(name, names_query()))


def hierarchy_exists(tm1, dimension, hierarchy):
    return exists(lambda: tm1.client.hierarchies.get(dimension, hierarchy, names_query()))


def create_dimension(tm1, item):
    tm1.client.dimensions.create(dimension_body(item))


def create_hierarchy(tm1, dimension, item):
    tm1.client.hierarchies.create(dimension, hierarchy_body(item))


def update_structure(tm1, dimension, hierarchy, body):
    """Writes a hierarchy's Elements and Edges, as given: TM1 deletes what isn't listed.

    With only one of them (the other filtered out), the other is written back as the hierarchy has
    it: TM1 deletes a hierarchy's edges on a PATCH of its elements alone. Of the edges it has, those
    between elements still listed, since TM1 deletes the rest's elements."""
    elements = body.get('Elements')
    if elements is None:
        elements = odata(tm1.client.elements.list(dimension, hierarchy, ODataQuery.of(None, select='Name,Type')))
    edges = body.get('Edges')
    if edges is None:
        listed = {_lower_and_drop_spaces(e['Name']) for e in elements}
        edges = [e for e in odata(tm1.client.edges.list(dimension, hierarchy, ODataQuery.of(None, select='ParentName,ComponentName,Weight')))
                 if _lower_and_drop_spaces(e['ParentName']) in listed and _lower_and_drop_spaces(e['ComponentName']) in listed]
    tm1.client.hierarchies.replace_structure(dimension, hierarchy, elements, edges)


def element_names(tm1, dimension, hierarchy):
    return [e.name for e in tm1.client.elements.list(dimension, hierarchy, names_query())]


def has_elements(tm1, dimension, hierarchy):
    return bool(tm1.client.elements.list(dimension, hierarchy, names_query(top=1)))


def element_attributes(tm1, dimension, hierarchy):
    """(name, type) of each element attribute."""
    attributes = odata(tm1.client.attributes.list(AttributeSet.elements(dimension, hierarchy)))
    return [(a['Name'], a['Type']) for a in attributes]


def create_element(tm1, dimension, hierarchy, name, element_type):
    tm1.client.elements.create(dimension, hierarchy, {'Name': name, 'Type': element_type})


def delete_element(tm1, dimension, hierarchy, name):
    tm1.client.elements.delete(dimension, hierarchy, name)


def create_element_attribute(tm1, dimension, hierarchy, name, attribute_type):
    tm1.client.attributes.create(AttributeSet.elements(dimension, hierarchy), {'Name': name, 'Type': attribute_type})


def delete_element_attribute(tm1, dimension, hierarchy, name):
    """As TM1py's: through the attributes dimension, and quietly if it isn't there."""
    attributes = '}ElementAttributes_'
    try:
        tm1.client.elements.delete(attributes + dimension, attributes + hierarchy, name)
    except NotFound:
        pass


# --- Cubes ---------------------------------------------------------------------------------------

def cube_exists(tm1, name):
    return exists(lambda: tm1.client.cubes.get(name, names_query()))


def cube_dimensions(tm1, cube):
    dimensions = [d.name for d in tm1.client.cubes.dimensions(cube, names_query())]
    # As TM1py: a server with EnableSandboxDimension=T lists Sandboxes first, which isn't the cube's own
    if dimensions and _lower_and_drop_spaces(dimensions[0]) == 'sandboxes':
        dimensions = dimensions[1:]
    return dimensions


def create_cube(tm1, item):
    """A cube as TM1py's Cube.body wrote it."""
    dimensions = ODataPath.of('Dimensions')
    body = {'Name': item['Name'], 'Dimensions@odata.bind': [str(dimensions.key(d['Name'])) for d in item['Dimensions']]}
    if item.get('Rules'):
        body['Rules'] = item['Rules']
    tm1.client.cubes.create(body)


def update_rules(tm1, cube, rules):
    tm1.client.cubes.update(cube, {'Rules': rules})


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
    if int(version.split('.')[0]) < 11:
        # TM1 10 doesn't know parameter types
        body['Parameters'] = [{k: v for k, v in p.items() if k != 'Type'} for p in body['Parameters']]
    return body


def process_exists(tm1, name):
    return exists(lambda: tm1.client.processes.get(name, names_query()))


def create_or_update_process(tm1, item):
    body = process_body(item, tm1.version)
    if process_exists(tm1, item['Name']):
        tm1.client.processes.update(item['Name'], body)
    else:
        tm1.client.processes.create(body)


def execute_process(tm1, name):
    tm1.client.processes.execute(name)


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


_DURATION = re.compile(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?\Z')


def frequency(text):
    """A chore's Frequency as a timedelta, from either form it's written in: TM1's own
    (P01DT00H00M00S, in files from before skipcheck-tm1's services read chores) or ISO 8601 as
    skipcheck-tm1 writes it (PT24H)."""
    match = _DURATION.match(text)
    if not match:
        raise ValueError(f'Not a chore frequency: {text!r}')
    days, hours, minutes, seconds = (float(part) if part else 0 for part in match.groups())
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def normalize_frequency(text):
    """A chore's Frequency as skipcheck-tm1 reads it from TM1 (PT24H), whichever form it's in, so
    a file from before the change compares equal to the server."""
    return duration(frequency(text)) if text else text


def _frequency(text):
    """TM1py's ChoreFrequency: days, hours, minutes and seconds, each zero-padded to 2 digits."""
    total = int(frequency(text).total_seconds())
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return 'P{}DT{}H{}M{}S'.format(*(str(p).zfill(2) for p in (days, hours, minutes, seconds)))


def _task_body(task):
    return {'Process@odata.bind': str(ODataPath.of('Processes').key(task['Process']['Name'])),
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


def chore_exists(tm1, name):
    return exists(lambda: tm1.client.chores.get(name, names_query()))


def create_or_update_chore(tm1, item):
    """As TM1py's ChoreService.update_or_create."""
    chores = tm1.client.chores
    name = item['Name']
    body = chore_body(item)
    if not chore_exists(tm1, name):
        # TM1 refuses SetServerLocalStartTime on an active chore: a DST-sensitive one is created
        # inactive, and activated at the end
        chores.create({**body, 'Active': False} if item['DSTSensitive'] else body)
        _set_start_time_and_activate(chores, name, item)
        return

    was_active = chores.get(name, ODataQuery.of(None, select='Name,Active')).active
    try:
        # Deactivated for the update, and activated again if it should be active
        chores.deactivate(name)
        # Without Active: it stays deactivated while its tasks and start time change, which TM1
        # refuses on an active chore, and is activated at the end if it should be
        chores.update(name, {k: v for k, v in body.items() if k not in ('Tasks', 'Active')})
        old_tasks = odata(chores.tasks(name, ODataQuery.of(None, expand='Process($select=Name)')))
        for step, task in enumerate(item['Tasks']):
            if step >= len(old_tasks):
                chores.add_task(name, _task_body(task))
                continue
            old = old_tasks[step]
            old_parameters = [{'Name': p['Name'], 'Value': p['Value']} for p in old['Parameters']]
            if old['Process']['Name'] != task['Process']['Name'] or old_parameters != _task_body(task)['Parameters']:
                chores.update_task(name, step, _task_body(task))
        for _ in range(len(item['Tasks']), len(old_tasks)):
            chores.delete_task(name, len(item['Tasks']))
        _set_start_time_and_activate(chores, name, item)
    except Exception:
        # A failure partway (a task whose process the target lacks, say) leaves the chore as
        # active as it was, not switched off with nothing to turn it on again
        if was_active:
            try:
                chores.activate(name)
            except Exception:
                logger.exception(f'Could not activate chore {name} again after its update failed')
        raise


def _set_start_time_and_activate(chores, name, item):
    if item['DSTSensitive']:
        moment, _ = _start_time(item['StartTime'])
        chores.set_server_local_start_time(name, moment.date(), moment.time())
    if item['Active']:
        chores.activate(name)


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


def _cellset_query(cell_properties):
    """What a cellset is read with: its cube's dimensions, its axes' members, and its cells."""
    return ODataQuery.of(None, expand=(
        'Cube($select=Name;$expand=Dimensions($select=Name)),'
        'Axes($expand=Tuples($expand=Members($select=UniqueName;$expand=Element($select=UniqueName)))),'
        f"Cells($select={','.join(cell_properties)})"))


def _cells(raw):
    """A cellset's cells, keyed by their elements' unique names in the cube's dimension order, as
    TM1py's execute_mdx and execute_view returned them."""
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


class Cellset:
    """An MDX query's cellset, left on TM1 while it's used: its :attr:`id`, and its :attr:`cells`
    (as :func:`execute_mdx` gives them). Deleted on leaving the with block."""

    def __init__(self, tm1, mdx, cell_properties):
        self._tm1 = tm1
        read = tm1.client.cellsets.execute(mdx, _cellset_query(cell_properties))
        self.id = read.id
        try:
            self.cells = _cells(odata(read))
        except Exception:
            self.close()
            raise

    def close(self):
        self._tm1.client.cellsets.delete(self.id)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def execute_mdx(tm1, mdx, cell_properties):
    with Cellset(tm1, mdx, cell_properties) as cellset:
        return cellset.cells


def execute_view(tm1, cube, view, cell_properties):
    read = tm1.client.cellsets.execute_view(cube, PUBLIC_VIEWS, view, _cellset_query(cell_properties))
    try:
        return _cells(odata(read))
    finally:
        tm1.client.cellsets.delete(read.id)


def execute_mdx_values(tm1, mdx):
    read = tm1.client.cellsets.execute(mdx, ODataQuery.of(None, expand='Cells($select=Value)'))
    try:
        return [cell['Value'] for cell in odata(read)['Cells']]
    finally:
        tm1.client.cellsets.delete(read.id)


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


def folder_path(path):
    """A folder under Applications, by its names joined with '/'."""
    folder = ContentPath.applications()
    for part in path.split('/'):
        if part.strip():
            folder = folder.child(part)
    return folder


def application_path(path, application_type, name):
    suffix, _ = APPLICATION_TYPES[application_type]
    return folder_path(path).child(name + suffix)


def application_exists(tm1, path, application_type, name):
    return exists(lambda: tm1.client.contents.get(application_path(path, application_type, name), names_query()))


def application_entries(tm1, path):
    """The entries in a folder under Applications, as TM1's JSON (@odata.type, ID, Name …)."""
    return odata(tm1.client.contents.contents(folder_path(path), PUBLIC_CONTENTS))


def applications(tm1):
    """The names of the folders at the top of Applications."""
    return [e.name for e in tm1.client.elements.components('}ApplicationEntries', '}ApplicationEntries', '}applications', names_query())]


def get_application(tm1, path, application_type, name):
    """An application entry, as TM1py's application objects gave it: its body (@odata.type, Name,
    and its reference or URL), and a document's content."""
    contents = tm1.client.contents
    entry = application_path(path, application_type, name)
    _, odata_type = APPLICATION_TYPES[application_type]
    body = {'@odata.type': odata_type, 'Name': name}
    content = None
    if application_type == 'DOCUMENT':
        content = contents.content(entry)
        contents.document(entry)
    elif application_type == 'FOLDER':
        contents.get(entry)
    elif application_type == 'LINK':
        body['URL'] = odata(contents.get(entry))['URL']
    elif application_type == 'SUBSET':
        query = ODataQuery.of(None, expand='Subset($select=Name;$expand=Hierarchy($select=Name;$expand=Dimension($select=Name)))')
        subset = odata(contents.get(entry, query))['Subset']
        body['Subset@odata.bind'] = str(ODataPath.of('Dimensions').key(subset['Hierarchy']['Dimension']['Name'])
                                        .nav('Hierarchies').key(subset['Hierarchy']['Name']).nav('Subsets').key(subset['Name']))
    elif application_type == 'VIEW':
        query = ODataQuery.of(None, expand='View($select=Name;$expand=Cube($select=Name))')
        view = odata(contents.get(entry, query))['View']
        body['View@odata.bind'] = str(ODataPath.of('Cubes').key(view['Cube']['Name']).nav('Views').key(view['Name']))
    else:
        reference = {'CHORE': ('Chore', 'Chores'), 'CUBE': ('Cube', 'Cubes'), 'DIMENSION': ('Dimension', 'Dimensions'),
                     'PROCESS': ('Process', 'Processes')}[application_type]
        target = odata(contents.get(entry, ODataQuery.of(None, expand=f'{reference[0]}($select=Name)')))[reference[0]]['Name']
        body[reference[0] + '@odata.bind'] = str(ODataPath.of(reference[1]).key(target))
    return body, content


def create_application(tm1, path, body, content=None):
    """Creates an entry from its body; a document's content goes in a second request."""
    folder = folder_path(path)
    tm1.client.contents.create(folder, PUBLIC_CONTENTS, body)
    if body['@odata.type'] == APPLICATION_TYPES['DOCUMENT'][1]:
        tm1.client.contents.upload(folder.child(body['Name'] + '.blob'), content)


def delete_application(tm1, path, application_type, name):
    tm1.client.contents.delete(application_path(path, application_type, name))


def rename_application(tm1, path, application_type, name, new_name):
    tm1.client.contents.move(application_path(path, application_type, name), folder_path(path), PUBLIC_CONTENTS, new_name)
