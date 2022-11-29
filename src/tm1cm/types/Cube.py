
import copy
import json
import logging

from urllib.parse import quote

from tm1cm.application import RemoteApplication
from tm1cm.types.Base import Base
from tm1cm.common import filter_list

from TM1py.Objects.Cube import Cube as TM1PyCube
from TM1py.Objects.Dimension import Dimension as TM1PyDimension

class Cube(Base):

    def __init__(self, config):
        self.type = 'cube'
        super().__init__(config)

    # def _list_local(self, app):
    #     pass

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Cubes?$select=Name'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    # def _get_local(self, app, items):
    #     pass

    def _get_remote(self, app, items):
        if items is None:
            return []

        rest = app.session._tm1_rest

        filter = 'or '.join(['Name eq \'' + item + '\'' for item in items])
        request = '/api/v1/Cubes?$expand=Dimensions($select=Name)&$select=Name,Dimensions&$filter=' + filter

        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return [self._transform_from_remote(result) for result in results]

    # def _filter_local(self, items):
    #     pass

    def _filter_remote(self, items):
        return self._filter_local(items)

    def _transform_from_remote(self, item):
        item = copy.deepcopy(item)
        if item['Dimensions'][0]['Name'] == 'Sandboxes':
            del item['Dimensions'][0]

        return item

    def _transform_to_remote(self, item):
        item = copy.deepcopy(item)
        item.setdefault('Rules', '')

        return item

    def _transform_from_local(self, item):
        item = copy.deepcopy(item)
        item['Dimensions'] = [{'Name': dim} for dim in item['Dimensions']]
        return item

    def _transform_to_local(self, item):
        item = copy.deepcopy(item)
        item['Dimensions'] = [dim['Name'] for dim in item['Dimensions']]
        return item

    def _update_remote(self, app, item):
        session = app.session
        item = self._transform_to_remote(item)

        cube_name = item['Name']

        try:
            dimensions = [x['Name'] for x in item['Dimensions']]

            if session.cubes.exists(cube_name):
                if session.cubes.get(cube_name).dimensions != dimensions:
                    logger.info(f'Deleting cube {cube_name} for being different')
                    session.cubes.delete(cube_name)

            if not session.cubes.exists(cube_name):
                for dimension in dimensions:
                    if not session.dimensions.exists(dimension):
                        session.dimensions.create(TM1PyDimension(dimension))

                session.cubes.create(TM1PyCube.from_dict(item))
        except Exception:
            logger.exception(f'Encountered error while updating cube {item}')
            raise

    # def _update_local(self, app, item):
    #     pass

    def _delete_remote(self, app, item):
        session = app.session
        try:
            cube = item['Name']
            if session.cubes.exists(cube):
                session.cubes.delete(cube)
        except Exception:
            logger.exception(f'Encountered error while deleting cube {cube}')

    # def _delete_local(self, app, item):
    #     pass

logger = logging.getLogger(Cube.__name__)