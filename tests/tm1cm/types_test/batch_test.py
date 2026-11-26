import pytest

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm import tm1 as tm1_client
from tm1cm.application import RemoteApplication

# Enough long names that getting them all needs several requests
MANY = [f'tm1cmBatch_{i:04d}_' + 'x' * 30 for i in range(250)]
# Characters TM1 allows in object names that need URL-encoding (TM1 refuses ' in a dimension's)
ODD = ['tm1cmOdd A&B', 'tm1cmOdd #1', 'tm1cmOdd 1+1', 'tm1cmOdd Ümlaut', 'tm1cmOdd 50%']


class _Read:
    """A service's list, recording the query strings it was called with."""

    def __init__(self):
        self.queries = []

    def __call__(self, query):
        text = query.to_query_string()
        self.queries.append(text)
        return [text]


def test_filter_request_batches_under_the_url_limit():
    read = _Read()

    results = tm1_client.filtered(read, tm1_client.names_query(), MANY)

    assert len(read.queries) > 1
    assert all(len(query) <= tm1_client.MAX_URL for query in read.queries)
    # Each name asked for once, in one request
    for name in MANY:
        assert sum(query.count(f"'{name}'") for query in read.queries) == 1, name
    assert results == read.queries


def test_filter_request_single_batch():
    read = _Read()

    tm1_client.filtered(read, tm1_client.names_query(), ['a', "b'c"])

    assert read.queries == ["$select=Name&$filter=((Name%20eq%20'a')%20or%20(Name%20eq%20'b''c'))"]


def test_filter_request_nothing_to_get():
    read = _Read()

    assert tm1_client.filtered(read, tm1_client.names_query(), []) == []
    assert read.queries == []


@pytest.mark.requires_tm1
def test_get_many_and_odd_names_from_tm1(tm1_connection):
    """Every object comes back when a get needs several requests, and names needing encoding work."""
    remote = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    session = remote.session
    names = MANY + ODD
    for name in names:
        tm1_objects.create_dimension(session, name, ['a'])
    try:
        listed = [name for name in remote.dimensions.list(remote) if name in names]
        assert sorted(listed) == sorted(names)

        got = dict(remote.dimensions.get(listed, remote))
        assert sorted(got) == sorted(names)
    finally:
        for name in names:
            tm1_objects.delete_dimension(session, name)
