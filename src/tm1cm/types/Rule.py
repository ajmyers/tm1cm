import json
import logging
import os
import urllib.parse

from TM1py.Objects.Rules import Rules as TM1PyRules

from tm1cm.types.base import Base


class Rule(Base):

    def __init__(self, config, app=None):
        self.type = 'rule'
        super().__init__(config, app)

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Cubes?$select=Name&$filter=Rules ne null'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    def _get_local(self, app, items):

        files = [os.path.join(app.path, self.path, item + self.ext) for item in items]

        for name, file in zip(items, files):
            with open(file, 'r') as fp:
                result = fp.read()

            yield name, self._transform_from_local(name, result)

    def _get_remote(self, app, items):
        filter = ['Name eq \'' + urllib.parse.quote(item, safe='') + '\'' for item in items]
        request = '/api/v1/Cubes?$select=Name,Rules&$filter='

        results = self._do_filter_request(app, request, filter)
        results = {result['Name']: result for result in results}
        results = [(item, results[item]['Rules']) for item in items]

        for name, result in results:
            yield name, self._transform_from_remote(name, result)

    def _update_local(self, app, name, item):
        path = os.path.join(app.path, self.path, name + self.ext)
        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(name, item)

        with open(path, 'w') as fp:
            fp.write(item)

    def _update_remote(self, app, name, item):
        session = app.session
        item = self._transform_to_remote(name, item)

        if session.cubes.exists(name):
            cube = session.cubes.get(name)
            cube.rules = TM1PyRules(item)
            session.cubes.update(cube)

    def _delete_remote(self, app, name):
        session = app.session

        if session.cubes.exists(name):
            empty_rule = TM1PyRules('')
            cube = session.cubes.get(name)
            cube.rules = empty_rule
            session.cubes.update(cube)

    def _transform_from_remote(self, name, item):
        if not item:
            return ''
        else:
            return item


logger = logging.getLogger(Rule.__name__)
