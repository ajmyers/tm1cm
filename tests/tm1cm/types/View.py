import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Cube import Cube
from tm1cm.types.Dimension import Dimension
from tm1cm.types.Hierarchy import Hierarchy
from tm1cm.types.Subset import Subset
from tm1cm.types.View import View


class ViewTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(ViewTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())
        # self.temp_app = LocalApplication(self.config, '/var/folders/8q/q77h38t92td3rw1y4l_pxpr80000gn/T/tmpqteqi_59')

    def test_filter_local(self):
        config = {**self.config, **{'include_cube_view': 'tm1cm*', 'exclude_subset': '*2'}}
        views = View(config)

        original = views.list(self.local_app)
        original = views.filter(self.local_app, original)

        self.assertEqual(original, [('tm1cmTestCube01', 'tm1cmTestCube01_View1')])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_cube_view': 'tm1cm*', 'exclude_subset': ''}}
        views = View(config)

        lst = views.list(self.remote_app)

        self.assertEqual(lst, [('tm1cmTestCube01', 'tm1cmTestCube01_View1')])

        self._cleanup_remote()

    def test_get_local(self):
        views = View(self.config)

        lst = views.list(self.local_app)
        lst = views.get(self.local_app, lst)

        self.assertEqual(lst, [(('tm1cmTestCube01', 'tm1cmTestCube01_View1'),
                                {'Columns': [{'Subset': {'Name': 'tm1cmTestSubset', 'Hierarchy': {'Name': 'tm1cmTestCube01_Dim1', 'Dimension': {'Name': 'tm1cmTestCube01_Dim1'}}}}], 'FormatString': '0.#########',
                                 'Rows': [{'Subset': {'Alias': '', 'Expression': '{ [tm1cmTestCube01_Dim2].[tm1cmTestCube01_Dim2].Members }', 'Hierarchy': {'Name': 'tm1cmTestCube01_Dim2', 'Dimension': {'Name': 'tm1cmTestCube01_Dim2'}}}}],
                                 'SuppressEmptyColumns': False, 'SuppressEmptyRows': False, 'Titles': [], 'Name': 'tm1cmTestCube01_View1', '@odata.type': '#ibm.tm1.api.v1.NativeView'})])

    def test_get_remote(self):
        views = View(self.config)

        lst = views.list(self.remote_app)
        lst = views.get(self.remote_app, [lst[0]])

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        views = View(self.config)

        lst = views.list(self.local_app)

        self.assertEqual(lst, [('tm1cmTestCube01', 'tm1cmTestCube01_View1')])

    def test_list_remote(self):
        views = View(self.config)

        lst = views.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        views = View(self.config)

        original = views.list(self.local_app)
        original = views.get(self.local_app, original)

        for name, item in original:
            views.update(self.temp_app, name, item)

        modified = views.list(self.temp_app)

        modified = views.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()
        self._cleanup_remote()

    def _setup_remote(self):
        # Setup Dimensions/Hierarchies
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

        # Setup Cube
        config = {**self.config, **{
            'include_cube': 'tm1cm*/*',
            'exclude_cube': ''
        }}
        cubes = Cube(config)

        lst = cubes.list(self.local_app)
        lst = cubes.get(self.local_app, lst)

        for name, item in lst:
            cubes.update(self.remote_app, name, item)

        # Setup Subsets
        config = {**self.config, **{'include_subset': 'tm1cm*', 'exclude_subset': ''}}
        subsets = Subset(config)

        lst = subsets.list(self.local_app)
        lst = subsets.get(self.local_app, lst)

        for name, item in lst:
            subsets.update(self.remote_app, name, item)

        # Setup Views
        config = {**self.config, **{'include_cube_view': 'tm1cm*', 'exclude_cube_view': ''}}
        views = View(config)

        lst = views.list(self.local_app)
        lst = views.get(self.local_app, lst)

        for name, item in lst:
            views.update(self.remote_app, name, item)

    def _cleanup_remote(self):
        # Setup Cube
        config = {**self.config, **{
            'include_cube': 'tm1cm*/*',
            'exclude_cube': ''
        }}
        cubes = Cube(config)

        lst = cubes.list(self.local_app)
        lst = cubes.get(self.local_app, lst)

        for name, item in lst:
            cubes.delete(self.remote_app, name, item)

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
