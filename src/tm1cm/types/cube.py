import copy
import json
import logging
import urllib.parse

from TM1py.Objects.Cube import Cube as TM1PyCube
from TM1py.Objects.Dimension import Dimension as TM1PyDimension

from tm1cm.types.base import Base


class Cube(Base):

    def __init__(self, config, app=None):
        self.type = 'cube'
        super().__init__(config, app)

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Cubes?$select=Name'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    def _get_remote(self, app, items):
        filter = ['Name eq \'' + urllib.parse.quote(item, safe='') + '\'' for item in items]
        request = '/api/v1/Cubes?$expand=Dimensions($select=Name)&$select=Name,Dimensions&$filter='

        results = self._do_filter_request(app, request, filter)
        results = {result['Name']: result for result in results}
        results = [(item, results[item]) for item in items]

        for name, item in results:
            yield name, self._transform_from_remote(name, item)

    def _transform_from_remote(self, name, item):
        item = copy.deepcopy(item)
        if item['Dimensions'][0]['Name'] == 'Sandboxes':
            del item['Dimensions'][0]

        return item

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)
        item.setdefault('Rules', '')

        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        item['Dimensions'] = [{'Name': dim} for dim in item['Dimensions']]
        item['Name'] = name
        return item

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        item['Dimensions'] = [dim['Name'] for dim in item['Dimensions']]
        del item['Name']

        return item

    def _update_remote(self, app, name, item):
        session = app.session
        item = self._transform_to_remote(name, item)

        dimensions = [x['Name'] for x in item['Dimensions']]

        if session.cubes.exists(name):
            if session.cubes.get(name).dimensions != dimensions:
                logger.warning(f'Deleting cube {name} for having mismatching dimensions')
                session.cubes.delete(name)

        if not session.cubes.exists(name):
            for dimension in dimensions:
                if not session.dimensions.exists(dimension):
                    logger.debug(f'Creating dimension {dimension} because it is required to create cube {name}')
                    session.dimensions.create(TM1PyDimension(dimension))

            session.cubes.create(TM1PyCube.from_dict(item))

    def _delete_remote(self, app, name):
        session = app.session
        if session.cubes.exists(name):
            session.cubes.delete(name)


logger = logging.getLogger(Cube.__name__)
