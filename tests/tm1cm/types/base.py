import itertools
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


class Wrapper:
    class Base(unittest.TestCase):

        def __init__(self, *args, **kwargs):
            super(Wrapper.Base, self).__init__(*args, **kwargs)

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

            self.maxDiff = None

        def setUp(self):
            self._cleanup_remote()

        def tearDown(self):
            self._cleanup_remote()

        def test_list_local(self):
            self._test_list(remote=False)

        def test_list_remote(self):
            self._test_list(remote=True)

        def test_filter_local(self):
            config = {**self.config, **self.filter_config}
            filter_type = self.type.__class__(config)
            self._test_filter(filter_type, self.filter_result, remote=False)

        def test_filter_remote(self):
            config = {**self.config, **self.filter_config}
            filter_type = self.type.__class__(config)
            self._test_filter(filter_type, self.filter_result, remote=True)

        def test_get_local(self):
            self._test_get(remote=False)

        def test_get_remote(self):
            self._test_get(remote=True)

        def test_update(self):
            source_list = self.type.list(self.local_app)
            source_items = self.type.get(self.local_app, source_list)

            self._setup_remote()

            for item, index in itertools.product(source_items, range(3)):
                self.type.update(self.remote_app, *item)
                self.type.update(self.temp_app, *item)

            local_items = self.type.get(self.temp_app, source_list)
            remote_items = self.type.get(self.remote_app, source_list)

            self.assertListEqual(local_items, remote_items)

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

        def _test_list(self, remote=True):
            source, target = self._get_source_target(remote)

            source_list = self.type.list(source)

            if remote:
                self._setup_remote()
            else:
                source_items = self.type.get(source, source_list)
                for name, item in source_items:
                    self.type.update(target, name, item)

            target_list = self.type.list(target)

            self.assertListEqual(source_list, target_list)

        def _test_filter(self, filter_type, result, remote=True):
            app = self.remote_app if remote else self.local_app

            if remote:
                self._setup_remote()

            original = set(self.type.list(app))
            filtered = set(filter_type.list(app))

            self.assertTrue(len(original) > len(filtered) > 0)
            self.assertSetEqual(original - filtered, set(result))

        def _test_get(self, remote=True):
            source, target = self._get_source_target(remote)

            source_list = self.type.list(source)
            source_items = self.type.get(source, source_list)

            if remote:
                self._setup_remote()
            else:
                for name, item in source_items:
                    self.type.update(target, name, item)

            target_list = self.type.list(target)
            target_items = self.type.get(target, target_list)

            self.assertListEqual(source_list, target_list)
            self.assertListEqual(source_items, target_items)

        def _get_source_target(self, remote=False):
            if remote:
                return self.local_app, self.remote_app
            else:
                return self.local_app, self.temp_app


if __name__ == '__main__':
    unittest.main()
