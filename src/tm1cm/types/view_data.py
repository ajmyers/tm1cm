import copy
import csv
import json
import logging
import os
import re

from tm1cm.types.base import Base


class ViewData(Base):

    def __init__(self, config, app=None):
        self.type = 'view_data'
        super().__init__(config, app)

        self.include = self.config.get('include_cube_view_data', '*/*')
        self.exclude = self.config.get('exclude_cube_view_data', '')

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

        session = app.session

        for cube, view in items:
            data = session.cubes.cells.execute_view(cube, view, False, ['Value', 'Updateable'])
            yield (cube, view), self._transform_from_remote((cube, view), data)

    def _update_remote(self, app, name, item):
        session = app.session
        rest = session._tm1_rest

        item = self._transform_to_remote(name, item)

        query = 'SELECT { '
        row_text_list = ['(' + ', '.join(row[:-1]) + ')' for row in item]
        query = query + ', '.join(row_text_list)
        query = query + '} ON COLUMNS FROM [' + name[0] + ']'

        source = set(tuple(row) for row in item)
        target = session.cubes.cells.execute_mdx(query, ['Value', 'Updateable'])
        target = self._transform_from_remote(name, target)
        target = set(tuple(row) for row in target)

        updates = source - target

        if not updates:
            return

        request = '/api/v1/Cubes(\'{}\')/tm1.UpdateCells'.format(name[0])

        body = {'Updates': []}
        for row in updates:
            groups = [re.match(r'(\[)(.*?)(\]\.\[)(.*?)(\]\.\[)(.*?)(\])', a) for a in row[:-1]]
            elements = [(g.group(2), g.group(4), g.group(6)) for g in groups]
            tups = ['Dimensions(\'{}\')/Hierarchies(\'{}\')/Elements(\'{}\')'.format(*elem) for elem in elements]

            body['Updates'].append({'Tuple@odata.bind': tups, 'Value': row[-1]})

        rest.POST(request, json.dumps(body))

    def _delete_remote(self, app, name):
        return

    def _transform_from_remote(self, name, item):
        return [[*k, str(v['Value']) if v['Value'] else ''] for k, v in item.items() if not v['Updateable'] & 0x10000000]

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)

        result = []
        for row in item:
            updated_row = []
            for key, value in row.items():
                if key != 'Value':
                    updated_row.append('[{}].[{}].[{}]'.format(*key.split(':', 1), value))
                else:
                    value = str(value) if value and value != '0' else ''
                    updated_row.append(value)

            result.append(updated_row)

        return result

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)

        result = []
        for row in item:
            result_row = dict()
            for element in row[:-1]:
                element = element.replace('].[', ':')
                element = element.replace('[', '')
                element = element.replace(']', '')
                dimension, hierarchy, element = element.split(':')

                result_row[dimension + ':' + hierarchy] = element

            result_row['Value'] = row[-1] if row[-1] else ''

            result.append(result_row)

        return result

    def _update_local(self, app, name, item):
        path = os.path.join(app.path, self.path, os.sep.join(name) + self.ext if not isinstance(name, str) else name + self.ext)
        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(name, item)

        with open(path, 'w') as fp:
            w = csv.DictWriter(fp, item[0].keys())
            w.writeheader()
            w.writerows(item)

    def _get_local(self, app, items):

        files = [os.sep.join(item) if not isinstance(item, str) else item for item in items]
        files = [os.path.join(app.path, self.path, file + self.ext) for file in files]

        for name, file in zip(items, files):
            with open(file, 'r') as fp:
                item = list(csv.DictReader(fp))

            yield name, self._transform_from_local(name, item)


logger = logging.getLogger(ViewData.__name__)
