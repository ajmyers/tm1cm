"""tm1cm.discovery, against a mock TM1 and Cognos that answer as the real ones did (Cognos 12.1.1,
TM1 11.8 in CAM security: skipcheck-tm1's pa-setup)."""
import httpx2
import pytest

from tm1cm import discovery

LDAP_PROMPT = {'promptInfo': {'displayObjects': [
    {'name': 'CAMNamespace', 'type': 'hidden', 'value': 'LDAP'},
    {'name': 'CAMUsername', 'type': 'text'}, {'name': 'CAMPassword', 'type': 'textnoecho'}]}}
OIDC_PROMPT = {'promptInfo': {'displayObjects': [
    {'name': 'camRedirectURL', 'type': 'redirect', 'value': 'http://idp/auth?client_id=cognos'},
    {'name': 'CAMNamespace', 'type': 'hidden', 'value': 'OIDC'}]}}
NAMESPACES = {'promptInfo': {'displayObjects': [{'name': 'CAMNamespace', 'type': 'singleselect', 'promptOptions': [
    {'isDefault': False, 'value': 'LDAP'}, {'isDefault': True, 'value': 'OIDC'}]}]}}


def mock(cam=True, dispatcher='http://cognos:9300/bi/v1/disp'):
    """TM1 at tm1:8010 (CAM security, or its own), and Cognos at cognos:9300 with an LDAP namespace
    that prompts for a password and an OIDC one that signs in in the browser."""
    def handler(request):
        url = str(request.url)
        if request.url.host == 'tm1':
            headers = [('WWW-Authenticate', f'CAMPassport {dispatcher}'),
                       ('WWW-Authenticate', 'CAMNamespace')] if cam else [('WWW-Authenticate', 'Basic realm="TM1"')]
            return httpx2.Response(401, headers=headers)
        if url.endswith('/bi/v1/login'):
            return httpx2.Response(441, json=NAMESPACES)
        if 'CAMNamespace=LDAP' in url:
            return httpx2.Response(441, json=LDAP_PROMPT)
        if 'CAMNamespace=OIDC' in url:
            return httpx2.Response(441, json=OIDC_PROMPT)
        return httpx2.Response(404)
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_reads_tm1s_challenge():
    assert discovery.challenge('http://tm1:8010', http=mock(cam=False)) == discovery.Challenge('basic')
    assert discovery.challenge('http://tm1:8010/', http=mock()) == discovery.Challenge('cam', 'http://cognos:9300/bi/v1/disp')


def test_cam_without_an_address_is_still_cam():
    client = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(401, headers=[('WWW-Authenticate', 'CAMNamespace')])))

    assert discovery.challenge('http://tm1:8010', http=client) == discovery.Challenge('cam')


def test_a_server_that_isnt_tm1_is_said():
    client = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200, text='hello')))

    with pytest.raises(discovery.DiscoveryError, match='is it TM1'):
        discovery.challenge('http://web:80', http=client)


def test_lists_cognos_namespaces_default_first_and_how_each_logs_on():
    client = mock()
    assert discovery.namespaces('http://cognos:9300/bi/v1/disp', http=client) == ['OIDC', 'LDAP']
    assert discovery.login_kind('http://cognos:9300/bi/v1/disp', 'LDAP', http=client) == 'password'
    assert discovery.login_kind('http://cognos:9300/bi/v1/disp', 'OIDC', http=client) == 'browser'


def test_a_server_that_isnt_cognos_is_said():
    client = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(404, text='<html>')))

    with pytest.raises(discovery.DiscoveryError, match='not a Cognos login'):
        discovery.namespaces('http://web/bi', http=client)


@pytest.mark.parametrize('given, root', [
    ('http://c:9300/bi/v1/disp', 'http://c:9300/bi'),
    ('https://c/ibmcognos/bi/v1/disp', 'https://c/ibmcognos/bi'),
    ('https://c/ibmcognos/cgi-bin/cognos.cgi', 'https://c/ibmcognos/bi'),
    ('https://c/ibmcognos/cgi-bin/cognosisapi.dll', 'https://c/ibmcognos/bi'),
    ('http://c:9300/p2pd/servlet/dispatch', 'http://c:9300/bi'),
    ('http://c:9300', 'http://c:9300/bi'),
])
def test_finds_cognos_from_each_form_of_clientcamuri(given, root):
    assert discovery.cognos_root(given) == root


def test_login_addresses():
    assert discovery.browser_login_url('http://c:9300/bi/v1/disp', 'My OIDC') == 'http://c:9300/bi/?CAMNamespace=My%20OIDC'
    assert discovery.gateway_login_url('https://c/cgi-bin/cognos.cgi', 'AD') == 'https://c/cgi-bin/cognos.cgi?CAMNamespace=AD'
    assert discovery.gateway_login_url('https://c/gw?x=1', 'AD') == 'https://c/gw?x=1&CAMNamespace=AD'
    assert discovery.gateway_login_url('https://c/gw', '') == 'https://c/gw'


def test_challenges_merged_into_one_header():
    def handler(request):
        return httpx2.Response(401, headers=[('WWW-Authenticate', 'CAMPassport http://host/ibmcognos/cgi-bin/cognos.cgi, CAMNamespace')])
    http = httpx2.Client(transport=httpx2.MockTransport(handler))

    assert discovery.challenge('http://tm1:8010', http=http) == discovery.Challenge('cam', 'http://host/ibmcognos/cgi-bin/cognos.cgi')
