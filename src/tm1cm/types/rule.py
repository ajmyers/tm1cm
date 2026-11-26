import logging
import os

from tm1cm import tm1 as tm1_client
from tm1cm.types.base import Base


class Rule(Base):

    def __init__(self, config, app=None):
        self.type = 'rule'
        super().__init__(config, app)

    def _list_remote(self, app):
        cubes = app.session.client.cubes.list(tm1_client.names_query(filter='Rules ne null'))

        return sorted([cube.name for cube in cubes])

    def _get_local(self, app, items):

        files = [os.path.join(app.path, self.path, item + self.ext) for item in items]

        for name, file in zip(items, files):
            with open(file, 'r') as fp:
                result = fp.read()

            yield name, self._transform_from_local(name, result)

    def _get_remote(self, app, items):
        query = tm1_client.ODataQuery.of(None, select='Name,Rules')

        results = tm1_client.filtered(app.session.client.cubes.list, query, items)
        results = {result.name: result.rules for result in results}
        results = [(item, results[item]) for item in items]

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

        if tm1_client.cube_exists(session, name):
            tm1_client.update_rules(session, name, item)

    def _delete_remote(self, app, name):
        session = app.session

        if tm1_client.cube_exists(session, name):
            tm1_client.update_rules(session, name, '')

    def _transform_from_remote(self, name, item):
        if not item:
            return ''
        else:
            return item


logger = logging.getLogger(Rule.__name__)
