import pytest


@pytest.fixture(scope='session')
def tm1_connection(tm1_server):
    """TM1py connection settings (TM1Service keyword arguments) for the shared TM1 container.

    tm1_server, from skipcheck-tm1-testcontainers, starts one TM1 server in Docker for the whole
    session, and skips the test when Docker or a TM1 source isn't available. TM1py adds /api/v1
    to base_url itself, so it gets the server's root rather than its REST URL.
    """
    rest_url = tm1_server.rest_url.rstrip('/')
    return {
        'base_url': rest_url.removesuffix('/api/v1'),
        'user': tm1_server.username,
        'password': tm1_server.password,
    }
