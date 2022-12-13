import copy
import json
import logging
import urllib.parse
import urllib.parse

from tm1cm.types.base import Base


class Subset(Base):

    def __init__(self, config, app=None):
        self.type = 'subset'
        super().__init__(config, app)

        self.include = self.config.get('include_dimension_hierarchy_subset', '*/*/*')
        self.exclude = self.config.get('exclude_dimension_hierarchy_subset', '')

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

    def _get_remote(self, app, items):

        rest = app.session._tm1_rest

        item_dict = {}
        for name in items:
            dimension, hierarchy, subset = name
            if dimension not in item_dict:
                item_dict.setdefault(dimension, {})
            if hierarchy not in item_dict[dimension]:
                item_dict[dimension].setdefault(hierarchy, {})
                subset_list = [item[2] for item in items if item[0] == dimension and item[1] == hierarchy]

                filter = ['Name eq \'' + urllib.parse.quote(item, safe='') + '\'' for item in subset_list]
                request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets?$expand=Elements($select=Name)&$select=Name,Expression,Elements,Alias&$filter='.format(dimension, hierarchy)

                results = self._do_filter_request(app, request, filter)

                for result in results:
                    item_dict[dimension][hierarchy][result['Name']] = result

            yield name, self._transform_from_remote(name, item_dict[dimension][hierarchy][subset])

    def _update_remote(self, app, name, item):
        session = app.session
        rest = session._tm1_rest

        item = self._transform_to_remote(name, item)

        dimension, hierarchy, subset = name
        body = json.dumps(item, ensure_ascii=False)
        if session.dimensions.subsets.exists(subset, dimension, hierarchy, False):
            if 'Elements@odata.bind' in item:
                request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')/Elements/$ref'.format(dimension, hierarchy, subset)
                rest.DELETE(request)

            request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(dimension, hierarchy, subset)
            rest.PATCH(request, body)
        else:
            request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets'.format(dimension, hierarchy)
            rest.POST(request, body)

    def _delete_remote(self, app, name):
        session = app.session
        rest = session._tm1_rest

        dimension, hierarchy, subset = name
        request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(dimension, hierarchy, subset)
        rest.DELETE(request)

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

        item.setdefault('Expression', None)

        return item

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)
        item['Hierarchy@odata.bind'] = f'Dimensions(\'{name[0]}\')/Hierarchies(\'{name[1]}\')'
        if 'Elements' in item:
            item['Elements@odata.bind'] = [item['Hierarchy@odata.bind'] + '/Elements(\'{}\')'.format(element['Name']) for element in item['Elements']]
            del item['Elements']
        if 'Expression' in item:
            if item['Expression'] is None:
                del item['Expression']

        return item

    def _transform_from_remote(self, name, item):
        item = copy.deepcopy(item)
        if item['Expression'] is not None:
            del item['Elements']
        return item


logger = logging.getLogger(Subset.__name__)
