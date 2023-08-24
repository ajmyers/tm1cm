import base64
import copy
import json
import logging
import os
import shutil
from fnmatch import fnmatch
from glob import iglob

import yaml
from TM1py.Objects.NativeView import NativeView
from TM1py.Objects.Subset import AnonymousSubset
from TM1py.Services import TM1Service

from tm1cm.common import filter_list, Dumper
from tm1cm.ti_format import format_procedure


class Application:

    def __init__(self, config):
        self.config = config

        self._cube_object = None
        self._rule_object = None
        self._dimension_object = None
        self._hierarchy_list = None
        self._process_object = None
        self._file_list = []
        self._view_list = []
        self._subset_list = []

        self.refreshed = False

    @property
    def cubes(self):
        return {x['Name']: x for x in self._cube_object}

    @property
    def rules(self):
        return {x['Name']: x for x in self._rule_object}

    @property
    def dimensions(self):
        return {x['Name']: x for x in self._dimension_object}

    @property
    def hierarchies(self):
        return self._hierarchy_list

    @property
    def processes(self):
        return {x['Name']: x for x in self._process_object}

    @property
    def files(self):
        return self._file_list

    @property
    def views(self):
        return self._view_list

    @property
    def subsets(self):
        return self._subset_list

    def refresh(self, overlay=True):
        self._populate(overlay)
        self._filter()

        self.refreshed = True

        return self

    def to_local(self, path, clear=False):
        logger = logging.getLogger(__name__)

        if not self.refreshed:
            self.refresh()

        for folder in ['data', 'scripts', 'files']:
            file_path = os.path.join(path, folder)
            if clear and os.path.exists(file_path):
                shutil.rmtree(file_path)

        # Cube
        file_path = os.path.join(path, 'data', 'cube')
        if self._cube_object:
            os.makedirs(file_path, exist_ok=True)

        for cube in self._cube_object:
            cube_name = cube['Name']
            logger.debug('Processing cube {}'.format(cube_name))

            file_name = '{}.cube'.format(cube_name)
            with open(os.path.join(file_path, file_name), 'wb') as outfile:
                text = self.dump(cube)
                outfile.write(text)

        # View
        file_path = os.path.join(path, 'data', 'view')
        for cube_name, view_name in self._view_list:
            view_path = os.path.join(file_path, cube_name)
            os.makedirs(view_path, exist_ok=True)

            view = self.get_view(cube_name, view_name)
            logger.debug('Processing cube view {}, {}'.format(cube_name, view_name))

            file_name = '{}.view'.format(view_name)
            with open(os.path.join(view_path, file_name), 'wb') as outfile:
                text = self.dump(view)
                outfile.write(text)

        # View Data
        file_path = os.path.join(path, 'data', 'view_data')
        for cube_name, view_name in self._view_data_list:
            view_path = os.path.join(file_path, cube_name)
            os.makedirs(view_path, exist_ok=True)

            view_data = self.get_view_data(cube_name, view_name)
            logger.debug('Processing cube view data {}, {}'.format(cube_name, view_name))

            file_name = '{}.view_data'.format(view_name)
            with open(os.path.join(view_path, file_name), 'wb') as outfile:
                text = self.dump(view_data)
                outfile.write(text)

        # Subsets
        file_path = os.path.join(path, 'data', 'subset')
        for dimension_name, hierarchy_name, subset_name in self._subset_list:
            subset_path = os.path.join(file_path, dimension_name, hierarchy_name)
            os.makedirs(subset_path, exist_ok=True)

            subset = dict(self.get_subset(dimension_name, hierarchy_name, subset_name))
            logger.debug('Processing subset {}/{}/{}'.format(dimension_name, hierarchy_name, subset_name))

            file_name = '{}.subset'.format(subset_name)
            with open(os.path.join(subset_path, file_name), 'wb') as outfile:
                text = self.dump(subset)
                outfile.write(text)

        # Rule
        file_path = os.path.join(path, 'data', 'rule')
        if self._rule_object:
            os.makedirs(file_path, exist_ok=True)

        for cube in self._rule_object:
            cube_name = cube['Name']
            logger.debug('Processing rule {}'.format(cube_name))

            rule = cube.get('Rules', None)
            if rule:
                file_name = '{}.rule'.format(cube_name)
                with open(os.path.join(file_path, file_name), 'wb') as outfile:
                    outfile.write(rule.encode('utf8'))

        # Dimension
        file_path = os.path.join(path, 'data', 'dimension')
        if self._dimension_object:
            os.makedirs(file_path, exist_ok=True)

        for dimension in self._dimension_object:
            dimension_name = dimension['Name']
            logger.debug('Processing dimension {}'.format(dimension_name))

            file_name = '{}.dimension'.format(dimension_name)
            with open(os.path.join(file_path, file_name), 'wb') as outfile:
                text = self.dump(dimension)
                outfile.write(text)

        # Hierarchy
        file_path = os.path.join(path, 'data', 'hierarchy')
        for dimension_name, hierarchy_name in self._hierarchy_list:
            hierarchy_path = os.path.join(file_path, dimension_name)
            os.makedirs(hierarchy_path, exist_ok=True)

            hierarchy = self.get_hierarchy(dimension_name, hierarchy_name)

            file_name = '{}.hierarchy'.format(hierarchy_name)
            with open(os.path.join(hierarchy_path, file_name), 'wb') as outfile:
                hierarchy['ElementAttributes'] = sorted(hierarchy['ElementAttributes'], key=lambda x: x['Name'])

                text = self.dump(hierarchy)
                outfile.write(text)

        # Process
        file_path = os.path.join(path, 'data', 'process')
        if self._process_object:
            os.makedirs(file_path, exist_ok=True)

        procedures = ['PrologProcedure', 'MetadataProcedure', 'DataProcedure', 'EpilogProcedure']

        for process in copy.deepcopy(self._process_object):
            file_name = '{}.process'.format(process['Name'])

            with open(os.path.join(file_path, file_name), 'wb') as outfile:
                output = []
                for procedure in procedures:
                    header = globals().get('{}_BEGIN'.format(procedure[:-9].upper()))

                    text = process[procedure]
                    text = self._fix_generated_lines(text)
                    text = text.replace('\r\n', '\n')

                    footer = globals().get('{}_END'.format(procedure[:-9].upper()))
                    output.append((header + text + footer).encode('utf8'))

                header = globals().get('PROPERTIES_BEGIN').encode('utf8')
                text = self.dump({key: value for key, value in process.items() if key not in procedures})
                footer = globals().get('PROPERTIES_END').encode('utf8')
                output.insert(0, header + text + footer)

                outfile.write(''.encode('utf8').join(output))

        # Files & Scripts
        for obj in self._file_list:
            file_path, file_name = os.path.split(os.path.join(path, os.sep.join(obj)))

            os.makedirs(file_path, exist_ok=True)

            with open(os.path.join(file_path, file_name), 'wb') as outfile:
                outfile.write(self.get_file(os.sep.join(obj)))

    def to_remote(self, session):
        pass

    def _populate(self, overlay=True):
        """ To be overridden """
        pass

    def get_hierarchy(self, dimension, hierarchy=None):
        """ To be overridden """

    def _filter(self):
        c = self.config

        include = c.get('include_cube', '*')
        exclude = c.get('exclude_cube', '')
        self._cube_object = filter_list(self._cube_object, include, exclude, name_func=lambda x, extra: x['Name'])
        self._rule_object = filter_list(self._rule_object, include, exclude, name_func=lambda x, extra: x['Name'])
        self._view_list = filter_list(self._view_list, include, exclude, name_func=lambda x, extra: x[0])

        include = c.get('include_cube_view', '*/*')
        exclude = c.get('exclude_cube_view', '')
        self._view_list = filter_list(self._view_list, include, exclude, name_func=lambda x, extra: '/'.join(x))

        include = c.get('include_cube_view_data', '')
        exclude = c.get('exclude_cube_view_data', '')
        self._view_data_list = filter_list(self._view_list, include, exclude, name_func=lambda x, extra: '/'.join(x))

        include = c.get('include_rule', '*')
        exclude = c.get('exclude_rule', '')
        self._rule_object = filter_list(self._rule_object, include, exclude, name_func=lambda x, extra: x['Name'])

        include = c.get('include_dimension', '*')
        exclude = c.get('exclude_dimension', '')
        self._dimension_object = filter_list(self._dimension_object, include, exclude, name_func=lambda x, extra: x['Name'])
        self._hierarchy_list = filter_list(self._hierarchy_list, include, exclude, name_func=lambda x, extra: x[0])
        self._subset_list = filter_list(self._subset_list, include, exclude, name_func=lambda x, extra: x[0])

        for dimension in self._dimension_object:
            include = c.get('include_dimension_attribute', '*/*')
            exclude = c.get('exclude_dimension_attribute', '')

            dimension['Attributes'] = filter_list(dimension['Attributes'], include, exclude, name_func=lambda x, extra: '{}/{}'.format(extra, x[0]), extra=dimension['Name'])

        include = c.get('include_dimension_hierarchy', '*/*')
        exclude = c.get('exclude_dimension_hierarchy', '')
        self._hierarchy_list = filter_list(self._hierarchy_list, include, exclude, name_func=lambda x, extra: '/'.join(x))
        self._subset_list = filter_list(self._subset_list, include, exclude, name_func=lambda x, extra: '/'.join(x[:2]))

        include = c.get('include_dimension_hierarchy_subset', '*/*/*')
        exclude = c.get('exclude_dimension_hierarchy_subset', '')
        self._subset_list = filter_list(self._subset_list, include, exclude, name_func=lambda x, extra: '/'.join(x))

        include = c.get('include_process', '*')
        exclude = c.get('exclude_process', '')
        self._process_object = filter_list(self._process_object, include, exclude, name_func=lambda x, extra: x['Name'])

        include = c.get('include_file', '')
        exclude = c.get('exclude_file', '')
        self._file_list = filter_list(self._file_list, include, exclude, name_func=lambda x, extra: '/'.join(x))

    def _filter_hierarchy(self, dimension, hierarchy):
        # Filter elements for certain hierarchies
        include = self.config.get('include_dimension_hierarchy_element', '*/*')
        exclude = self.config.get('exclude_dimension_hierarchy_element', '')

        if not isinstance(include, list):
            include = [include]

        if not isinstance(exclude, list):
            exclude = [exclude]

        name = '{}/{}'.format(dimension, hierarchy['Name'])
        include_element = any([fnmatch(name, x) for x in include]) and not any([fnmatch(name, x) for x in exclude])
        if not include_element:
            hierarchy['Elements'] = []
            hierarchy['Edges'] = []
            hierarchy['DefaultMember'] = {}

        hierarchy.setdefault('Elements', [])
        hierarchy.setdefault('Edges', [])
        hierarchy.setdefault('Subsets', [])
        hierarchy.setdefault('DefaultMember', {})

        # Filter dimension hierarchy attributes
        include = self.config.get('include_dimension_hierarchy_attribute', '*/*/*')
        exclude = self.config.get('exclude_dimension_hierarchy_attribute', '')

        def name_func(obj, extra):
            return '{}/{}/{}'.format(extra['dimension_name'], extra['hierarchy_name'], obj['Name'])

        extra = {
            "dimension_name": dimension,
            "hierarchy_name": hierarchy['Name']
        }

        hierarchy['ElementAttributes'] = filter_list(hierarchy['ElementAttributes'], include, exclude, name_func=name_func, extra=extra)

        # Filter dimension hierarchy attributes from Elements
        def name_func(obj, extra):
            return '{}/{}/{}'.format(extra['dimension_name'], extra['hierarchy_name'], obj[0])

        extra = {
            "dimension_name": dimension,
            "hierarchy_name": hierarchy['Name']
        }

        for i, element in enumerate(hierarchy['Elements']):
            lst = filter_list(element['Attributes'], include, exclude, name_func=name_func, extra=extra)
            hierarchy['Elements'][i]['Attributes'] = lst

        # Filter dimension hierarchy attributes values
        include = self.config.get('include_dimension_hierarchy_attribute_value', '*/*/*')
        exclude = self.config.get('exclude_dimension_hierarchy_attribute_value', '')

        for i, element in enumerate(hierarchy['Elements']):
            lst = filter_list(element['Attributes'], include, exclude, name_func=name_func, extra=extra)
            hierarchy['Elements'][i]['Attributes'] = lst

    def _fix_generated_lines(self, text):
        try:
            split = text.split('\r\n')
            index = split.index('#****End: Generated Statements****')

            if index + 1 == len(split) or split[index + 1] != '':
                split.insert(index + 1, '')

            return '\r\n'.join(split)
        except Exception:
            return text

    def dump(self, data):
        if self.config.get('text_output_format', 'YAML').upper() == 'YAML':
            text = yaml.dump(data, Dumper=Dumper, width=255)
        else:
            text = json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)

        return text.encode('utf8')

    def load(self, fp):
        if self.config.get('text_output_format', 'YAML').upper() == 'YAML':
            data = yaml.safe_load(fp)
        else:
            data = json.load(fp)

        return data


class RemoteApplication(Application):
    def __init__(self, config, session=None, session_config=None):
        if session:
            self._connected = True
            self._address = session._tm1_rest._address
            self._address = session._tm1_rest._port
            self._session = session
            self._update_config()
        else:
            self._connected = False
            self._base_url = session_config.get('base_url', '')
            self._address = session_config.get('address', '')
            self._port = session_config.get('port', '')
            self._session_config = session_config

        super().__init__(config)

    def __str__(self):
        return 'url={} connected={}'.format(self._base_url, self._connected)

    def __repr__(self):
        return '<RemoteApplication ({})>'.format(self.__str__())

    @property
    def session(self):
        self.connect()
        return self._session

    def _populate(self, overlay=None):
        logger = logging.getLogger(__name__)

        self.connect()

        rest = self._session._tm1_rest

        c = self.config

        # Cubes & Rules
        try:
            request = '/api/v1/Cubes?$select=Name,Dimensions,Rules&$expand=Dimensions($select=Name)'
            response = rest.GET(request)
            result = json.loads(response.text)['value']

            self._cube_object = result

            # Remove sandbox dimension if present
            for cube in result:
                if cube['Dimensions'][0]['Name'] == 'Sandboxes':
                    cube['Dimensions'].remove(cube['Dimensions'][0])

            self._rule_object = [x.copy() for x in self._cube_object if x['Rules']]

            for cube in self._cube_object:
                if 'Rules' in cube:
                    cube.pop('Rules')
        except Exception:
            logger.exception('Exception occurred when populating cube and rule objects')
            raise

        # Views
        try:
            request = '/api/v1/Cubes?$select=Name,Views&$expand=Views($select=Name)'
            response = rest.GET(request)
            result = json.loads(response.text)['value']

            self._view_list = []
            for cube in result:
                for view in cube['Views']:
                    self._view_list.append((cube['Name'], view['Name']))
        except Exception:
            logger.exception('Exception occurred when cube views')
            raise

        # Subsets
        try:
            request = '/api/v1/Dimensions?$select=Name,Hierarchies&$expand=Hierarchies($select=Name,Subsets;$expand=Subsets($select=Name))'
            response = rest.GET(request)
            result = json.loads(response.text)['value']

            self._subset_list = []
            for dimension in result:
                for hierarchy in dimension['Hierarchies']:
                    for subset in hierarchy['Subsets']:
                        self._subset_list.append((dimension['Name'], hierarchy['Name'], subset['Name']))
        except Exception:
            logger.exception('Exception occurred when populating subset list')
            raise

        # Dimensions & Hierarchies
        try:
            request = '/api/v1/Dimensions?$select=Name,UniqueName,Attributes,Hierarchies&$expand=Hierarchies($expand=Elements($count;$top=0);$select=Name)'
            response = rest.GET(request)
            result = json.loads(response.text)['value']

            self._dimension_object = result

            self._hierarchy_list = []
            for dimension in self._dimension_object:
                for hierarchy in dimension['Hierarchies']:
                    self._hierarchy_list.append((dimension['Name'], hierarchy['Name']))
                # Remove Hierarchies
                dimension['Hierarchies'] = []
        except Exception:
            logger.exception('Exception occurred when populating dimension and hierarchy objects')
            raise

        # Processes
        procedures = ['PrologProcedure', 'MetadataProcedure', 'DataProcedure', 'EpilogProcedure']
        try:
            processes = self._session.processes.get_all()
            self._process_object = [json.loads(x._construct_body()) for x in processes]

            autoformat = c.get('autoformat_ti_process', True)

            for process in self._process_object:
                for procedure in procedures:
                    if autoformat:
                        try:
                            process[procedure] = format_procedure(process[procedure])
                        except Exception:
                            logger.warning('Auto formatting of TI process {} failed for {}. Using original formatting'.format(process['Name'], procedure))

                if 'DataSource' in process:
                    if 'password' in process['DataSource']:
                        del process['DataSource']['password']
        except Exception:
            logger.exception('Exception occurred when populating process objects')
            raise

        # Files
        if c.get('do_file_operations', False):
            try:
                process = c.get('file_to_blob_update_process', None)
                if process:
                    include = c.get('include_file', '')
                    if isinstance(include, str):
                        include = list(include)

                    exclude = c.get('exclude_file', '')
                    if isinstance(exclude, str):
                        exclude = list(exclude)

                    exclude.append('*.pyc')

                    data = {'Parameters': [
                        {'Name': 'pInclude', 'Value': json.dumps(include)},
                        {'Name': 'pExclude', 'Value': json.dumps(exclude)},
                    ]}

                    self._session.processes.execute(process, data)

                request = '/api/v1/Contents(\'Blobs\')/Contents?$select=Name&$filter=startswith(Name, \'tm1cm-\')'
                response = rest.GET(request)
                result = json.loads(response.text)['value']

                self._file_list = [base64.b32decode(x['Name'][6:], casefold=True).decode().split('/') for x in result]
            except Exception:
                logger.exception('Exception occurred when populating file list')
                raise

    def connect(self, session_config=None):
        if session_config:
            self._session_config = session_config

        if not self._connected:
            self._session = TM1Service(**self._session_config)

            self._connected = True
            self._update_config()

    def _update_config(self):
        request = '/api/v1/Configuration'
        response = self._session._tm1_rest.GET(request)
        result = json.loads(response.text)

        self._data_directory = result['DataBaseDirectory']

    def get_hierarchy(self, dimension, hierarchy):
        logger = logging.getLogger(__name__)

        self.connect()

        include = list(self.config.get('include_dimension_hierarchy_element', '*/*'))
        exclude = list(self.config.get('exclude_dimension_hierarchy_element', ''))

        name_comp = '{}/{}'.format(dimension, hierarchy)

        if any([fnmatch(name_comp, x) for x in include]) and not any([fnmatch(name_comp, x) for x in exclude]):
            request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')?$select=DefaultMember,ElementAttributes,Name,UniqueName,Edges,Elements&$expand=DefaultMember,ElementAttributes,Edges($select=ParentName,ComponentName,Weight),Elements($select=Name,UniqueName,Index,Type,Attributes)'.format(
                dimension, hierarchy)
        else:
            request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')?$select=DefaultMember,ElementAttributes,Name,UniqueName&$expand=DefaultMember,ElementAttributes'.format(dimension, hierarchy)

        try:
            response = self._session._tm1_rest.GET(request)
            result = json.loads(response.text)
            if '@odata.context' in result:
                del result['@odata.context']

            result.setdefault('Elements', [])
            result.setdefault('Edges', [])
            result.setdefault('Subsets', [])

            for element in result['Elements']:
                element.pop('Index')
                element.pop('UniqueName')

            result.pop('DefaultMember')

            self._filter_hierarchy(dimension, result)

            return result
        except Exception:
            logger.exception('Unable to get dimension hierarchy {}/{}'.format(dimension, hierarchy))
            raise

    def get_file(self, file):
        logger = logging.getLogger(__name__)

        self.connect()

        name = 'tm1cm-{}'.format(base64.b32encode(file.encode()).decode().lower())
        request = '/api/v1/Contents(\'Blobs\')/Contents(\'{}\')/Content'.format(name)

        try:
            response = self._session._tm1_rest.GET(request)

            return response.text.encode()
        except Exception:
            logger.exception('Unable to get file {} ({})'.format(file, name))
            raise

    def get_view(self, cube, view):
        logger = logging.getLogger(__name__)

        self.connect()

        view_service = self._session.cubes.views
        try:
            data = view_service.get_native_view(cube, view, False).body
            return json.loads(data)
        except Exception:
            logger.error('Unable to get cube view {}/{}, because it is invalid. Using default view'.format(cube, view))
            return self._construct_empty_view(cube, view)

    def get_view_data(self, cube, view):
        logger = logging.getLogger(__name__)

        self.connect()

        cell_service = self._session.cubes.cells
        rest = self._session._tm1_rest
        try:
            try:
                request = '/api/v1/Cubes(\'{}\')/tm1.Unlock'.format(cube)
                rest.POST(request)
                locked = True
            except Exception:
                locked = False

            data = cell_service.execute_view(cube, view, False, ['Value', 'Updateable'])
            restructed_data = [[*k, v['Value']] for k, v in data.items() if not v['Updateable'] & 0x10000000]

            if locked:
                request = '/api/v1/Cubes(\'{}\')/tm1.Lock'.format(cube)
                rest.POST(request)

            return restructed_data
        except Exception:
            logger.error('Unable to get cube view data for cube={} and view={}'.format(cube, view))
            raise

    def _construct_empty_view(self, cube, view):
        logger = logging.getLogger(__name__)

        self.connect()

        logger.info('Called for {}/{}'.format(cube, view))
        view = NativeView(cube, view, format_string='0.#########')

        rest = self._session._tm1_rest

        request = '/api/v1/Cubes(\'{}\')/Dimensions?$select=Name&$expand=Hierarchies($select=Name,DefaultMember;$expand=DefaultMember($select=Name))'.format(cube)
        response = rest.GET(request)
        result = json.loads(response.text)['value']

        for dimension in result:
            dim = dimension['Name']
            subset = AnonymousSubset(dim, dim, expression='{TM1SUBSETALL( [%s] )}' % dim)
            view.add_title(dimension['Name'], dimension['Hierarchies'][0]['DefaultMember']['Name'], subset)

        return json.loads(view.body, strict=False)

    def get_subset(self, dimension, hierarchy, subset):
        logger = logging.getLogger(__name__)

        self.connect()

        subset_service = self._session.dimensions.subsets
        try:
            return subset_service.get(subset, dimension, hierarchy, False).body_as_dict
        except Exception:
            logger.exception('Unable to get subset {}/{}/{}'.format(dimension, hierarchy, subset))
            raise


class LocalApplication(Application):

    def __init__(self, config, path):
        self.path = path

        super().__init__(config)

    def _populate(self, overlay=True):
        logger = logging.getLogger(__name__)
        c = self.config

        # Cubes & Rules
        try:
            result = []
            path = os.path.join(self.path, 'data', 'cube', '*.cube')
            for filename in iglob(path):
                with open(filename, 'rb') as fp:
                    result.append(self.load(fp))

            self._cube_object = result

            result = []
            path = os.path.join(self.path, 'data', 'rule', '*.rule')
            for filename in iglob(path):
                with open(filename, 'rb') as fp:
                    _, name = os.path.split(filename)
                    name = os.path.splitext(name)[0]
                    result.append({'Name': name, 'Rules': fp.read().decode('utf8')})

            self._rule_object = result
        except Exception:
            logger.exception('Exception occurred when populating cube and rule objects')
            raise

        # Views
        try:
            result = []
            view_path = os.path.join(self.path, 'data', 'view')
            path = os.path.join(view_path, '**', '*.view')
            for filename in iglob(path, recursive=True):
                if os.path.isfile(filename):
                    result.append(filename[len(view_path) + 1:-5].split(os.sep))

                self._view_list = result
        except Exception:
            logger.exception('Exception occurred when populating view objects')
            raise

        # View Data
        try:
            result = []
            view_path = os.path.join(self.path, 'data', 'view_data')
            path = os.path.join(view_path, '**', '*.view_data')
            for filename in iglob(path, recursive=True):
                if os.path.isfile(filename):
                    result.append(filename[len(view_path) + 1:-10].split(os.sep))

                self._view_data_list = result
        except Exception:
            logger.exception('Exception occurred when populating view data objects')
            raise

        # Subsets
        try:
            result = []
            subset_path = os.path.join(self.path, 'data', 'subset')
            path = os.path.join(subset_path, '**', '*.subset')
            for filename in iglob(path, recursive=True):
                if os.path.isfile(filename):
                    result.append(filename[len(subset_path) + 1:-7].split(os.sep))
            self._subset_list = result
        except Exception:
            logger.exception('Exception occurred when populating subset objects')
            raise

        # Dimensions & Hierarchies
        try:
            result = []
            path = os.path.join(self.path, 'data', 'dimension', '*.dimension')
            for filename in iglob(path):
                with open(filename, 'rb') as fp:
                    result.append(self.load(fp))
            self._dimension_object = result

            result = []
            hierarchy_path = os.path.join(self.path, 'data', 'hierarchy')
            path = os.path.join(hierarchy_path, '**', '*.hierarchy')
            for filename in iglob(path, recursive=True):
                if os.path.isfile(filename):
                    result.append(filename[len(hierarchy_path) + 1:-10].split(os.sep))
            self._hierarchy_list = result
        except Exception:
            logger.exception('Exception occurred when populating dimension and hierarchy objects')
            raise

        # Processes
        try:
            result = []
            path = os.path.join(self.path, 'data', 'process', '*.process')

            overlay_options = []
            if c.get('include_ti_queue', False):
                overlay_options.append('queue')
            if c.get('include_ti_overlay', False):
                overlay_options.append('metrics')

            autoformat = c.get('autoformat_ti_process', True)

            for filename in iglob(path):
                with open(filename, 'rb') as fp:
                    process_text = fp.read().decode('utf8')
                    process_properties = self.load(self._get_process_text(process_text, 'PropertiesProcedure'))

                    for procedure in ['PrologProcedure', 'MetadataProcedure', 'DataProcedure', 'EpilogProcedure']:
                        procedure_text = self._get_process_text(process_text, procedure)

                        if autoformat:
                            try:
                                procedure_text = format_procedure(procedure_text)
                            except Exception:
                                logger.warning('Auto formatting of TI process {} failed for {}. Using original formatting'.format(process_properties['Name'], procedure))

                        process_properties[procedure] = procedure_text

                    if 'DataSource' in process_properties:
                        if 'password' in process_properties['DataSource']:
                            del process_properties['DataSource']['password']

                    result.append(process_properties)

            self._process_object = result
        except Exception:
            logger.exception('Exception occurred when populating process objects')
            raise

        # Files
        try:
            result = []
            for folder in ['files', 'scripts']:
                path = os.path.join(self.path, folder, '**', '*')
                for filename in iglob(path, recursive=True):
                    if os.path.isfile(filename):
                        result.append(filename[len(self.path) + 1:].split(os.sep))

            self._file_list = result
        except Exception:
            logger.exception('Exception occurred when populating dimension and hierarchy objects')
            raise

    def get_hierarchy(self, dimension, hierarchy):
        logger = logging.getLogger(__name__)

        path = os.path.join(self.path, 'data', 'hierarchy', dimension)
        filename = '{}.hierarchy'.format(hierarchy)

        try:
            with open(os.path.join(path, filename), 'rb') as fp:
                result = self.load(fp)

                self._filter_hierarchy(dimension, result)
                return result
        except Exception:
            logger.exception('Unable to get hierarchy')
            raise

    def get_file(self, file):
        logger = logging.getLogger(__name__)

        path = os.path.join(self.path, os.sep.join(file.split('/')))

        try:
            with open(path, 'rb') as fp:
                return fp.read()
        except Exception:
            logger.exception('Unable to get file {}'.format(file))
            raise

    def get_view(self, cube, view):
        logger = logging.getLogger(__name__)

        path = os.path.join(self.path, 'data', 'view', cube, '{}.view'.format(view))

        try:
            with open(path, 'rb') as fp:
                return self.load(fp)
        except Exception:
            logger.exception('Unable to get cube view {}/{}'.format(cube, view))
            return {}

    def get_view_data(self, cube, view):
        logger = logging.getLogger(__name__)

        path = os.path.join(self.path, 'data', 'view_data', cube, '{}.view_data'.format(view))

        try:
            with open(path, 'rb') as fp:
                return self.load(fp)
        except Exception:
            logger.exception('Unable to get cube view data {}/{}'.format(cube, view))
            raise

    def get_subset(self, dimension, hierarchy, subset):
        logger = logging.getLogger(__name__)

        path = os.path.join(self.path, 'data', 'subset', dimension, hierarchy, '{}.subset'.format(subset))

        try:
            with open(path, 'rb') as fp:
                return self.load(fp)
        except Exception:
            logger.exception('Unable to get subset {}/{}/{}'.format(dimension, hierarchy, subset))
            raise

    @staticmethod
    def from_remote(app, path):
        remote = LocalApplication(app.config, path)

        remote._cube_object = app._cube_object
        remote._rule_object = app._rule_object
        remote._dimension_object = app._dimension_object
        remote._hierarchy_list = app._hierarchy_list
        remote._process_object = app._process_object
        remote._view_list = app._view_list
        remote._view_data_list = app._view_list
        remote._file_list = app._file_list
        remote._subset_list = app._subset_list

        return remote

    def _get_process_text(self, text, procedure):
        header = globals().get('{}_BEGIN'.format(procedure[:-9].upper()))
        footer = globals().get('{}_END'.format(procedure[:-9].upper()))
        start = text.index(header) + len(header)
        end = text.index(footer)

        process_text = text[start:end]
        process_text = process_text.replace('\r\n', '\n')
        process_text = '\r\n'.join(process_text.split('\n'))

        return process_text


PROPERTIES_BEGIN = """
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# BEGIN: PROPERTIES                                                           #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
""".lstrip()

PROPERTIES_END = """
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# END: PROPERTIES                                                             #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
""".rstrip()

PROLOG_BEGIN = """
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# BEGIN: PROLOG PROCEDURE                                                     #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #

"""

PROLOG_END = """

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# END: PROLOG PROCEDURE                                                       #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
""".rstrip()

METADATA_BEGIN = """
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# BEGIN: METADATA PROCEDURE                                                   #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #

"""

METADATA_END = """

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# END: METADATA PROCEDURE                                                     #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
""".rstrip()

DATA_BEGIN = """
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# BEGIN: DATA PROCEDURE                                                       #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #

"""

DATA_END = """

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# END: DATA PROCEDURE                                                         #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
""".rstrip()

EPILOG_BEGIN = """
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# BEGIN: EPILOG PROCEDURE                                                     #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #

"""

EPILOG_END = """

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
# END: EPILOG PROCEDURE                                                       #
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
""".rstrip()
