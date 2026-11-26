"""A TM1 in CAM security, through Cognos and Keycloak, for the live CAM tests (live_cam_test).

The settings come from the environment when TM1_CAM_URL is set, for a stack started some other way
(see live_cam_test). Otherwise skipcheck-tm1-testcontainers starts one: Keycloak, Cognos with an
LDAP and an OIDC namespace holding the same test user, and a TM1 in CAM security through the OIDC
namespace. That needs Docker, a TM1 source and a Cognos source (COGNOS_PRIVATE_IMAGE,
COGNOS_INSTALL_VOLUME, COGNOS_ZIP_DIR or COGNOS_ZIP_URL); without them the tests skip.

Cognos takes minutes to start and holds about 8 GB. With TESTCONTAINERS_REUSE_ENABLE=true the stack
is left running and found again by the next run.
"""
import os
import socket
from dataclasses import dataclass
from dataclasses import field

USER = 'admin'
PASSWORD = 'adminpw'
# The port Cognos is published on when the stack is reused: it's part of the stack's configuration,
# so a reused stack has to have the same one every run
REUSED_COGNOS_PORT = 19390


@dataclass(frozen=True)
class CamStack:
    rest_url: str
    namespace: str
    user: str
    password: str
    dispatcher: str = ''
    password_namespace: str = ''
    password_user: str = ''
    password_password: str = ''
    # Extra arguments for the browser, so it reaches what only the Docker network can name
    browser_args: list = field(default_factory=list)

    @property
    def root(self):
        """TM1's root, without /api/v1, as connect.yaml's base_url holds it."""
        return self.rest_url.rstrip('/').removesuffix('/api/v1')


SETTINGS = ['TM1_CAM_URL', 'CAM_NAMESPACE', 'CAM_USER', 'CAM_PASSWORD']


def from_environment():
    """The stack the environment names, or None when TM1_CAM_URL isn't set."""
    if not os.environ.get('TM1_CAM_URL'):
        return None
    missing = [s for s in SETTINGS if not os.environ.get(s)]
    if missing:
        raise RuntimeError('TM1_CAM_URL is set, but not ' + ', '.join(missing))
    return CamStack(
        rest_url=os.environ['TM1_CAM_URL'], namespace=os.environ['CAM_NAMESPACE'],
        user=os.environ['CAM_USER'], password=os.environ['CAM_PASSWORD'],
        dispatcher=os.environ.get('COGNOS_URL', ''),
        password_namespace=os.environ.get('CAM_PASSWORD_NAMESPACE', ''),
        password_user=os.environ.get('CAM_PASSWORD_USER', ''),
        password_password=os.environ.get('CAM_PASSWORD_PASSWORD', ''))


def skip_reason():
    """Why no stack can be started here, or None when one can."""
    from skipcheck_tm1_testcontainers.plugin import cognos_skip_reason
    return cognos_skip_reason()


def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def environment():
    """The stack, built but not started."""
    from skipcheck_tm1_testcontainers import Namespace
    from skipcheck_tm1_testcontainers import PlanningAnalyticsEnvironment
    from skipcheck_tm1_testcontainers import reuse_enabled

    # Keycloak sends the browser back to Cognos at COGNOS_PUBLIC_URL, which has to be known before
    # Cognos starts: so Cognos gets a port of our choosing, not a random one
    port = REUSED_COGNOS_PORT if reuse_enabled() else _free_port()

    def cognos(container):
        container.with_user(USER, PASSWORD, 'Admins')
        container.with_bind_ports(container.DISPATCHER_PORT, port)
        container.with_env('COGNOS_PUBLIC_URL', f'http://localhost:{port}')

    return (PlanningAnalyticsEnvironment.builder()
            .cognos(cognos)
            .keycloak()
            .tm1('tm1cmCam')
            .cam_security(Namespace.OIDC, USER)
            .reuse(True)
            .build())


def started(env):
    """The settings of a started stack."""
    keycloak = env.keycloak()
    cognos = env.cognos()
    tm1 = env.tm1('tm1cmCam')
    host_keycloak = keycloak.url.removeprefix('http://')
    network_keycloak = keycloak.network_url.removeprefix('http://').split(':')[0]
    return CamStack(
        rest_url=tm1.rest_url, namespace='OIDC', user=USER, password=PASSWORD,
        dispatcher=cognos.url.rstrip('/').removesuffix('/bi'),
        password_namespace='LDAP', password_user=USER, password_password=PASSWORD,
        # Keycloak's issuer, and so its sign-in page, is http://keycloak:8080, the name Cognos
        # reaches it by: the browser is told to find that name on this machine's port for it
        browser_args=[f'--host-resolver-rules=MAP {network_keycloak} {host_keycloak}'])
