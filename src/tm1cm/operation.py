import base64
import json
import logging
import os
import re

from enum import IntEnum, auto

from TM1py.Objects.Cube import Cube
from TM1py.Objects.Dimension import Dimension
from TM1py.Objects.Rules import Rules
from TM1py.Objects.Process import Process
from TM1py.Objects.Hierarchy import Hierarchy


class Operation:

    def __init__(self, source, operation_type, arguments):
        self.source = source
        self.type = operation_type

        self._function = {
            Ops.DELETE_RULE: self._operation_delete_rule,
            Ops.DELETE_VIEW: self._operation_delete_view,
            Ops.DELETE_VIEW_DATA: self._operation_delete_view_data,
            Ops.DELETE_SUBSET: self._operation_delete_subset,
            Ops.DELETE_CUBE: self._operation_delete_cube,
            Ops.DELETE_HIERARCHY: self._operation_delete_hierarchy,
            Ops.DELETE_DIMENSION: self._operation_delete_dimension,
            Ops.DELETE_PROCESS: self._operation_delete_process,
            Ops.DELETE_FILE: self._operation_delete_file,
            Ops.UPDATE_RULE: self._operation_update_rule,
            Ops.UPDATE_CUBE: self._operation_update_cube,
            Ops.UPDATE_VIEW: self._operation_update_view,
            Ops.UPDATE_VIEW_DATA: self._operation_update_view_data,
            Ops.UPDATE_SUBSET: self._operation_update_subset,
            Ops.UPDATE_HIERARCHY: self._operation_update_hierarchy,
            Ops.UPDATE_DIMENSION: self._operation_update_dimension,
            Ops.UPDATE_PROCESS: self._operation_update_process,
            Ops.UPDATE_FILE: self._operation_update_file,
        }[self.type]

        self._arguments = arguments

    def __str__(self):
        return '{}: {}'.format(self.type.name, ', '.join(self._arguments))

    def __repr__(self):
        return '<Operation ({})>'.format(self.__str__())

    def __eq__(self, other):
        return self.type == other.type and self._arguments == other._arguments

    def __hash__(self):
        return hash(self.type.value + str(self._arguments))

    def do(self, target):
        self.target = target
        self._function(*self._arguments)

    def _operation_delete_process(self, process_name):
        """Deletes a turbo integrator process

        Args:
            process_name (str): Process name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(process_name))

        session = self.target.session
        try:
            if session.processes.exists(process_name):
                session.processes.delete(process_name)
                logger.info('Deleted process {}'.format(process_name))
        except Exception:
            logger.exception('Encountered error while deleting process {}'.format(process_name))
            raise

    def _operation_delete_rule(self, cube_name):
        """Deletes a rule from a cube

        Args:
            cube_name (str): Name of cube to delete rule from
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(cube_name))

        session = self.target.session
        try:
            if session.cubes.exists(cube_name):
                empty_rule = Rules('')
                cube = session.cubes.get(cube_name)
                cube.rules = empty_rule
                session.cubes.update(cube)
                logger.info('Removed rule from cube {}'.format(cube_name))
            else:
                logger.error('Unable to delete rule because cube {} does not exist'.format(cube_name))
        except Exception:
            logger.exception('Encountered error while deleting cube {}'.format(cube_name))
            raise

    def _operation_delete_cube(self, cube_name):
        """Deletes a cube

        Args:
            cube_name (str): Description
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(cube_name))

        session = self.target.session
        try:
            if session.cubes.exists(cube_name):
                session.cubes.delete(cube_name)
                logger.info('Deleted cube {}'.format(cube_name))
        except Exception:
            logger.exception('Encountered error while deleting cube {}'.format(cube_name))
            raise

    def _operation_delete_view(self, cube_name, view_name):
        """Deletes a cube view

        Args:
            cube_name (str): Description
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}/{}'.format(cube_name, view_name))

        session = self.target.session
        try:
            if session.cubes.views.exists(cube_name, view_name, False):
                session.cubes.views.delete(cube_name, view_name, False)
                logger.info('Deleted cube view {}/{}'.format(cube_name, view_name))
        except Exception:
            logger.exception('Encountered error while deleting cube view {}/{}'.format(cube_name, view_name))
            raise

    def _operation_delete_view_data(self, cube_name, view_name):
        pass

    def _operation_delete_subset(self, dimension_name, hierarchy_name, subset_name):
        """Deletes a subset

        Args:
            dimension_name (str): Dimension Name
            hierarchy_name (str): Hierarchy Name
            subset_name (str): Subset Name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}/{}/{}'.format(dimension_name, hierarchy_name, subset_name))

        session = self.target.session
        try:
            if session.dimensions.subsets.exists(subset_name, dimension_name, hierarchy_name, False):
                session.dimensions.subsets.delete(subset_name, dimension_name, hierarchy_name, False)
                logger.info('Deleted subset {}/{}/{}'.format(dimension_name, hierarchy_name, subset_name))
        except Exception:
            logger.exception('Encountered error while deleting subset {}/{}/{}'.format(dimension_name, hierarchy_name, subset_name))
            raise

    def _operation_delete_hierarchy(self, dimension_name, hierarchy_name):
        """Deletes a hierarchy from a dimension

        Args:
            dimension_name (str): Dimension name
            hierarchy_name (str): Hierarchy name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}:{}'.format(dimension_name, hierarchy_name))

        session = self.target.session

        try:
            if session.dimensions.hierarchies.exists(dimension_name, hierarchy_name):
                session.dimensions.hierarchies.delete(dimension_name, hierarchy_name)
                logger.info('Deleted hierarchy {}:{}'.format(dimension_name, hierarchy_name))
            else:
                logger.info('Unable to delete hierarchy {}:{} because it does not exist'.format(dimension_name, hierarchy_name))
        except Exception:
            logger.exception('Encountered error while deleting hierarchy {}:{}'.format(dimension_name, hierarchy_name))
            raise

    def _operation_delete_dimension(self, dimension_name):
        """Deletes a dimension

        Args:
            dimension_name (str): Dimension name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(dimension_name))

        session = self.target.session

        try:
            if session.dimensions.exists(dimension_name):
                session.dimensions.delete(dimension_name)
                logger.info('Deleted dimension {}'.format(dimension_name))
        except Exception:
            logger.exception('Encountered error while deleting dimension {}'.format(dimension_name))
            raise

    def _operation_delete_file(self, file_name):
        """Deletes a file

        Args:
            file_name (str): File name
        """

        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(file_name))

        session = self.target.session
        tm1_rest = session._tm1_rest

        try:
            name = 'tm1cm-{}'.format(base64.b32encode(file_name.encode()).decode())
            request = '/api/v1/Contents(\'Blobs\')/Contents(\'{}\')'.format(name)

            tm1_rest.DELETE(request)

            process = 'TAP.File.Delete File'
            params = {
                'Parameters': [
                    {
                        "Name": "pFile",
                        "Value": file_name
                    },
                    {
                        "Name": "pBaseDirectory",
                        "Value": os.path.split(self.target._data_directory)[0]
                    },
                ],
            }

            session.processes.execute(process, params)

        except Exception:
            logger.exception('Encountered error while deleting file {} {}'.format(file_name, name))
            raise

    def _operation_update_rule(self, cube_name):
        """updates a cube rule

        Args:
            cube_name (str): Cube name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(cube_name))

        session = self.target.session

        try:
            if session.cubes.exists(cube_name):
                cube = session.cubes.get(cube_name)
                cube.rules = Rules(self.source.rules[cube_name]['Rules'])
                session.cubes.update(cube)
            else:
                logger.error('Unable to update cube rule because cube {} does not exist'.format(cube_name))
        except Exception:
            logger.exception('Encountered error while updating rule in cube {}'.format(cube_name))
            raise

    def _operation_update_cube(self, cube_name):
        """Updates a cube

        Args:
            cube_name (str): Cube name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(cube_name))

        session = self.target.session

        try:
            cube = self.source.cubes[cube_name]
            dimensions = [x['Name'] for x in cube['Dimensions']]

            if session.cubes.exists(cube_name):
                if session.cubes.get(cube_name).dimensions != dimensions:
                    logger.info('Deleting cube {} for being different'.format(cube_name))
                    session.cubes.delete(cube_name)

            if not session.cubes.exists(cube_name):
                cube.setdefault('Rules', '')
                for dimension in dimensions:
                    if not session.dimensions.exists(dimension):
                        session.dimensions.create(Dimension(dimension))
                session.cubes.create(Cube.from_dict(cube))
        except Exception:
            logger.exception('Encountered error while updating cube {}'.format(cube_name))
            raise

    def _operation_update_view(self, cube_name, view_name):
        """Updates a cube

        Args:
            cube_name (str): Cube name
            view_name (str): View name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}/{}'.format(cube_name, view_name))

        session = self.target.session
        rest = session._tm1_rest
        try:
            view = json.dumps(self.source.get_view(cube_name, view_name), ensure_ascii=False)

            if session.cubes.views.exists(cube_name, view_name, False):
                request = '/api/v1/Cubes(\'{}\')/Views(\'{}\')'.format(cube_name, view_name)
                func = rest.PATCH
            else:
                request = '/api/v1/Cubes(\'{}\')/Views'.format(cube_name)
                func = rest.POST

            func(request, view)
        except Exception:
            logger.exception('Encountered error while updating cube view {}/{}'.format(cube_name, view_name))
            raise

    def _operation_update_view_data(self, cube_name, view_name):
        """Updates a cube

        Args:
            cube_name (str): Cube name
            view_name (str): View name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}/{}'.format(cube_name, view_name))

        session = self.target.session
        rest = session._tm1_rest
        try:
            try:
                request = '/api/v1/Cubes(\'{}\')/tm1.Unlock'.format(cube_name)
                rest.POST(request)
                locked = True
            except Exception:
                locked = False

            view_data = self.source.get_view_data(cube_name, view_name)
            for row in view_data:
                groups = [re.match(r'(\[)(.*?)(\]\.\[)(.*?)(\]\.\[)(.*?)(\])', a) for a in row[:-1]]
                dimensions = [g.group(2) for g in groups]
                elements = [g.group(6) for g in groups]
                value = row[-1]

                try:
                    session.cubes.cells.write_value(value, cube_name, elements, dimensions)
                except Exception:
                    logger.error('Error writing row {}:"{}" to {}'.format(elements, value, cube_name))

            if locked:
                request = '/api/v1/Cubes(\'{}\')/tm1.Lock'.format(cube_name)
                rest.POST(request)
        except Exception:
            logger.exception('Encountered error while updating cube view {}/{}'.format(cube_name, view_name))
            raise

    def _operation_update_subset(self, dimension_name, hierarchy_name, subset_name):
        """Updates a subset

        Args:
            dimension_name (str): Dimension Name
            hierarchy_name (str): Hierarchy Name
            subset_name (str): Subset Name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}/{}/{}'.format(dimension_name, hierarchy_name, subset_name))

        session = self.target.session
        rest = session._tm1_rest
        try:
            subset = json.dumps(self.source.get_subset(dimension_name, hierarchy_name, subset_name), ensure_ascii=False)
            if session.dimensions.subsets.exists(subset_name, dimension_name, hierarchy_name, False):
                request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets(\'{}\')'.format(dimension_name, hierarchy_name, subset_name)
                rest.PATCH(request, subset)
            else:
                request = '/api/v1/Dimensions(\'{}\')/Hierarchies(\'{}\')/Subsets'.format(dimension_name, hierarchy_name)
                rest.POST(request, subset)
        except Exception:
            logger.exception('Encountered error while updating subset {}/{}/{}'.format(dimension_name, hierarchy_name, subset_name))
            raise

    def _operation_update_hierarchy(self, dimension_name, hierarchy_name):
        """Updates a hierarchy on a dimension

        Args:
            dimension_name (str): Dimension Name
            hierarchy_name (str): Hierarchy Name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}:{}'.format(dimension_name, hierarchy_name))

        session = self.target.session

        try:
            data = self.source.get_hierarchy(dimension_name, hierarchy_name)
            hierarchy = Hierarchy.from_dict(data)

            if not session.dimensions.hierarchies.exists(dimension_name, hierarchy_name):
                session.dimensions.hierarchies.create(Hierarchy(hierarchy_name, dimension_name))

            session.dimensions.hierarchies.update_element_attributes(hierarchy)

            target_hierarchy = self.target.get_hierarchy(dimension_name, hierarchy_name)
            if target_hierarchy['Elements'] or data['Elements']:
                session.dimensions.hierarchies.update(hierarchy)

                attributes = [x['Name'] for x in data['ElementAttributes']]
                elements = [x['Name'] for x in data['Elements']]

                if len(attributes) == 0 or len(elements) == 0:
                    return

                attribute_list = ['[}ElementAttributes_%s].[}ElementAttributes_%s].[%s]' % (dimension_name, dimension_name, attribute) for attribute in attributes]
                element_list = ['[{}].[{}].[{}]'.format(dimension_name, hierarchy_name, element) for element in elements]
                mdx = 'SELECT { %s } ON ROWS, { %s } ON COLUMNS FROM [%s]' % (','.join(element_list), ','.join(attribute_list), '}ElementAttributes_' + dimension_name)

                cellset_id = session.cubes.cells.create_cellset(mdx)
                cellset = session.cubes.cells.execute_mdx(mdx, cell_properties=['Ordinal', 'Value', 'Updateable', 'RuleDerived'])

                updates = []
                for element in data['Elements']:
                    for attribute, value in element.get('Attributes', {}).items():
                        if attribute not in attributes:
                            continue
                        cellset_value = cellset.get(
                            ('[%s].[%s].[%s]' % (dimension_name, hierarchy_name, element['Name']), '[}ElementAttributes_%s].[}ElementAttributes_%s].[%s]' % (dimension_name, dimension_name, attribute)), {'Value': '_____'})
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
                                logger.info('Did not update {} for attribute {} in dimension {} because not updateable'.format(element['Name'], attribute, dimension_name))

                if updates:
                    tm1_rest = session._tm1_rest
                    request = "/api/v1/Cellsets('{}')/Cells".format(cellset_id)

                    tm1_rest.PATCH(request, json.dumps(updates, ensure_ascii=False))
                    session.cubes.cells.delete_cellset(cellset_id)
        except Exception:
            logger.exception('Encountered error while updating dimension {}'.format(dimension_name))
            raise

    def _operation_update_dimension(self, dimension_name):
        """Updates a dimension

        Args:
            dimension_name (str): Dimension name
        """
        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(dimension_name))

        session = self.target.session
        try:
            data = self.source.dimensions[dimension_name]
            dimension = Dimension.from_dict(data)

            if not session.dimensions.exists(dimension_name):
                session.dimensions.create(dimension)
        except Exception:
            logger.exception('Encountered error while updating dimension {}'.format(dimension_name))
            raise

    def _operation_update_process(self, process_name):
        """Updates a process

        Args:
            process_name (str): Process name
        """

        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(process_name))

        session = self.target.session
        try:
            process = self.source.processes[process_name]
            process = Process.from_dict(process)

            if session.processes.exists(process_name):
                session.processes.update(process)
            else:
                session.processes.create(process)

        except Exception:
            logger.exception('Encountered error while updating process {}'.format(process_name))
            raise

    def _operation_update_file(self, file_name):
        """Updates a file

        Args:
            file_name (str): File name
        """

        logger = logging.getLogger(__name__)
        logger.info('Called for {}'.format(file_name))

        session = self.target.session
        tm1_rest = session._tm1_rest

        try:
            name = 'tm1cm-{}'.format(base64.b32encode(file_name.encode()).decode().lower())
            request = '/api/v1/Contents(\'Blobs\')/Contents'
            data = {
                "@odata.type": "#ibm.tm1.api.v1.Document",
                "Name": name
            }

            try:
                tm1_rest.POST(request, json.dumps(data))
            except Exception:
                pass

            request = '/api/v1/Contents(\'Blobs\')/Contents(\'{}\')/Content'.format(name)
            data = self.source.get_file(file_name)

            try:
                url = tm1_rest._base_url + request
                url = url.replace(' ', '%20').replace('#', '%23')

                tm1_rest._s.patch(url=url, headers=tm1_rest._headers, data=data, verify=tm1_rest._verify)
            except Exception:
                logger.exception('unable to patch')

            process = 'TAP.File.Blob to File'
            params = {
                'Parameters': [
                    {
                        "Name": "pBlob",
                        "Value": name
                    },
                    {
                        "Name": "pFile",
                        "Value": file_name
                    },
                    {
                        "Name": "pBaseDirectory",
                        "Value": os.path.split(self.target._data_directory)[0]
                    },
                ],
            }

            session.processes.execute(process, params)
        except Exception:
            logger.exception('Encountered error while updating file {}'.format(file_name))
            raise


class Ops(IntEnum):

    """This enum defines all the possible operations that can take place as part
    of tm1cm against a TM1 application. It also defines the order in which those
    operations must take place.
    """

    DELETE_PROCESS = auto()
    DELETE_RULE = auto()
    DELETE_VIEW_DATA = auto()
    DELETE_VIEW = auto()
    DELETE_SUBSET = auto()
    DELETE_CUBE = auto()
    DELETE_HIERARCHY = auto()
    DELETE_DIMENSION = auto()
    DELETE_FILE = auto()
    UPDATE_PROCESS = auto()
    UPDATE_DIMENSION = auto()
    UPDATE_HIERARCHY = auto()
    UPDATE_CUBE = auto()
    UPDATE_RULE = auto()
    UPDATE_SUBSET = auto()
    UPDATE_VIEW = auto()
    UPDATE_VIEW_DATA = auto()
    UPDATE_FILE = auto()
