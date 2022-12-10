import unittest

from tests.tm1cm.types import base
from tm1cm.types.view import View


class ViewTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(ViewTest, self).__init__(*args, **kwargs)

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

    def test_get_local(self):
        views = View(self.config)

        lst = views.list(self.local_app)
        lst = views.get(self.local_app, lst)

        self.assertEqual(lst, [(('tm1cmTestCube01', 'tm1cmTestCube01_View1'),
                                {'Columns': [{'Subset': {'Name': 'tm1cmTestSubset', 'Hierarchy': {'Name': 'tm1cmTestCube01_Dim1', 'Dimension': {'Name': 'tm1cmTestCube01_Dim1'}}}}], 'FormatString': '0.#########',
                                 'Rows': [{'Subset': {'Alias': '', 'Expression': '{ [tm1cmTestCube01_Dim2].[tm1cmTestCube01_Dim2].Members }', 'Hierarchy': {'Name': 'tm1cmTestCube01_Dim2', 'Dimension': {'Name': 'tm1cmTestCube01_Dim2'}}}}],
                                 'SuppressEmptyColumns': False, 'SuppressEmptyRows': False, 'Titles': [], 'Name': 'tm1cmTestCube01_View1', '@odata.type': '#ibm.tm1.api.v1.NativeView'})])

    def test_get_remote(self):
        self._setup_remote()

        views = View(self.config)

        lst = views.list(self.remote_app)
        lst = views.get(self.remote_app, [lst[0]])

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        views = View(self.config)

        lst = views.list(self.local_app)

        self.assertEqual(lst, [('tm1cmTestCube01', 'tm1cmTestCube01_View1')])

    def test_list_remote(self):
        self._setup_remote()

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

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.subsets)
        self._setup_remote_object(self.cubes)
        self._setup_remote_object(self.views)


if __name__ == '__main__':
    unittest.main()
