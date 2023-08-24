
import logging
import os
import TM1py

from git import Repo
from shutil import rmtree
from tempfile import mkdtemp

from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.operation import Operation, Ops

AUTHOR = 'tm1cm <tm1cm@local>'


class Migration:
    def __init__(self, source, target):
        logger = logging.getLogger(__name__)

        self.source = source
        self.target = target

        self.path = mkdtemp(prefix='tm1cm_')
        self.repo = Repo.init(self.path)

        if self.target:
            self.target.to_local(self.path, False)
            self.repo.git.add('*')
            self.repo.git.commit('-m', 'initial', author=AUTHOR)

            for folder in ['data', 'scripts', 'files']:
                self._git_rm_path(folder)
        else:
            self.repo.git.commit('--allow-empty', '-m', 'initial')

        self.source.to_local(self.path, True)
        if isinstance(self.source, RemoteApplication):
            self.source = LocalApplication.from_remote(self.source, self.path)

        # Patch TM1py to not delete attributes
        TM1py.Services.HierarchyService._update_element_attributes = _update_element_attributes

        try:
            self.repo.git.add('*')
        except Exception:
            logger.info('Unable to add new files, probably fine')

        self._compute_operations()

    @property
    def operations(self):
        return sorted(self._operations, key=lambda x: x.type)

    def do_operations(self, operations):
        logger = logging.getLogger(__name__)
        retry = []
        for operation in sorted(operations, key=lambda x: x.type):
            try:
                operation.do(self.target)
            except Exception:
                logger.error('Operation {} Failed, will retry at the end'.format(operation))
                retry.append(operation)

        for operation in retry:
            try:
                operation.do(self.target)
            except Exception:
                logger.error('Retry Operation {} Failed'.format(operation))

    def do_all_operations(self):
        self.do_operations(self.operations)

    def _get_operation_list(self, change_type, object_type, name, name_old=None):
        if change_type == 'R':
            a = self._get_operation_list('A', object_type, name)
            b = self._get_operation_list('D', object_type, name_old)
            return a + b
        else:
            action = 'DELETE' if change_type == 'D' else 'UPDATE'
            operation_type = getattr(Ops, '{}_{}'.format(action, object_type.upper()))
            if object_type in ['hierarchy', 'view', 'view_data', 'subset']:
                operation_args = name.split(os.sep)
            else:
                operation_args = (name,)

            return [Operation(self.source, operation_type, operation_args)]

    def _compute_operations(self):
        head_commit = self.repo.head.commit
        self._operations = []
        for diff_added in head_commit.diff(None):
            change_type = diff_added.change_type[:1]

            folder, sub_folder, *object_a = diff_added.a_path.split('/')
            object_a = os.sep.join(object_a)

            try:
                object_a_name, object_a_ext = object_a.rsplit('.', 1)
            except Exception:
                object_a_name = object_a

            _, _, *object_b = diff_added.b_path.split('/')
            object_b = os.sep.join(object_b)

            try:
                object_b_name, object_b_ext = object_b.rsplit('.', 1)
            except Exception:
                object_b_name = object_b

            if folder == 'data':
                op = self._get_operation_list(change_type, object_b_ext, object_b_name, object_a_name)
            else:
                op = self._get_operation_list(change_type, 'file', diff_added.b_path, diff_added.a_path)

            self._operations.extend(op)

    def _git_rm_path(self, folder):
        try:
            self.repo.git.rm('-r', folder)
            rmtree(os.path.join(self.path, folder), ignore_errors=True)
        except Exception:
            pass


def _update_element_attributes(self, hierarchy):
    # get existing attributes first.
    element_attributes = self.elements.get_element_attributes(dimension_name=hierarchy.dimension_name, hierarchy_name=hierarchy.name)
    element_attribute_names = [ea.name for ea in element_attributes]

    # write ElementAttributes that don't already exist !
    for element_attribute in hierarchy.element_attributes:
        if element_attribute not in element_attribute_names:
            self.elements.create_element_attribute(dimension_name=hierarchy.dimension_name, hierarchy_name=hierarchy.name, element_attribute=element_attribute)
