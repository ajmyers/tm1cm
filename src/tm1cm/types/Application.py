import copy
import io
import json
import logging
import os
from glob import iglob

import yaml
from TM1py.Exceptions.Exceptions import TM1pyRestException
from TM1py.Objects.Application import ApplicationTypes
from TM1py.Objects.Application import ChoreApplication
from TM1py.Objects.Application import CubeApplication
from TM1py.Objects.Application import DimensionApplication
from TM1py.Objects.Application import DocumentApplication
from TM1py.Objects.Application import FolderApplication
from TM1py.Objects.Application import LinkApplication
from TM1py.Objects.Application import ProcessApplication
from TM1py.Objects.Application import SubsetApplication
from TM1py.Objects.Application import ViewApplication

from tm1cm.common import Dumper
from tm1cm.types.base import Base

APPLICATION_TYPES = {
    'chore': 'CHORE',
    'cube': 'CUBE',
    'dimension': 'DIMENSION',
    'blob': 'DOCUMENT',
    'extr': 'LINK',
    'process': 'PROCESS',
    'subset': 'SUBSET',
    'view': 'VIEW'
}


class Application(Base):

    def __init__(self, config, app=None):
        self.type = 'application'
        super().__init__(config, app)

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        filter = ' or '.join(['endswith(Name, \'.{}\')'.format(ext) for ext in APPLICATION_TYPES.keys()])
        request = '/api/v1/Dimensions(\'}ApplicationEntries\')/Hierarchies(\'}ApplicationEntries\')/Elements?$select=Name&$filter=' + filter
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        items = [element['Name'].split('\\') for element in results]
        items = [(*item[:-1], *item[-1].rsplit('.', 1)) for item in items]
        items = sorted(items, key=lambda x: '/'.join(x))

        return items

    def _get_remote(self, app, items):

        session = app.session

        for item in items:
            *path, name, ext = item
            app_type = APPLICATION_TYPES.get(ext)
            path = '/'.join(path)

            try:
                application = session.applications.get(path, app_type, name, False)

                app = json.loads(application.body)
                if app_type == 'DOCUMENT':
                    app['Content'] = application.content

                yield item, self._transform_from_remote(item, app)
            except TM1pyRestException:
                logger.error(f'Unable to get application {name} from remote')
                yield name, None

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        try:
            # Create Folders:
            for i, p in enumerate(name[:-2]):
                app_name = p
                path = ''
                if i > 0:
                    path = '/'.join(name[:i])

                application = FolderApplication(path, app_name)
                if not session.applications.exists(path, 'FOLDER', app_name):
                    session.applications.create(application, False)

            path = '/'.join(name[:-2])
            app_name = name[-2]
            app_type = APPLICATION_TYPES[name[-1]]

            if session.applications.exists(path, app_type, app_name):
                session.applications.delete(path, app_type, app_name, False)
            session.applications.create(item, False)

        except Exception:
            logger.exception(f'Encountered error while updating application {name}')
            raise

    def _delete_remote(self, app, name):
        session = app.session

        try:
            path = '/'.join(name[:-2])
            app_name = name[-2]
            app_type = APPLICATION_TYPES[name[-1]]
            session.applications.delete(path, app_type, app_name, False)

        except Exception:
            logger.exception(f'Encountered error while deleting application {name}')
            raise

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']

        item['Type'] = item['@odata.type'].rsplit('.', 1)[-1]
        del item['@odata.type']

        if item['Type'] == 'ProcessReference':
            item['Process'] = item['Process@odata.bind'][11:-2]
            del item['Process@odata.bind']

        if item['Type'] == 'ChoreReference':
            item['Chore'] = item['Chore@odata.bind'][8:-2]
            del item['Chore@odata.bind']

        if item['Type'] == 'ViewReference':
            item['View'] = item['View@odata.bind']
            item['View'] = item['View'].replace('Cubes(\'', '')
            item['View'] = item['View'].replace('\')/Views(\'', ':')
            item['View'] = item['View'].replace('\')', '')
            del item['View@odata.bind']

        if item['Type'] == 'CubeReference':
            item['Cube'] = item['Cube@odata.bind'][7:-2]
            del item['Cube@odata.bind']

        if item['Type'] == 'DimensionReference':
            item['Dimension'] = item['Dimension@odata.bind'][12:-2]
            del item['Dimension@odata.bind']

        if item['Type'] == 'SubsetReference':
            item['Subset'] = item['Subset@odata.bind']
            item['Subset'] = item['Subset'].replace('Dimensions(\'', '')
            item['Subset'] = item['Subset'].replace('\')/Hierarchies(\'', ':')
            item['Subset'] = item['Subset'].replace('\')/Subsets(\'', ':')
            item['Subset'] = item['Subset'].replace('\')', '')
            del item['Subset@odata.bind']

        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        item['Name'] = name[-2]

        if item['Type'] == 'ProcessReference':
            item['Process@odata.bind'] = 'Processes(\'{}\')'.format(item['Process'])
            del item['Process']

        if item['Type'] == 'ChoreReference':
            item['Chore@odata.bind'] = 'Chores(\'{}\')'.format(item['Chore'])
            del item['Chore']

        if item['Type'] == 'ViewReference':
            item['View@odata.bind'] = 'Cubes(\'{}\')/Views(\'{}\')'.format(*item['View'].split(':'))
            del item['View']

        if item['Type'] == 'CubeReference':
            item['Cube@odata.bind'] = 'Cubes(\'{}\')'.format(item['Cube'])
            del item['Cube']

        if item['Type'] == 'DimensionReference':
            item['Dimension@odata.bind'] = 'Dimensions(\'{}\')'.format(item['Dimension'])
            del item['Dimension']

        if item['Type'] == 'SubsetReference':
            item['Subset@odata.bind'] = 'Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(*item['Subset'].split(':'))
            del item['Subset']

        if item['Type'] in ('Link', 'Document'):
            item['@odata.type'] = '#ibm.tm1.api.v1.' + item['Type']
        else:
            item['@odata.type'] = 'tm1.' + item['Type']

        del item['Type']

        return item

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)

        path = '/'.join(name[:-2])
        item['Type'] = item['@odata.type'].rsplit('.', 1)[-1]

        if item['Type'] == 'Document':
            return DocumentApplication(path, name[-2], item['Content'])

        if item['Type'] == 'ProcessReference':
            process = item['Process@odata.bind'][11:-2]
            return ProcessApplication(path, name[-2], process)

        if item['Type'] == 'ChoreReference':
            chore = item['Chore@odata.bind'][8:-2]
            return ChoreApplication(path, name[-2], chore)

        if item['Type'] == 'ViewReference':
            view = item['View@odata.bind']
            view = view.replace('Cubes(\'', '')
            view = view.replace('\')/Views(\'', ':')
            view = view.replace('\')', '')
            cube, view = view.split(':')
            return ViewApplication(path, name[-2], cube, view)

        if item['Type'] == 'CubeReference':
            cube = item['Cube@odata.bind'][7:-2]
            return CubeApplication(path, name[-2], cube)

        if item['Type'] == 'DimensionReference':
            dimension = item['Dimension@odata.bind'][12:-2]
            return DimensionApplication(path, name[-2], dimension)

        if item['Type'] == 'SubsetReference':
            subset = item['Subset@odata.bind']
            subset = subset.replace('Dimensions(\'', '')
            subset = subset.replace('\')/Hierarchies(\'', ':')
            subset = subset.replace('\')/Subsets(\'', ':')
            subset = subset.replace('\')', '')
            dimension, hierarchy, subset = subset.split(':')
            return SubsetApplication(path, name[-2], dimension, hierarchy, subset)

        if item['Type'] == 'Link':
            url = item['URL']
            return LinkApplication(path, name[-2], url)

    def _update_local(self, app, name, item):
        ext = self.ext
        binary = False
        if name[-1] == 'blob':
            binary = True
            ext = ''

        path = os.path.join(app.path, self.path, os.sep.join(name[:-1]) + ext if not isinstance(name, str) else name + ext)
        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(name, item)

        if binary:
            with open(path, 'wb') as fp:
                fp.write(item['Content'])
        else:
            with open(path, 'w') as fp:
                if self.file_format == 'YAML':
                    text = yaml.dump(item, Dumper=Dumper, width=255, sort_keys=False)
                else:
                    text = json.dumps(item, indent=4, sort_keys=False, ensure_ascii=False)

                fp.write(text)

    def _list_local(self, app):
        path = os.path.join(app.path, self.path)
        full_path = os.path.join(path, '**', '*')

        items = [fn for fn in iglob(full_path, recursive=True) if os.path.isfile(fn)]
        items = [item[len(path) + 1:] for item in items]
        items = [self.transform_type(path, item) for item in items]
        items = [(*item[0].split(os.sep), item[1]) for item in items]
        items = sorted(items, key=lambda x: '/'.join(x))

        return items

    def _get_local(self, app, items):
        files = [self._item_to_filename(item) for item in items]
        files = [os.path.join(app.path, self.path, file) for file in files]

        for name, file in zip(items, files):
            if not file.endswith(self.ext):
                with open(file, 'rb') as fp:
                    result = {
                        'Type': 'Document',
                        'Content': fp.read(),
                    }
            else:
                with open(file, 'rb') as fp:
                    if self.file_format == 'YAML':
                        result = yaml.safe_load(fp)
                    else:
                        result = json.safe_load(fp, indent=4, sort_keys=True, ensure_ascii=False)

            yield name, self._transform_from_local(name, result)

    def _delete_local(self, app, name):
        path = os.sep.join(name[:-1])
        if name[-1] != 'blob':
            path = path + self.ext

        path = os.path.join(app.path, self.path, path)
        if os.path.exists(path):
            os.remove(path)

    def _filter_name_func(self, item, extra):
        return item if isinstance(item, str) else '/'.join(item[:-1])

    def _item_to_filename(self, item):
        if item[-1] == 'blob':
            return os.sep.join(item[:-1])
        else:
            return os.sep.join(item[:-1]) + self.ext

    def _filename_to_item(self, path, filename):
        item = filename.split(os.sep)
        if not item[-1].endswith(self.ext):
            item = (*item, 'blob')
        else:
            with open(os.path.join(path, filename), 'r') as fp:
                if self.file_format == 'YAML':
                    content = yaml.safe_load(fp)
                else:
                    content = json.safe_load(fp, indent=4, sort_keys=True, ensure_ascii=False)

                content_type = content['Type']
                content_map = {
                    'ChoreReference': 'chore',
                    'CubeReference': 'cube',
                    'DimensionReference': 'dimension',
                    'Link': 'extr',
                    'ProcessReference': 'process',
                    'ViewReference': 'view',
                    'SubsetReference': 'subset'
                }

                item = (*item[:-1], item[-1][:-len(self.ext)], content_map[content_type])

        return item

    def transform_type(self, path, item, blob=None):
        if not item.endswith(self.ext):
            return item, 'blob'

        if blob:
            fp = io.BytesIO(blob.data_stream.read())
        else:
            fp = open(os.path.join(path, item))

        if self.file_format == 'YAML':
            obj = yaml.safe_load(fp)
        else:
            obj = json.safe_load(fp)

        fp.close()

        suffix = ApplicationTypes(obj['Type'].replace('Reference', '')).suffix[1:]

        return os.path.splitext(item)[0], suffix


logger = logging.getLogger(Application.__name__)
