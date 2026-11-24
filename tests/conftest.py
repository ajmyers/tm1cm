import pytest


@pytest.fixture(autouse=True)
def error_reports(tmp_path, monkeypatch):
    """Error reports go to the test's own folder, not a temporary file of their own."""
    from tm1cm import errors

    path = tmp_path / 'tm1cm-error-report.log'

    def report(error):
        with open(path, 'a', encoding='utf-8') as fp:
            fp.write(errors.report_text(error) + '\n')
        return str(path)

    monkeypatch.setattr(errors, 'report', report)
    # Each test's own secrets and servers: another's password must not be masked in this one's text
    monkeypatch.setattr(errors, '_secrets', set())
    monkeypatch.setattr(errors, '_servers', {})
    return path


@pytest.fixture(scope='session')
def tm1_connection(tm1_server):
    """Connection settings for the shared TM1 container, as connect.yaml and credentials.yaml hold them.

    tm1_server, from skipcheck-tm1-testcontainers, starts one TM1 server in Docker for the whole
    session, and skips the test when Docker or a TM1 source isn't available. tm1cm adds /api/v1
    to base_url itself, as TM1py did, so it gets the server's root rather than its REST URL.
    """
    rest_url = tm1_server.rest_url.rstrip('/')
    return {
        'base_url': rest_url.removesuffix('/api/v1'),
        'user': tm1_server.username,
        'password': tm1_server.password,
    }
