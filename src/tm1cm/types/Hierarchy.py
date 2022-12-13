import copy
import json
import logging
from urllib.parse import quote

from TM1py.Objects.Dimension import Dimension as TM1PyDimension
from TM1py.Objects.Element import Element as TM1PyElement
from TM1py.Objects.ElementAttribute import ElementAttribute as TM1PyElementAttribute
from TM1py.Objects.Hierarchy import Hierarchy as TM1PyHierarchy

from tm1cm.common import filter_list
from tm1cm.types.base import Base


class Hierarchy(Base):

    def __init__(self, config, app=None):
        self.type = 'hierarchy'
        super().__init__(config, app)

        self.include = self.config.get('include_dimension_hierarchy', '*/*')
        self.exclude = self.config.get('exclude_dimension_hierarchy', '')

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Dimensions?$select=Name,Hierarchies&$expand=Hierarchies($select=Name)'
        response = rest.GET(request)
        results = json.loads(response.text)['value']
        results = [(dim['Name'], hierarchy['Name']) for dim in results for hierarchy in dim['Hierarchies']]

        return sorted(results, key=lambda x: '-'.join(x))

    def _get_remote(self, app, items):

        elements = self._filter_hierarchy_elements_list(items)
        edges = self._filter_hierarchy_edges_list(elements)
        attributes = self._get_hierarchy_attributes(app, items)
        attributes = list(zip(*attributes))[0:3]
        attributes = list(zip(*attributes))
        attributes = self._filter_hierarchy_attributes_list(attributes)
        attribute_values = self._filter_hierarchy_attribute_values_list(attributes)

        rest = app.session._tm1_rest

        for item in items:
            dimension = item[0]
            hierarchy = item[1]

            elem1, elem2, edge1, edge2 = [''] * 4
            if item in elements:
                elem1, elem2 = ',Elements', ',Elements($select=Name,Type,Attributes)'
            if item in edges:
                edge1, edge2 = ',Edges', ',Edges($select=ParentName,ComponentName,Weight)'

            request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')?$select=Name,ElementAttributes{}{}&$expand=ElementAttributes{}{}'.format(quote(dimension), quote(hierarchy), elem1, edge1, elem2, edge2)
            response = rest.GET(request)
            result = json.loads(response.text)

            if 'ElementAttributes' in result:
                result['ElementAttributes'] = [attr for attr in result['ElementAttributes'] if (dimension, hierarchy, attr['Name']) in attributes]

            for element in result.get('Elements', []):
                for attribute in copy.copy(list(element['Attributes'].keys())):
                    if (dimension, hierarchy, attribute) not in attribute_values:
                        del element['Attributes'][attribute]

            yield item, self._transform_from_remote(item, result)

    def _update_remote(self, app, name, item):
        session = app.session
        rest = session._tm1_rest

        item = self._transform_to_remote(name, item)

        edges = self._filter_hierarchy_edges_list([name])
        elements = self._filter_hierarchy_elements_list([name])

        if not session.dimensions.exists(name[0]):
            dimension = TM1PyDimension(name[0])
            session.dimensions.create(dimension)

        if not session.dimensions.hierarchies.exists(name[0], name[1]):
            hierarchy = TM1PyHierarchy.from_dict(item, name[0])
            session.dimensions.hierarchies.create(hierarchy)

        # Attributes
        remote_full_attribute_list = set(self._get_hierarchy_attributes(app, [name]))
        local_full_attribute_list = set([(name[0], name[1], attr['Name'], attr['Type']) for attr in item['ElementAttributes']])

        remote_filtered_attribute_list = set(self._filter_hierarchy_attributes_list(remote_full_attribute_list))
        local_filtered_attribute_list = set(self._filter_hierarchy_attributes_list(local_full_attribute_list))

        delete_list = remote_filtered_attribute_list - local_filtered_attribute_list
        create_list = local_filtered_attribute_list - remote_filtered_attribute_list

        self._update_element_attributes(app, create_list, delete_list, name)

        # Elements & Edges
        body = {}
        if elements:
            body['Elements'] = item['Elements']
        if edges:
            body['Edges'] = item['Edges']
        if body:
            request = f'/api/v1/Dimensions(\'{quote(name[0])}\')/Hierarchies(\'{quote(name[1])}\')'
            rest.PATCH(request, json.dumps(body))

        # Attribute Values
        if local_filtered_attribute_list and item['Elements']:
            self._update_element_attribute_values(app, name, local_filtered_attribute_list, item['Elements'])

    def _delete_remote(self, app, name):
        session = app.session

        if session.dimensions.hierarchies.exists(*name):
            session.dimensions.hierarchies.delete(*name)

    def _transform_from_remote(self, name, item):
        item = copy.deepcopy(item)
        del item['@odata.context']
        item['ElementAttributes'] = sorted(item['ElementAttributes'], key=lambda x: x['Name'])
        return item

    def _transform_to_remote(self, name, item):
        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        if item is None:
            item = {}

        item['Name'] = name[1]

        item.setdefault('Elements', [])
        item.setdefault('ElementAttributes', [])
        item.setdefault('Edges', [])

        for element in item['Elements']:
            element.setdefault('Attributes', {})

        item['ElementAttributes'] = sorted(item['ElementAttributes'], key=lambda x: x['Name'])

        return item

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']
        for element in item.get('Elements', []):
            if 'Attributes' in element and not element['Attributes']:
                del element['Attributes']
        if 'ElementAttributes' in item:
            if not item['ElementAttributes']:
                del item['ElementAttributes']
        if 'Edges' in item:
            if not item['Edges']:
                del item['Edges']
        return item

    def _filter_hierarchy_elements_list(self, items):
        include_filter = self.config.get('include_dimension_hierarchy_element', '*/*')
        exclude_filter = self.config.get('exclude_dimension_hierarchy_element', '')

        return filter_list(items, include_filter, exclude_filter, name_func=self._filter_name_func)

    def _filter_hierarchy_edges_list(self, items):
        include_filter = self.config.get('include_dimension_hierarchy_edge', '*/*')
        exclude_filter = self.config.get('exclude_dimension_hierarchy_edge', '')

        return filter_list(items, include_filter, exclude_filter, name_func=self._filter_name_func)

    def _filter_hierarchy_attributes_list(self, items):
        def _filter_func(item, extra):
            return item if isinstance(item, str) else '/'.join(item[0:3])

        include_filter = self.config.get('include_dimension_hierarchy_attribute', '*/*/*')
        exclude_filter = self.config.get('exclude_dimension_hierarchy_attribute', '')

        return filter_list(items, include_filter, exclude_filter, name_func=_filter_func)

    def _filter_hierarchy_attribute_values_list(self, items):
        def _filter_func(item, extra):
            return item if isinstance(item, str) else '/'.join(item[0:4])

        include_filter = self.config.get('include_dimension_hierarchy_attribute_value', '*/*/*')
        exclude_filter = self.config.get('exclude_dimension_hierarchy_attribute_value', '')

        return filter_list(items, include_filter, exclude_filter, name_func=_filter_func)

    def _get_hierarchy_attributes(self, app, items):
        rest = app.session._tm1_rest

        filter = 'or '.join({'Name eq \'' + quote(item[0], safe='') + '\'' for item in items})
        request = '/api/v1/Dimensions?$select=Name,Hierarchies&$expand=Hierarchies($select=Name,ElementAttributes;$expand=ElementAttributes)&$filter=' + filter
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        lst = []
        for dimension in results:
            for hierarchy in dimension['Hierarchies']:
                if (dimension['Name'], hierarchy['Name']) in items:
                    for attribute in hierarchy['ElementAttributes']:
                        lst.append((dimension['Name'], hierarchy['Name'], attribute['Name'], attribute['Type']))

        return lst

    def _update_element_attributes(self, app, create, delete, name):
        if not create and not delete:
            return

        request = f'/api/v1/Dimensions(\'{name[0]}\')/Hierarchies(\'{name[1]}\')/Elements?$top=0&$count'
        response = app.session._tm1_rest.GET(request)
        results = json.loads(response.text)
        count = results['@odata.count']

        if count == 0:
            element = '}SYS_Temp_Element'
            app.session.elements.create(*name, TM1PyElement(element, 'Numeric'))

        for attr in delete:
            app.session.elements.delete_element_attribute(*attr[0:3])

        for attr in create:
            element_attribute = TM1PyElementAttribute(*attr[2:4])
            app.session.elements.create_element_attribute(*attr[0:2], element_attribute)

        if count == 0:
            app.session.elements.delete(*name, element)

    def _update_element_attribute_values(self, app, name, attributes, elements):
        attribute_list = ['[}ElementAttributes_%s].[}ElementAttributes_%s].[%s]' % (name[0], name[1], attribute[2]) for attribute in attributes]
        element_list = ['[{}].[{}].[{}]'.format(name[0], name[1], element['Name']) for element in elements]
        mdx = 'SELECT { %s } ON ROWS, { %s } ON COLUMNS FROM [%s]' % (','.join(element_list), ','.join(attribute_list), '}ElementAttributes_' + name[0])

        cellset_id = app.session.cubes.cells.create_cellset(mdx)
        cellset = app.session.cubes.cells.execute_mdx(mdx, cell_properties=['Ordinal', 'Value', 'Updateable', 'RuleDerived'])

        attributes = [attribute[2] for attribute in attributes]

        updates = []
        for element in elements:
            for attribute, value in element.get('Attributes', {}).items():
                if attribute not in attributes:
                    continue
                cellset_value = cellset.get(
                    ('[%s].[%s].[%s]' % (name[0], name[1], element['Name']), '[}ElementAttributes_%s].[}ElementAttributes_%s].[%s]' % (name[0], name[0], attribute)), {'Value': '_____'})

                if value != cellset_value['Value']:
                    if not cellset_value['Updateable'] & 0x10000000:
                        if attribute == 'Format':
                            value = 'd:' + value
                        update = {
                            "Ordinal": cellset_value['Ordinal'],
                            "Value": value
                        }
                        updates.append(update)
                    else:
                        logger.info('Did not update {} for attribute {} in dimension {} because not updateable'.format(element['Name'], attribute, name[0]))

        if updates:
            rest = app.session._tm1_rest
            request = "/api/v1/Cellsets('{}')/Cells".format(cellset_id)

            rest.PATCH(request, json.dumps(updates, ensure_ascii=False))
            app.session.cubes.cells.delete_cellset(cellset_id)


logger = logging.getLogger(Hierarchy.__name__)
