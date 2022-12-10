import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.types.application import Application
from tm1cm.types.chore import Chore
from tm1cm.types.cube import Cube
from tm1cm.types.dimension import Dimension
from tm1cm.types.hierarchy import Hierarchy
from tm1cm.types.process import Process
from tm1cm.types.rule import Rule
from tm1cm.types.subset import Subset
from tm1cm.types.view import View


class Base(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(Base, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

        self.applications = Application(self.config)
        self.chores = Chore(self.config)
        self.cubes = Cube(self.config)
        self.dimensions = Dimension(self.config)
        self.hierarchies = Hierarchy(self.config)
        self.processes = Process(self.config)
        self.rules = Rule(self.config)
        self.subsets = Subset(self.config)
        self.views = View(self.config)

    def setUp(self):
        self._cleanup_remote()

    def tearDown(self):
        self._cleanup_remote()

    def _cleanup_remote_object(self, object_type):
        lst = object_type.list(self.remote_app)
        for name in lst:
            object_type.delete(self.remote_app, name)

    def _setup_remote_object(self, object_type):
        lst = object_type.list(self.local_app)
        lst = object_type.get(self.local_app, lst)
        for name, item in lst:
            object_type.update(self.remote_app, name, item)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.applications)
        self._cleanup_remote_object(self.chores)
        self._cleanup_remote_object(self.processes)
        self._cleanup_remote_object(self.views)
        self._cleanup_remote_object(self.rules)
        self._cleanup_remote_object(self.cubes)
        self._cleanup_remote_object(self.subsets)
        self._cleanup_remote_object(self.hierarchies)
        self._cleanup_remote_object(self.dimensions)


if __name__ == '__main__':
    unittest.main()
