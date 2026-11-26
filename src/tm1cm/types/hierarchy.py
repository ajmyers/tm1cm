import copy
import logging

from tm1cm import tm1 as tm1_client
from tm1cm.common import filter_list
from tm1cm.types.base import Base


class Hierarchy(Base):

    def __init__(self, config, app=None):
        self.type = 'hierarchy'
        super().__init__(config, app)

        self.include = self.config.get('include_dimension_hierarchy', '*/*')
        self.exclude = self.config.get('exclude_dimension_hierarchy', '')

    def _list_remote(self, app):
        query = tm1_client.ODataQuery.of(None, select='Name,Hierarchies', expand='Hierarchies($select=Name)')
        results = app.session.client.dimensions.list(query)
        results = [(dim.name, hierarchy.name) for dim in results for hierarchy in dim.hierarchies]

        return sorted(results, key=lambda x: '-'.join(x))

    def _get_remote(self, app, items):

        elements = self._filter_hierarchy_elements_list(items)
        edges = self._filter_hierarchy_edges_list(elements)
        attributes = self._get_hierarchy_attributes(app, items)
        attributes = list(zip(*attributes))[0:3]
        attributes = list(zip(*attributes))
        attributes = self._filter_hierarchy_attributes_list(attributes)
        attribute_values = self._filter_hierarchy_attribute_values_list(attributes)

        hierarchies = app.session.client.hierarchies

        for item in items:
            dimension = item[0]
            hierarchy = item[1]

            elem1, elem2, edge1, edge2 = [''] * 4
            if item in elements:
                elem1, elem2 = ',Elements', ',Elements($select=Name,Type,Attributes)'
            if item in edges:
                edge1, edge2 = ',Edges', ',Edges($select=ParentName,ComponentName,Weight)'

            query = tm1_client.ODataQuery.of(None, select='Name,ElementAttributes' + elem1 + edge1, expand='ElementAttributes' + elem2 + edge2)
            result = tm1_client.odata(hierarchies.get(dimension, hierarchy, query))

            if 'ElementAttributes' in result:
                result['ElementAttributes'] = [attr for attr in result['ElementAttributes'] if (dimension, hierarchy, attr['Name']) in attributes]

            for element in result.get('Elements', []):
                for attribute in copy.copy(list(element['Attributes'].keys())):
                    if (dimension, hierarchy, attribute) not in attribute_values:
                        del element['Attributes'][attribute]

            yield item, self._transform_from_remote(item, result)

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        # The same rule as _get_remote: edges only for hierarchies whose elements are included.
        # Otherwise the item, read with elements excluded, carries no edges, and writing them
        # would delete every edge on the target.
        elements = self._filter_hierarchy_elements_list([name])
        edges = self._filter_hierarchy_edges_list(elements)

        if not tm1_client.dimension_exists(session, name[0]):
            tm1_client.create_dimension(session, {'Name': name[0]})

        if not tm1_client.hierarchy_exists(session, *name):
            # Without its attributes: TM1 can't create attributes on a hierarchy with no elements,
            # and the attribute step below adds them, handling that case
            tm1_client.create_hierarchy(session, name[0], {**item, 'ElementAttributes': []})

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
        if elements and 'Elements' in item:
            body['Elements'] = item['Elements']
        if edges and 'Edges' in item:
            body['Edges'] = item['Edges']
        if body:
            tm1_client.update_structure(session, *name, body)

        # Attribute Values
        if local_filtered_attribute_list and item.get('Elements'):
            self._update_element_attribute_values(app, name, local_filtered_attribute_list, item['Elements'])

    def _delete_remote(self, app, name):
        session = app.session

        if tm1_client.hierarchy_exists(session, *name):
            session.client.hierarchies.delete(*name)

    def _transform_from_remote(self, name, item):
        item = copy.deepcopy(item)
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
        if 'Elements' in item:
            for element in item['Elements']:
                if 'Attributes' in element and not element['Attributes']:
                    del element['Attributes']
            if not item['Elements']:
                del item['Elements']
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
        query = tm1_client.ODataQuery.of(None, select='Name,Hierarchies',
                                         expand='Hierarchies($select=Name,ElementAttributes;$expand=ElementAttributes)')
        dimensions = sorted({item[0] for item in items})
        results = tm1_client.odata(tm1_client.filtered(app.session.client.dimensions.list, query, dimensions))

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

        empty = not tm1_client.has_elements(app.session, *name)

        if empty:
            element = '}SYS_Temp_Element'
            tm1_client.create_element(app.session, *name, element, 'Numeric')

        for attr in delete:
            tm1_client.delete_element_attribute(app.session, *attr[0:3])

        for attr in create:
            tm1_client.create_element_attribute(app.session, *attr[0:4])

        if empty:
            tm1_client.delete_element(app.session, *name, element)

    def _update_element_attribute_values(self, app, name, attributes, elements):
        attribute_list = ['[}ElementAttributes_%s].[}ElementAttributes_%s].[%s]' % (name[0], name[1], attribute[2]) for attribute in attributes]
        element_list = ['[{}].[{}].[{}]'.format(name[0], name[1], element['Name']) for element in elements]
        mdx = 'SELECT { %s } ON ROWS, { %s } ON COLUMNS FROM [%s]' % (','.join(element_list), ','.join(attribute_list), '}ElementAttributes_' + name[0])

        with tm1_client.Cellset(app.session, mdx, ['Ordinal', 'Value', 'Updateable', 'RuleDerived']) as cellset:
            self._write_attribute_values(app, name, attributes, elements, cellset)

    def _write_attribute_values(self, app, name, attributes, elements, cellset):
        cellset_id = cellset.id
        cellset = cellset.cells

        attributes = [attribute[2] for attribute in attributes]

        # Add special handling for sandboxes if the sandbox dimension is present
        include_sandbox = False
        try:
            first_key = next(iter(cellset))
            if '[Sandboxes].[Sandboxes].[Base]' in first_key:
                include_sandbox = True
        except Exception:
            pass

        updates = []
        for element in elements:
            for attribute, value in element.get('Attributes', {}).items():
                if attribute not in attributes:
                    continue

                if include_sandbox:
                    cellset_value = cellset.get(
                        ('[Sandboxes].[Sandboxes].[Base]',
                         '[%s].[%s].[%s]' % (name[0], name[1], element['Name']),
                         '[}ElementAttributes_%s].[}ElementAttributes_%s].[%s]' % (name[0], name[0], attribute)),
                        {'Value': '_____'})
                else:
                    cellset_value = cellset.get(
                        ('[%s].[%s].[%s]' % (name[0], name[1], element['Name']),
                         '[}ElementAttributes_%s].[}ElementAttributes_%s].[%s]' % (name[0], name[0], attribute)),
                        {'Value': '_____'})

                if value != cellset_value['Value']:
                    if 'Updateable' in cellset_value and (not cellset_value['Updateable'] & 0x10000000):
                        if attribute == 'Format':
                            value = 'd:' + value
                        update = {
                            "Ordinal": cellset_value['Ordinal'],
                            "Value": value
                        }
                        updates.append(update)
                    else:
                        logger.info('Did not update {} for attribute {} in dimension {} because not updateable'.format(element['Name'], attribute, name[0]))

        # The cellset is deleted afterwards whether or not there was anything to write (0.9 left
        # it on the server when not)
        if updates:
            app.session.client.cellsets.update_cells(cellset_id, updates)


logger = logging.getLogger(Hierarchy.__name__)
