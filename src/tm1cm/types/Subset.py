import copy
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
                    item_dict[dimension][hierarchy][result['Name']] = self._transform_from_remote(result['Name'], result)

        return [(item, item_dict[item[0]][item[1]][item[2]]) for item in items]

    # def _filter_local(self, items):
    #     pass

    def _filter_remote(self, items):
        return self._filter_local(items)

    def _update_remote(self, app, name, item):
        session = app.session
        rest = session._tm1_rest

        item = self._transform_to_remote(name, item)

        try:
            dimension, hierarchy, subset = name
            body = json.dumps(item, ensure_ascii=False)
            if session.dimensions.subsets.exists(subset, dimension, hierarchy, False):
                request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(dimension, hierarchy, subset)
                rest.PATCH(request, body)
            else:
                request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets'.format(dimension, hierarchy)
                rest.POST(request, body)
        except Exception:
            logger.exception(f'Encountered error while updating subset {name}')
            raise

    # def _update_local(self, app, item):
    #     pass

    def _delete_remote(self, app, name, item):
        session = app.session
        rest = session._tm1_rest

        try:
            dimension, hierarchy, subset = name
            request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(dimension, hierarchy, subset)
            rest.DELETE(request)
        except Exception:
            logger.exception(f'Encountered error while deleting subset {name}')

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']
        if 'Elements' in item:
            item['Elements'] = [a['Name'] for a in item['Elements']]
            if not item['Elements']:
                del item['Elements']
        if 'Expression' in item:
            if not item['Expression']:
                del item['Expression']
        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        item['Name'] = name[2]
        if 'Expression' in item and 'Elements' in item:
            del item['Elements']
        elif 'Elements' in item:
            item['Elements'] = [{'Name': a} for a in item['Elements']]
        else:
            item.setdefault('Expression', None)

        return item

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)
        item['Hierarchy@odata.bind'] = f'Dimensions(\'{name[0]}\')/Hierarchies(\'{name[1]}\')'
        if 'Elements' in item:
            item['Elements@odata.bind'] = [item['Hierarchy@odata.bind'] + '/Elements(\'{}\')'.format(element['Name']) for element in item['Elements']]
            del item['Elements']

        return item

    # def _delete_local(self, app, item):
    #     pass


logger = logging.getLogger(Subset.__name__)
