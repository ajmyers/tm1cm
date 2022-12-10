import copy
import json
import logging

from TM1py.Objects.Dimension import Dimension as TM1PyDimension

from tm1cm.types.base import Base


class Dimension(Base):

    def __init__(self, config):
        self.type = 'dimension'
        super().__init__(config)

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Dimensions?$select=Name'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    def _get_remote(self, app, items):
        if items is None:
            return []

        rest = app.session._tm1_rest

        filter = 'or '.join(['Name eq \'' + item + '\'' for item in items])
        request = '/api/v1/Dimensions?$select=Name&$filter=' + filter

        response = rest.GET(request)
        results = json.loads(response.text)['value']
        results = {result['Name']: result for result in results}
        results = [(item, results[item]) for item in items]

        return [(name, self._transform_from_remote(name, item)) for name, item in results]

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        try:
            dimension = TM1PyDimension.from_dict(item)

            if not session.dimensions.exists(name):
                session.dimensions.create(dimension)
        except Exception:
            logger.exception(f'Encountered error while updating dimension {name}')
            raise

    def _delete_remote(self, app, name, _):
        session = app.session

        try:
            if session.dimensions.exists(name):
                session.dimensions.delete(name)
        except Exception:
            logger.exception(f'Encountered error while deleting dimension {name}')

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
