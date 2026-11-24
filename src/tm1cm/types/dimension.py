import copy
import json
import logging
import urllib.parse

from tm1cm import tm1 as tm1_client
from tm1cm.types.base import Base


class Dimension(Base):

    def __init__(self, config, app=None):
        self.type = 'dimension'
        super().__init__(config, app)

    def _list_remote(self, app):
        rest = app.session.rest

        request = '/api/v1/Dimensions?$select=Name'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    def _get_remote(self, app, items):
        filter = ['Name eq \'' + urllib.parse.quote(item, safe='') + '\'' for item in items]
        request = '/api/v1/Dimensions?$select=Name&$filter='

        results = self._do_filter_request(app, request, filter)
        results = {result['Name']: result for result in results}
        results = [(item, results[item]) for item in items]

        for name, item in results:
            yield name, self._transform_from_remote(name, item)

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        if not session.rest.exists(f"/api/v1/Dimensions('{tm1_client.key(name)}')"):
            tm1_client.create_dimension(session, item)

    def _delete_remote(self, app, name):
        session = app.session

        url = f"/api/v1/Dimensions('{tm1_client.key(name)}')"
        if session.rest.exists(url):
            session.rest.DELETE(url)

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)
        item.setdefault('Hierarchies', [])
        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        if item is None:
            item = {}
        item['Name'] = name
        return item

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']

        return item


logger = logging.getLogger(Dimension.__name__)
