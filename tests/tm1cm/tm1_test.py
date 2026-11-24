"""tm1cm.tm1: TM1py's connection settings, resolved as TM1py resolved them, without a server."""
import pytest

from tm1cm import tm1
from tm1cm.errors import ConfigError


def _settings(**kwargs):
    builder, root, async_requests = tm1.session_builder(**kwargs)
    return {key: repr(value) for key, value in builder.settings().items()}, root, async_requests


@pytest.mark.parametrize('kwargs, root', [
    ({'base_url': 'https://host:10000'}, 'https://host:10000'),
    ({'base_url': 'https://host:10000/'}, 'https://host:10000'),
    ({'base_url': 'https://co.planning-analytics.ibmcloud.com:443/tm1/api/tm1'}, 'https://co.planning-analytics.ibmcloud.com:443/tm1/api/tm1'),
    ({'address': 'tm1', 'port': 8001}, 'https://tm1:8001'),
    ({'address': 'tm1', 'port': 8001, 'ssl': False}, 'http://tm1:8001'),
    ({'address': 'tm1', 'port': 8001, 'ssl': 'False'}, 'http://tm1:8001'),
    ({'address': '', 'port': 8001, 'ssl': True}, 'https://localhost:8001'),
], ids=['base_url', 'trailing slash', 'IBM Cloud', 'address and port', 'ssl off', 'ssl off as text', 'no address'])
def test_requests_go_to_the_root_plus_api_v1(kwargs, root):
    settings, got_root, _ = _settings(**kwargs)

    assert got_root == root
    assert settings['base_url'] == repr(root + '/api/v1/')


@pytest.mark.parametrize('kwargs, authenticator', [
    ({'user': 'admin', 'password': 'apple'}, 'Basic admin'),
    ({'user': 'admin', 'password': 'apple', 'namespace': 'LDAP'}, 'CAMNamespace LDAP/admin'),
    ({'cam_passport': 'abc'}, 'CAMPassport'),
], ids=['TM1 security', 'CAM', 'CAM passport'])
def test_authentication(kwargs, authenticator):
    settings, _, _ = _settings(base_url='https://host:1', **kwargs)

    assert authenticator in settings['authenticator']


@pytest.mark.parametrize('verify, expected', [
    (None, False), (True, True), (False, False), ('True', True), ('false', False), ('/certs/ca.pem', '/certs/ca.pem'),
], ids=['unset: not checked, as TM1py', 'True', 'False', "'True'", "'false'", 'CA bundle'])
def test_verify(verify, expected):
    kwargs = {'base_url': 'https://host:1'} if verify is None else {'base_url': 'https://host:1', 'verify': verify}
    settings, _, _ = _settings(**kwargs)

    assert settings['verify'] == repr(expected)


def test_base64_password():
    assert tm1._password({'password': 'YXBwbGU=', 'decode_b64': True}) == 'apple'
    assert tm1._password({'password': 'YXBwbGU='}) == 'YXBwbGU='


def test_session_context_and_async():
    settings, _, async_requests = _settings(base_url='https://host:1', session_context='Nightly', async_requests_mode='True')

    assert settings['session_context'] == repr('Nightly')
    assert async_requests is True
    assert _settings(base_url='https://host:1')[0]['session_context'] == repr('tm1cm')


def test_timeout():
    settings, _, _ = _settings(base_url='https://host:1', timeout=120)

    assert 'request=120.0' in settings['timeouts']


@pytest.mark.parametrize('kwargs', [{'integrated_login': True}, {'integrated_login': 'True'}, {'proxies': {'https': 'http://proxy'}}])
def test_unsupported_settings_are_refused(kwargs):
    with pytest.raises(ConfigError):
        tm1.session_builder(base_url='https://host:1', **kwargs)


def test_ignored_settings_are_accepted():
    tm1.session_builder(base_url='https://host:1', tcp_keepalive=True, connection_pool_size=4, re_connect_on_session_timeout=True)


def test_no_server_is_refused():
    with pytest.raises(ConfigError, match='No TM1 server'):
        tm1.session_builder(base_url='', user='admin')


def test_key():
    assert tm1.key("Men's 50% #1") == 'Men%27%27s%2050%25%20%231'


def test_cells_dict_ignores_case_and_spaces():
    cells = tm1.CaseAndSpaceInsensitiveTuplesDict()
    cells[('[Region].[Region].[North America]',)] = 1

    assert cells[('[region].[region].[northamerica]',)] == 1
    assert list(cells) == [('[Region].[Region].[North America]',)]


@pytest.mark.parametrize('start_time, written', [
    ('2022-02-13T20:00Z', '2022-02-13T20:00Z'),
    ('2022-02-13T20:00:00+00:00', '2022-02-13T20:00+00:00'),
    ('2022-02-13T20:00:30-05:00', '2022-02-13T20:00:30-05:00'),
])
def test_chore_start_time_as_tm1py_wrote_it(start_time, written):
    assert tm1._start_time(start_time)[1] == written


def test_chore_frequency_as_tm1py_wrote_it():
    assert tm1._frequency('P1DT2H3M4S') == 'P01DT02H03M04S'
