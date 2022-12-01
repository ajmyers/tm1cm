import json
import logging

from tm1cm.types.Base import Base


class Subset(Base):

    def __init__(self, config):
        self.type = 'subset'
        super().__init__(config)

    # def _list_local(self, app):
    #     pass

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Dimensions?$select=Name,Hierarchies&$expand=Hierarchies($select=Name,Subsets;$expand=Subsets($select=Name))'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        lst = []
        for dimension in results:
            for hierarchy in dimension['Hierarchies']:
                for subset in hierarchy['Subsets']:
                    lst.append((dimension['Name'], hierarchy['Name'], subset['Name']))

        return lst

    # def _get_local(self, app, items):
    #     pass

    def _get_remote(self, app, items):
        if items is None:
            return []

        items = [item.split('/') for item in items]

        item_dict = {}
        for dimension, hierarchy, subset in items:
            item_dict.setdefault(dimension, {}).setdefault(hierarchy, {}).setdefault(subset, None)

        rest = app.session._tm1_rest

        for dimension, hierarchy_dict in item_dict.items():
            for hierarchy, subset_list in hierarchy_dict.items():
                filter = 'or '.join(['Name eq \'' + item + '\'' for item in subset_list])
                request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets?$expand=Elements($select=Name)&$select=Name,Expression,Elements,Alias&$filter={}'.format(dimension, hierarchy, filter)

                response = rest.GET(request)
                results = json.loads(response.text)['value']

                for result in results:
                    item_dict[dimension][hierarchy][result['Name']] = self._transform_from_remote(result)

        return [item_dict[dimension][hierarchy][subset] for dimension, hierarchy, subset in items]

    # def _filter_local(self, items):
    #     pass

    def _filter_remote(self, items):
        return self._filter_local(items)

    def _update_remote(self, app, item):
        session = app.session

        item = self._transform_to_remote(item)

        try:
            dimension = TM1PyDimension.from_dict(item)

            if not session.dimensions.exists(dimension.name):
                session.dimensions.create(dimension)
        except Exception:
            logger.exception(f'Encountered error while updating dimension {dimension_name}')
            raise

    # def _update_local(self, app, item):
    #     pass

    def _delete_remote(self, app, item):
        session = app.session

        dimension_name = item['Name']
        try:
            if session.dimensions.exists(dimension_name):
                session.dimensions.delete(dimension_name)
                logger.info(f'Deleted dimension {dimension_name}')
        except Exception:
            logger.exception(f'Encountered error while deleting dimension {dimension_name}')

    # def _transform_to_local(self, item):
    #     item = copy.deepcopy(item)
    #     item['Elements'] = [elem['Name'] for elem in item['Elements']]
    #     if not item['Expression']:
    #         del item['Expression']
    #
    #     if not item['Elements']:
    #         del item['Elements']
    #
    #     if not item['Alias']:
    #         del item['Alias']
    #
    #     return item

    # def _delete_local(self, app, item):
    #     pass


logger = logging.getLogger(Subset.__name__)
