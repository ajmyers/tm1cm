import copy
import json
import logging

from tm1cm.types.base import Base


class View(Base):

    def __init__(self, config):
        self.type = 'view'
        super().__init__(config)

        self.include = self.config.get('include_cube_view', '*/*')
        self.exclude = self.config.get('exclude_cube_view', '')

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Cubes?$select=Name,Views&$expand=Views($select=Name)'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        lst = []
        for cube in results:
            for view in cube['Views']:
                lst.append((cube['Name'], view['Name']))

        return lst

    def _get_remote(self, app, items):
        if items is None:
            return

        rest = app.session._tm1_rest

        item_dict = {}
        for cube, view in items:
            if cube not in item_dict:
                item_dict.setdefault(cube, {})
                view_list = [v[1] for v in items if v[0] == cube]
                filter = 'or '.join(['Name eq \'' + item + '\'' for item in view_list])
                request = '/api/v1/Cubes(\'{}\')/Views?$expand='.format(cube) + \
                          'tm1.NativeView/Rows/Subset($expand=Hierarchy($select=Name;' + \
                          '$expand=Dimension($select=Name)),Elements($select=Name);' + \
                          '$select=Expression,UniqueName,Name, Alias),  ' + \
                          'tm1.NativeView/Columns/Subset($expand=Hierarchy($select=Name;' + \
                          '$expand=Dimension($select=Name)),Elements($select=Name);' + \
                          '$select=Expression,UniqueName,Name,Alias), ' + \
                          'tm1.NativeView/Titles/Subset($expand=Hierarchy($select=Name;' + \
                          '$expand=Dimension($select=Name)),Elements($select=Name);' + \
                          '$select=Expression,UniqueName,Name,Alias), ' + \
                          'tm1.NativeView/Titles/Selected($select=Name)&$filter=' + filter

                response = rest.GET(request)
                results = json.loads(response.text)['value']

                for result in results:
                    item_dict[cube][result['Name']] = result

            yield (cube, view), self._transform_from_remote((cube, view), item_dict[cube][view])

    def _update_remote(self, app, name, item):
        session = app.session
        rest = session._tm1_rest

        item = self._transform_to_remote(name, item)

        try:
            cube, view = name

            item = {**{'@odata.type': item['@odata.type']}, **item}
            body = json.dumps(item, ensure_ascii=False)

            if session.cubes.views.exists(cube, view, False):
                request = '/api/v1/Cubes(\'{}\')/Views(\'{}\')'.format(cube, view)
                rest.PATCH(request, body)
            else:
                request = '/api/v1/Cubes(\'{}\')/Views'.format(cube)
                rest.POST(request, body)
        except Exception:
            logger.exception(f'Encountered error while updating view {name}')
            raise

    def _delete_remote(self, app, name):
        session = app.session
        rest = session._tm1_rest

        try:
            cube, view = name
            request = '/api/v1/Cubes(\'{}\')/Views(\'{}\')'.format(cube, view)
            rest.DELETE(request)
        except Exception:
            logger.exception(f'Encountered error while deleting view {name}')

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)

        def _row_col(selection):
            selection = copy.deepcopy(selection)
            for column in selection:
                if 'Elements' in column['Subset']:
                    column['Subset']['Elements'] = [a['Name'] for a in column['Subset']['Elements']]

                column['Subset']['Hierarchy'] = column['Subset']['Hierarchy']['Dimension']['Name'] + ':' + column['Subset']['Hierarchy']['Name']

                if 'Selected' in column:
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

        del item['Attributes']

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
                        column['Subset']['Hierarchy']['Dimension']['Name'],
                        column['Subset']['Hierarchy']['Name'],
                        column['Selected']['Name']
                    )
                    del column['Selected']
                if 'Name' in column['Subset']:
                    column['Subset@odata.bind'] = 'Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(
                        column['Subset']['Hierarchy']['Dimension']['Name'],
                        column['Subset']['Hierarchy']['Name'],
                        column['Subset']['Name']
                    )
                    del column['Subset']
                else:
                    if 'Elements' in column['Subset']:
                        column['Subset']['Elements@odata.bind'] = [
                            'Dimensions(\'{}\')/Hierarchies(\'{}\')/Elements(\'{}\')'.format(
                                column['Subset']['Hierarchy']['Dimension']['Name'],
                                column['Subset']['Hierarchy']['Name'],
                                a['Name']
                            )
                            for a in column['Subset']['Elements']
                        ]
                        del column['Subset']['Elements']

                    column['Subset']['Hierarchy@odata.bind'] = 'Dimensions(\'{}\')/Hierarchies(\'{}\')'.format(
                        column['Subset']['Hierarchy']['Dimension']['Name'],
                        column['Subset']['Hierarchy']['Name']
                    )
                    del column['Subset']['Hierarchy']

            return selection

        if item['@odata.type'] == '#ibm.tm1.api.v1.NativeView':
            item['Columns'] = _row_col(item['Columns'])
            item['Rows'] = _row_col(item['Rows'])
            item['Titles'] = _row_col(item['Titles'])

        return item


logger = logging.getLogger(View.__name__)
