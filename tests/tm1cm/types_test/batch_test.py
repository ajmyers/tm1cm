import json

import pytest
from TM1py.Objects import Dimension
from TM1py.Objects import Element
from TM1py.Objects import Hierarchy

from tests.tm1cm import util
from tm1cm.application import RemoteApplication
from tm1cm.types.base import Base

# Enough long names that getting them all needs several requests
MANY = [f'tm1cmBatch_{i:04d}_' + 'x' * 30 for i in range(250)]
# Characters TM1 allows in object names that need URL-encoding
ODD = ['tm1cmOdd A&B', 'tm1cmOdd #1', 'tm1cmOdd 1+1', 'tm1cmOdd Ümlaut', 'tm1cmOdd 50%']


class _Rest:
    def __init__(self, filters):
        self.filters = filters
        self.requests = []

    def GET(self, url):
        self.requests.append(url)
        found = [f for f in self.filters if f in url]

        class Response:
            text = json.dumps({'value': found})
        return Response()


class _App:
    def __init__(self, rest):
        self.session = type('Session', (), {'_tm1_rest': rest})()


def test_filter_request_batches_under_the_url_limit():
    filters = [f"Name eq '{name}'" for name in MANY]
    rest = _Rest(filters)

    results = list(Base._do_filter_request(_App(rest), '/api/v1/Dimensions?$filter=', filters))

    assert len(rest.requests) > 1
    assert all(len(url) <= 6000 for url in rest.requests)
    # Each filter asked for once, in one request, and its result yielded once
    assert sorted(results) == sorted(filters)
    for f in filters:
        assert sum(url.count(f) for url in rest.requests) == 1, f


def test_filter_request_single_batch():
    filters = ["Name eq 'a'", "Name eq 'b'"]
    rest = _Rest(filters)

    results = list(Base._do_filter_request(_App(rest), '/api/v1/Dimensions?$filter=', filters))

    assert rest.requests == ["/api/v1/Dimensions?$filter=Name eq 'a' or Name eq 'b'"]
    assert results == filters


def test_filter_request_nothing_to_get():
    rest = _Rest([])

    assert list(Base._do_filter_request(_App(rest), '/api/v1/Dimensions?$filter=', [])) == []
    assert rest.requests == []


@pytest.mark.requires_tm1
def test_get_many_and_odd_names_from_tm1(tm1_connection):
    """Every object comes back when a get needs several requests, and names needing encoding work."""
    remote = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    session = remote.session
    names = MANY + ODD
    for name in names:
        session.dimensions.create(Dimension(name, [Hierarchy(name, name, elements=[Element('a', 'Numeric')])]))
    try:
        listed = [name for name in remote.dimensions.list(remote) if name in names]
        assert sorted(listed) == sorted(names)

        got = dict(remote.dimensions.get(listed, remote))
        assert sorted(got) == sorted(names)
    finally:
        for name in names:
            session.dimensions.delete(name)
