import copy
import logging

from tm1cm import tm1 as tm1_client
from tm1cm.common import odata_key
from tm1cm.types.base import Base

PUBLIC = tm1_client.PUBLIC_SUBSETS


class Subset(Base):

    def __init__(self, config, app=None):
        self.type = 'subset'
        super().__init__(config, app)

        self.include = self.config.get('include_dimension_hierarchy_subset', '*/*/*')
        self.exclude = self.config.get('exclude_dimension_hierarchy_subset', '')

    def _list_remote(self, app):
        query = tm1_client.ODataQuery.of(None, select='Name,Hierarchies',
                                         expand='Hierarchies($select=Name,Subsets;$expand=Subsets($select=Name))')
        results = app.session.client.dimensions.list(query)

        lst = []
        for dimension in results:
            for hierarchy in dimension.hierarchies:
                for subset in hierarchy.subsets:
                    lst.append((dimension.name, hierarchy.name, subset.name))

        return lst

    def _get_remote(self, app, items):
        item_dict = {}
        for name in items:
            dimension, hierarchy, subset = name
            if dimension not in item_dict:
                item_dict.setdefault(dimension, {})
            if hierarchy not in item_dict[dimension]:
                item_dict[dimension].setdefault(hierarchy, {})
                subset_list = [item[2] for item in items if item[0] == dimension and item[1] == hierarchy]

                query = tm1_client.ODataQuery.of(None, select='Name,Expression,Elements,Alias', expand='Elements($select=Name)')

                def read(query, dimension=dimension, hierarchy=hierarchy):
                    return app.session.client.subsets.list(dimension, hierarchy, PUBLIC, query)

                results = tm1_client.odata(tm1_client.filtered(read, query, subset_list))

                for result in results:
                    item_dict[dimension][hierarchy][result['Name']] = result

            yield name, self._transform_from_remote(name, item_dict[dimension][hierarchy][subset])

    def _update_remote(self, app, name, item):
        subsets = app.session.client.subsets

        elements = [element['Name'] for element in item['Elements']] if 'Elements' in item else None
        item = self._transform_to_remote(name, item)

        dimension, hierarchy, subset = name
        if tm1_client.exists(lambda: subsets.get(dimension, hierarchy, PUBLIC, subset, tm1_client.names_query())):
            # A PATCH binding Elements appends to them, so SubsetService.update refuses it: the
            # elements are cleared and added again, and the rest patched
            patch = {key: value for key, value in item.items() if key != 'Elements@odata.bind'}
            if elements is not None:
                subsets.clear_elements(dimension, hierarchy, PUBLIC, subset)
            subsets.update(dimension, hierarchy, PUBLIC, subset, patch)
            if elements:
                subsets.add_elements(dimension, hierarchy, PUBLIC, subset, elements)
        else:
            subsets.create(dimension, hierarchy, PUBLIC, item)

    def _delete_remote(self, app, name):
        app.session.client.subsets.delete(*name[0:2], PUBLIC, name[2])

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
        item['Hierarchy@odata.bind'] = f'Dimensions(\'{odata_key(name[0])}\')/Hierarchies(\'{odata_key(name[1])}\')'
        if 'Elements' in item:
            item['Elements@odata.bind'] = [item['Hierarchy@odata.bind'] + '/Elements(\'{}\')'.format(odata_key(element['Name'])) for element in item['Elements']]
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
