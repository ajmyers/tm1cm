"""Working out how a TM1 server wants to be logged in to, asking only the servers.

Ported from Sublime-TM1 (core/discovery.py). Everything here is unauthenticated: no credentials go
into a probe. Each step asks a server something it tells anyone:

- TM1's 401 says how it wants to be logged in to: WWW-Authenticate Basic (TM1's own security), or
  CAMPassport with Cognos's address (its ClientCAMURI) and CAMNamespace (CAM security);
- Cognos's login lists its namespaces, and for each, either the user and password it prompts for,
  or the redirect a browser follows to sign in (OpenID Connect, SAML...).
"""
import re
from dataclasses import dataclass
from urllib.parse import quote

TIMEOUT = 10


class DiscoveryError(Exception):
    """A server didn't answer as TM1 or Cognos would."""


@dataclass(frozen=True)
class Challenge:
    # "basic" (TM1's own security) or "cam"
    kind: str
    # Cognos's address as TM1 gives it (ClientCAMURI), for "cam"
    dispatcher: str = ''


def client(verify=True):
    import httpx2

    return httpx2.Client(verify=verify, timeout=TIMEOUT, follow_redirects=False)


def challenge(root, verify=True, http=None):
    """How TM1 at ``root`` (its address, without /api/v1) asks to be logged in to, from the
    WWW-Authenticate headers of its 401. Transport errors (nothing listening, a certificate that
    isn't trusted) are raised as they are."""
    response = (http or client(verify)).get(root.rstrip('/') + '/api/v1/Configuration/ServerName')
    headers = response.headers.get_list('www-authenticate') if hasattr(response.headers, 'get_list') else \
        [response.headers.get('www-authenticate', '')]
    for header in headers:
        match = re.match(r'\s*CAMPassport\s+([^\s,]+)', header, re.IGNORECASE)
        if match:
            return Challenge('cam', match.group(1))
    if any(h.strip().lower().startswith('campassport') or h.strip().lower() == 'camnamespace' for h in headers):
        return Challenge('cam')
    if response.status_code in (401, 403) or any(h.strip().lower().startswith('basic') for h in headers):
        return Challenge('basic')
    raise DiscoveryError(f'{root} answered {response.status_code} without saying how to log in: is it TM1?')


def cognos_root(dispatcher):
    """Cognos's web root (ending in /bi) from the forms a ClientCAMURI takes: .../bi/v1/disp,
    .../bi, a gateway's .../cgi-bin/cognos.cgi, or a dispatcher's .../p2pd/servlet/dispatch."""
    url = dispatcher.rstrip('/')
    match = re.match(r'(.*?/bi)(/.*)?$', url)
    if match:
        return match.group(1)
    match = re.match(r'(.*)/cgi-bin/cognos(isapi)?\.(cgi|dll)$', url, re.IGNORECASE)
    if match:
        return match.group(1) + '/bi'
    match = re.match(r'(.*)/p2pd(/.*)?$', url)
    if match:
        return match.group(1) + '/bi'
    return url + '/bi'


def _login(dispatcher, query, verify, http):
    response = (http or client(verify)).get(cognos_root(dispatcher) + '/v1/login', params=query)
    try:
        return response.json().get('promptInfo', {}).get('displayObjects', [])
    except ValueError as e:
        raise DiscoveryError(f'{cognos_root(dispatcher)} is not a Cognos login (HTTP {response.status_code})') from e


def namespaces(dispatcher, verify=True, http=None):
    """Cognos's namespaces, the default first."""
    for item in _login(dispatcher, {}, verify, http):
        if item.get('name') == 'CAMNamespace':
            if item.get('type') == 'hidden':
                return [item.get('value')]
            options = item.get('promptOptions') or []
            return [o['value'] for o in sorted(options, key=lambda o: not o.get('isDefault'))]
    return []


def login_kind(dispatcher, namespace, verify=True, http=None):
    """How the namespace logs a user on: "password" (Cognos prompts for a user and password) or
    "browser" (it sends the browser to sign in elsewhere: OIDC, SAML...)."""
    items = _login(dispatcher, {'CAMNamespace': namespace}, verify, http)
    names = {item.get('name') for item in items}
    if any(item.get('type') == 'redirect' for item in items):
        return 'browser'
    if {'CAMUsername', 'CAMPassword'} <= names:
        return 'password'
    return 'browser'


def browser_login_url(dispatcher, namespace):
    """Where a browser signs in to the namespace, ending at Cognos with its cam_passport set."""
    return cognos_root(dispatcher) + '/?CAMNamespace=' + quote(namespace)


def gateway_login_url(gateway, namespace):
    """A CAM gateway's address for the namespace, as TM1py asked it for a passport."""
    if not namespace:
        return gateway
    return gateway + ('&' if '?' in gateway else '?') + 'CAMNamespace=' + quote(namespace)
