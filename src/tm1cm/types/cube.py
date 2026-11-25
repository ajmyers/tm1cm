import copy
import logging

from tm1cm import tm1 as tm1_client
from tm1cm.types.base import Base


class Cube(Base):

    def __init__(self, config, app=None):
        self.type = 'cube'
        super().__init__(config, app)

    def _list_remote(self, app):
        cubes = app.session.client.cubes.list(tm1_client.names_query())

        return sorted([cube.name for cube in cubes])

    def _get_remote(self, app, items):
        query = tm1_client.ODataQuery.of(None, select='Name,Dimensions', expand='Dimensions($select=Name)')

        results = tm1_client.filtered(app.session.client.cubes.list, query, items)
        results = {result['Name']: result for result in tm1_client.odata(results)}
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

        if tm1_client.cube_exists(session, name):
            if tm1_client.cube_dimensions(session, name) != dimensions:
                logger.warning(f'Deleting cube {name} for having mismatching dimensions')
                session.client.cubes.delete(name)

        if not tm1_client.cube_exists(session, name):
            for dimension in dimensions:
                if not tm1_client.dimension_exists(session, dimension):
                    logger.debug(f'Creating dimension {dimension} because it is required to create cube {name}')
                    tm1_client.create_dimension(session, {'Name': dimension})

            tm1_client.create_cube(session, item)

    def _delete_remote(self, app, name):
        session = app.session
        if tm1_client.cube_exists(session, name):
            session.client.cubes.delete(name)


logger = logging.getLogger(Cube.__name__)
