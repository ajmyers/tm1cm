import copy
import logging

from tm1cm import tm1 as tm1_client
from tm1cm.common import odata_key
from tm1cm.types.base import Base

PUBLIC = tm1_client.PUBLIC_VIEWS

# A native view's axes: each subset with its hierarchy and dimension, elements and expression
_SUBSET = 'Subset($expand=Hierarchy($select=Name;$expand=Dimension($select=Name)),Elements($select=Name);$select=Expression,UniqueName,Name,Alias)'
VIEW_EXPAND = ','.join([f'tm1.NativeView/Rows/{_SUBSET}', f'tm1.NativeView/Columns/{_SUBSET}', f'tm1.NativeView/Titles/{_SUBSET}',
                        'tm1.NativeView/Titles/Selected($select=Name)'])


class View(Base):

    def __init__(self, config, app=None):
        self.type = 'view'
        super().__init__(config, app)

        self.include = self.config.get('include_cube_view', '*/*')
        self.exclude = self.config.get('exclude_cube_view', '')

    def _list_remote(self, app):
        results = app.session.client.cubes.list(tm1_client.ODataQuery.of(None, select='Name,Views', expand='Views($select=Name)'))

        lst = []
        for cube in results:
            for view in cube.views:
                lst.append((cube.name, view.name))

        return lst

    def _get_remote(self, app, items):
        item_dict = {}
        for cube, view in items:
            if cube not in item_dict:
                item_dict.setdefault(cube, {})
                view_list = [v[1] for v in items if v[0] == cube]

                def read(query, cube=cube):
                    return app.session.client.views.list(cube, PUBLIC, query)

                results = tm1_client.odata(tm1_client.filtered(read, tm1_client.ODataQuery.of(None, expand=VIEW_EXPAND), view_list))

                for result in results:
                    item_dict[cube][result['Name']] = result

            yield (cube, view), self._transform_from_remote((cube, view), item_dict[cube][view])

    def _update_remote(self, app, name, item):
        views = app.session.client.views

        item = self._transform_to_remote(name, item)

        cube, view = name

        item = {**{'@odata.type': item['@odata.type']}, **item}

        if tm1_client.exists(lambda: views.get(cube, PUBLIC, view, tm1_client.names_query())):
            views.update(cube, PUBLIC, view, item)
        else:
            views.create(cube, PUBLIC, item)

    def _delete_remote(self, app, name):
        app.session.client.views.delete(name[0], PUBLIC, name[1])

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)

        def _row_col(selection):
            selection = copy.deepcopy(selection)
            for column in selection:
                if 'Elements' in column['Subset']:
                    column['Subset']['Elements'] = [a['Name'] for a in column['Subset']['Elements']]

                column['Subset']['Hierarchy'] = column['Subset']['Hierarchy']['Dimension']['Name'] + ':' + column['Subset']['Hierarchy']['Name']

                if 'Selected' in column and column['Selected']:
                    column['Selected'] = column['Selected']['Name']

            return selection

        del item['Name']

        if item['@odata.type'] == '#ibm.tm1.api.v1.NativeView':
            item['Type'] = 'Native'
            item['Columns'] = _row_col(item['Columns'])
            item['Rows'] = _row_col(item['Rows'])
            item['Titles'] = _row_col(item['Titles'])

        else:
            item['Type'] = 'MDX'

        del item['@odata.type']

        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)

        item['Name'] = name[1]

        def _row_col(selection):
            selection = copy.deepcopy(selection)
            for column in selection:
                if 'Elements' in column['Subset']:
                    column['Subset']['Elements'] = [{'Name': a} for a in column['Subset']['Elements']]

                dimension, hierarchy = column['Subset']['Hierarchy'].split(':')
                column['Subset']['Hierarchy'] = {'Name': hierarchy, 'Dimension': {'Name': dimension}}

                if 'Selected' in column:
                    column['Selected'] = {'Name': column['Selected']}

            return selection

        if item['Type'] == 'Native':
            item['@odata.type'] = '#ibm.tm1.api.v1.NativeView'
        elif item['Type'] == 'MDX':
            item['@odata.type'] = '#ibm.tm1.api.v1.MDXView'

        del item['Type']

        if item['@odata.type'] == '#ibm.tm1.api.v1.NativeView':
            item['Columns'] = _row_col(item['Columns'])
            item['Rows'] = _row_col(item['Rows'])
            item['Titles'] = _row_col(item['Titles'])

        return item

    def _transform_from_remote(self, name, item):
        item = copy.deepcopy(item)

        def _row_col(selection):
            selection = copy.deepcopy(selection)
            for column in selection:
                if column['Subset']['Name']:
                    del column['Subset']['Elements']
                    del column['Subset']['Expression']
                    del column['Subset']['UniqueName']
                    del column['Subset']['Alias']
                else:
                    del column['Subset']['Name']
                    del column['Subset']['UniqueName']
                    if column['Subset']['Expression']:
                        del column['Subset']['Elements']
                    else:
                        del column['Subset']['Expression']

            return selection

        item.pop('Attributes', None)

        if item['@odata.type'] == '#ibm.tm1.api.v1.NativeView':
            item['Columns'] = _row_col(item['Columns'])
            item['Rows'] = _row_col(item['Rows'])
            item['Titles'] = _row_col(item['Titles'])

        return item

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)

        def _row_col(selection):
            selection = copy.deepcopy(selection)
            for column in selection:
                if 'Selected' in column:
                    column['Selected@odata.bind'] = 'Dimensions(\'{}\')/Hierarchies(\'{}\')/Elements(\'{}\')'.format(
                        odata_key(column['Subset']['Hierarchy']['Dimension']['Name']),
                        odata_key(column['Subset']['Hierarchy']['Name']),
                        odata_key(column['Selected']['Name'])
                    )
                    del column['Selected']
                if 'Name' in column['Subset']:
                    column['Subset@odata.bind'] = 'Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(
                        odata_key(column['Subset']['Hierarchy']['Dimension']['Name']),
                        odata_key(column['Subset']['Hierarchy']['Name']),
                        odata_key(column['Subset']['Name'])
                    )
                    del column['Subset']
                else:
                    if 'Elements' in column['Subset']:
                        column['Subset']['Elements@odata.bind'] = [
                            'Dimensions(\'{}\')/Hierarchies(\'{}\')/Elements(\'{}\')'.format(
                                odata_key(column['Subset']['Hierarchy']['Dimension']['Name']),
                                odata_key(column['Subset']['Hierarchy']['Name']),
                                odata_key(a['Name'])
                            )
                            for a in column['Subset']['Elements']
                        ]
                        del column['Subset']['Elements']

                    column['Subset']['Hierarchy@odata.bind'] = 'Dimensions(\'{}\')/Hierarchies(\'{}\')'.format(
                        odata_key(column['Subset']['Hierarchy']['Dimension']['Name']),
                        odata_key(column['Subset']['Hierarchy']['Name'])
                    )
                    del column['Subset']['Hierarchy']

            return selection

        if item['@odata.type'] == '#ibm.tm1.api.v1.NativeView':
            item['Columns'] = _row_col(item['Columns'])
            item['Rows'] = _row_col(item['Rows'])
            item['Titles'] = _row_col(item['Titles'])

        return item


logger = logging.getLogger(View.__name__)
