import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Dimension import Dimension
from tm1cm.types.Hierarchy import Hierarchy


class HierarchyTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(HierarchyTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

    def setUp(self):
        self._cleanup_remote()

    def test_filter_local(self):
        config = {**self.config, **{'include_dimension_hierarchy': 'tm1cm*', 'exclude_dimension_hierarchy': ''}}
        hierarchies = Hierarchy(config)

        original = hierarchies.list(self.local_app)
        original = hierarchies.filter(self.local_app, original)

        self.assertEqual(original, [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1'), ('tm1cmTestCube01_Dim2', 'tm1cmTestCube01_Dim2')])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_dimension_hierarchy': 'tm1cm*', 'exclude_dimension_hierarchy': '*Dim1'}}
        hierarchies = Hierarchy(config)

        lst = hierarchies.list(self.remote_app)

        self.assertEqual(lst, [('tm1cmTestCube01_Dim2', 'tm1cmTestCube01_Dim2')])

        self._cleanup_remote()

    def test_get_local(self):
        config = {**self.config, **{
            'include_dimension_hierarchy': 'tm1cm*/*',
            'exclude_dimension_hierarchy': '',
            'include_dimension_hierarchy_element': 'tm1cm*/*',
            'exclude_dimension_hierarchy_element': '',
            'include_dimension_hierarchy_edge': 'tm1cm*/*',
            'exclude_dimension_hierarchy_edge': '',
            'include_dimension_hierarchy_attribute': 'tm1cm*/*',
            'exclude_dimension_hierarchy_attribute': '',
            'include_dimension_hierarchy_attribute_value': 'tm1cm*/*/*',
            'exclude_dimension_hierarchy_attribute_value': ''
        }}

        hierarchies = Hierarchy(config)

        lst = hierarchies.list(self.local_app)
        lst = hierarchies.get(self.local_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_get_remote(self):
        config = {**self.config, **{
            'include_dimension_hierarchy': '}Clients/*',
            'exclude_dimension_hierarchy': '',
            'include_dimension_hierarchy_element': '*/*',
            'exclude_dimension_hierarchy_element': '',
            'include_dimension_hierarchy_edge': '*/*',
            'exclude_dimension_hierarchy_edge': '',
            'include_dimension_hierarchy_attribute': '*/*',
            'exclude_dimension_hierarchy_attribute': '',
            'include_dimension_hierarchy_attribute_value': '*/*/*',
            'exclude_dimension_hierarchy_attribute_value': ''
        }}

        hierarchies = Hierarchy(config)

        lst = hierarchies.list(self.remote_app)
        lst = hierarchies.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        hierarchies = Hierarchy(self.config)

        lst = hierarchies.list(self.local_app)

        self.assertEqual(lst, [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1'),
                               ('tm1cmTestCube01_Dim2', 'tm1cmTestCube01_Dim2')])

    def test_list_remote(self):
        hierarchies = Hierarchy(self.config)

        lst = hierarchies.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        hierarchies = Hierarchy(self.config)

        original = hierarchies.list(self.local_app)
        original = hierarchies.get(self.local_app, original)

        for name, item in original:
            hierarchies.update(self.temp_app, name, item)

        modified = hierarchies.list(self.temp_app)
        modified = hierarchies.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()

        config = {**self.config, **{
            'include_dimension_hierarchy': 'tm1cm*/*',
            'exclude_dimension_hierarchy': '',
            'include_dimension_hierarchy_element': 'tm1cm*/*',
            'exclude_dimension_hierarchy_element': '',
            'include_dimension_hierarchy_edge': 'tm1cm*/*',
            'exclude_dimension_hierarchy_edge': '',
            'include_dimension_hierarchy_attribute': 'tm1cm*/*',
            'exclude_dimension_hierarchy_attribute': '*TestIgnore',
            'include_dimension_hierarchy_attribute_value': 'tm1cm*/*/*',
            'exclude_dimension_hierarchy_attribute_value': ''
        }}
        hierarchies = Hierarchy(config)

        original = hierarchies.list(self.local_app)
        original = hierarchies.get(self.local_app, original)

        modified = hierarchies.list(self.remote_app)
        modified = hierarchies.get(self.remote_app, modified)

        self.assertEqual(original, modified)

        self._cleanup_remote()

    def _setup_remote(self):
        config = {**self.config, **{
            'include_dimension_hierarchy': 'tm1cm*/*',
            'exclude_dimension_hierarchy': '',
            'include_dimension_hierarchy_element': 'tm1cm*/*',
            'exclude_dimension_hierarchy_element': '',
            'include_dimension_hierarchy_edge': 'tm1cm*/*',
            'exclude_dimension_hierarchy_edge': '',
            'include_dimension_hierarchy_attribute': 'tm1cm*/*',
            'exclude_dimension_hierarchy_attribute': '*TestIgnore',
            'include_dimension_hierarchy_attribute_value': 'tm1cm*/*/*',
            'exclude_dimension_hierarchy_attribute_value': ''
        }}
        hierarchies = Hierarchy(config)

        lst = hierarchies.list(self.local_app)
        lst = hierarchies.get(self.local_app, lst)

        for name, item in lst:
            hierarchies.update(self.remote_app, name, item)

    def _cleanup_remote(self):
        config = {**self.config, **{
            'include_dimension': 'tm1cm*',
            'exclude_dimension': '',
            'include_dimension_hierarchy': 'tm1cm*/*',
            'exclude_dimension_hierarchy': '',
            'include_dimension_hierarchy_element': 'tm1cm*/*',
            'exclude_dimension_hierarchy_element': '',
            'include_dimension_hierarchy_edge': 'tm1cm*/*',
            'exclude_dimension_hierarchy_edge': '',
            'include_dimension_hierarchy_attribute': 'tm1cm*/*',
            'exclude_dimension_hierarchy_attribute': '',
            'include_dimension_hierarchy_attribute_value': 'tm1cm*/*/*',
            'exclude_dimension_hierarchy_attribute_value': ''
        }}
        dimensions = Dimension(config)

        lst = dimensions.list(self.remote_app)
        lst = dimensions.get(self.remote_app, lst)

        for name, item in lst:
            dimensions.delete(self.remote_app, name, item)


if __name__ == '__main__':
    unittest.main()
