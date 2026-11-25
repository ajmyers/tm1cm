import contextlib
import copy
import io
import json
import logging
import os
import random
import re
import string
from urllib.parse import unquote

import filetype
from glob import iglob
from skipcheck_tm1 import errors as tm1_errors

import yaml
from tm1cm import tm1 as tm1_client
from tm1cm.common import Dumper
from tm1cm.common import odata_key
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

# A reference's bind, for each reference type: its key, and the shape of its value. The local file
# holds the referenced object's plain name (its parts joined with ':' for views and subsets).
REFERENCES = {
    'ProcessReference': ('Process', "Processes('{}')"),
    'ChoreReference': ('Chore', "Chores('{}')"),
    'CubeReference': ('Cube', "Cubes('{}')"),
    'DimensionReference': ('Dimension', "Dimensions('{}')"),
    'ViewReference': ('View', "Cubes('{}')/Views('{}')"),
    'SubsetReference': ('Subset', "Dimensions('{}')/Hierarchies('{}')/Subsets('{}')"),
}

_BIND_KEY = re.compile(r"\('((?:[^']|'')*)'\)")


def _bind_names(bind):
    """The object names in a bind such as Cubes('a')/Views('b'), decoded: TM1 percent-encodes
    names that need it (Processes('Proc%231') is Proc#1), and OData doubles '."""
    return [unquote(key).replace("''", "'") for key in _BIND_KEY.findall(bind)]


def _make_bind(template, names):
    return template.format(*(odata_key(name) for name in names))


class Application(Base):

    def __init__(self, config, app=None):
        self.type = 'application'
        super().__init__(config, app)

    def _list_remote(self, app):
        # get list of applications
        try:
            applications = tm1_client.applications(app.session)
        except Exception:
            logger.error('Unable to get list of applications from remote')
            applications = []

        items = []
        for application in applications:
            self._recursive_list_remote(app, [application], items)

        return items

    def _recursive_list_remote(self, app, path, items):
        results = tm1_client.application_entries(app.session, '/'.join(path))

        # Do this as two separate operations to ensure correct order
        for entry in results:
            if entry['@odata.type'] != '#ibm.tm1.api.v1.Folder':
                items.append((*path, *entry['ID'].rsplit('.', 1)))

        for entry in results:
            if entry['@odata.type'] == '#ibm.tm1.api.v1.Folder':
                self._recursive_list_remote(app, path + [entry['Name']], items)

    @staticmethod
    def _exists(app, path, application_type, name):
        """Whether an application exists, with every name in its URL encoded (TM1py's
        ApplicationService.exists didn't encode folder names)."""
        return tm1_client.application_exists(app.session, path, application_type, name)

    def _get_remote(self, app, items):

        session = app.session

        for item in items:
            *path, name, ext = item
            app_type = APPLICATION_TYPES.get(ext)
            path = '/'.join(path)

            try:
                body, content = tm1_client.get_application(session, path, app_type, name)
                if app_type == 'DOCUMENT':
                    body['Content'] = content

                yield item, self._transform_from_remote(item, body)
            except tm1_errors.Tm1ApiError:
                logger.error(f'Unable to get application {name} from remote')
                yield name, None

    def _update_remote(self, app, name, item):
        session = app.session

        entry = self._transform_to_remote(name, item)

        try:
            # Create Folders:
            for i, p in enumerate(name[:-2]):
                app_name = p
                path = ''
                if i > 0:
                    path = '/'.join(name[:i])

                if not self._exists(app, path, 'FOLDER', app_name):
                    tm1_client.create_application(session, path, {'@odata.type': '#ibm.tm1.api.v1.Folder', 'Name': app_name})

            path = '/'.join(name[:-2])
            app_name = name[-2]
            app_type = APPLICATION_TYPES[name[-1]]

            if self._exists(app, path, app_type, app_name):
                tm1_client.delete_application(session, path, app_type, app_name)
            tm1_client.create_application(session, path, entry['body'], entry['content'])

            if app_type == 'DOCUMENT' and app_name != entry['name']:
                # Add special handling for spreadsheets to ensure when they're updated they can still be opened in TM1Web
                if self._exists(app, path, app_type, app_name):
                    tm1_client.delete_application(session, path, app_type, app_name)
                tm1_client.rename_application(session, path, app_type, entry['name'], app_name)

        except Exception:
            logger.exception(f'Encountered error while updating application {name}')
            raise

    def _delete_remote(self, app, name):
        session = app.session

        try:
            path = '/'.join(name[:-2])
            app_name = name[-2]
            app_type = APPLICATION_TYPES[name[-1]]
            tm1_client.delete_application(session, path, app_type, app_name)

        except Exception:
            logger.exception(f'Encountered error while deleting application {name}')
            raise

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']

        item['Type'] = item['@odata.type'].rsplit('.', 1)[-1]
        del item['@odata.type']

        if item['Type'] in REFERENCES:
            key, _ = REFERENCES[item['Type']]
            item[key] = ':'.join(_bind_names(item.pop(key + '@odata.bind')))

        return item

    def _transform_from_remote(self, name, item):
        # References in one form, whichever server they came from and however it encoded them
        if item and item.get('@odata.type', '').rsplit('.', 1)[-1] in REFERENCES:
            item = copy.deepcopy(item)
            key, template = REFERENCES[item['@odata.type'].rsplit('.', 1)[-1]]
            item[key + '@odata.bind'] = _make_bind(template, _bind_names(item[key + '@odata.bind']))
        return item

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        item['Name'] = name[-2]

        if item['Type'] in REFERENCES:
            key, template = REFERENCES[item['Type']]
            item[key + '@odata.bind'] = _make_bind(template, item.pop(key).split(':'))

        if item['Type'] in ('Link', 'Document'):
            item['@odata.type'] = '#ibm.tm1.api.v1.' + item['Type']
        else:
            item['@odata.type'] = 'tm1.' + item['Type']

        del item['Type']

        return item

    def _transform_to_remote(self, name, item):
        """The entry to create: its name, its body, and a document's content."""
        item = copy.deepcopy(item)

        item['Type'] = item['@odata.type'].rsplit('.', 1)[-1]

        if item['Type'] == 'Document':
            # Add special handling for spreadsheets to ensure when they're updated they can still be opened in TM1Web
            file_type = filetype.guess(item['Content'])
            file_id = item['Name']
            if file_type is not None:
                current_extension = file_id.split('.')[-1].lower() if '.' in file_id else file_id.lower()
                if file_type.extension in ('xlsx', 'xls') and current_extension not in ('xlsx', 'xls', 'xlsb', 'xlsm'):
                    unique = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                    file_id += '.' + unique + '.' + file_type.extension

            return {'name': file_id, 'body': {'@odata.type': item['@odata.type'], 'Name': file_id}, 'content': item['Content']}

        body = {'@odata.type': item['@odata.type'], 'Name': name[-2]}
        if item['Type'] in REFERENCES:
            key, template = REFERENCES[item['Type']]
            body[key + '@odata.bind'] = _make_bind(template, _bind_names(item[key + '@odata.bind']))

        if item['Type'] == 'Link':
            body['URL'] = item['URL']

        return {'name': name[-2], 'body': body, 'content': None}

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
                        result = json.load(fp)

            yield name, self._transform_from_local(name, result)

    def _delete_local(self, app, name):
        path = os.sep.join(name[:-1])
        if name[-1] != 'blob':
            path = path + self.ext
        path = os.path.join(self.path, path)
        full_path = os.path.join(app.path, path)
        if os.path.exists(full_path):
            with contextlib.suppress(OSError):
                os.remove(full_path)

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
                    content = json.load(fp)

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
            obj = json.load(fp)

        fp.close()

        suffix = tm1_client.APPLICATION_TYPES[obj['Type'].replace('Reference', '').upper()][0][1:]

        return os.path.splitext(item)[0], suffix


logger = logging.getLogger(Application.__name__)
