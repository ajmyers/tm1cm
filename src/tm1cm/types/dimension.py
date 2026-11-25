import copy
import logging

from tm1cm import tm1 as tm1_client
from tm1cm.types.base import Base


class Dimension(Base):

    def __init__(self, config, app=None):
        self.type = 'dimension'
        super().__init__(config, app)

    def _list_remote(self, app):
        dimensions = app.session.client.dimensions.list(tm1_client.names_query())

        return sorted([dimension.name for dimension in dimensions])

    def _get_remote(self, app, items):
        results = tm1_client.filtered(app.session.client.dimensions.list, tm1_client.names_query(), items)
        results = {result['Name']: result for result in tm1_client.odata(results)}
        results = [(item, results[item]) for item in items]

        for name, item in results:
            yield name, self._transform_from_remote(name, item)

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        if not tm1_client.dimension_exists(session, name):
            tm1_client.create_dimension(session, item)

    def _delete_remote(self, app, name):
        session = app.session

        if tm1_client.dimension_exists(session, name):
            session.client.dimensions.delete(name)

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
