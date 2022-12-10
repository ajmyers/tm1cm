import unittest

from tests.tm1cm.types import base
from tm1cm.types.hierarchy import Hierarchy


class HierarchyTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(HierarchyTest, self).__init__(*args, **kwargs)

    def test_filter_local(self):
        # TODO, Filter Local
        config = {**self.config, **{'include_dimension_hierarchy': 'tm1cm*', 'exclude_dimension_hierarchy': ''}}
        hierarchies = Hierarchy(config)

        original = hierarchies.list(self.local_app)
        original = hierarchies.filter(self.local_app, original)

        self.assertEqual(original, [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1'), ('tm1cmTestCube01_Dim2', 'tm1cmTestCube01_Dim2')])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'exclude_dimension_hierarchy': '*Dim1'}}
        hierarchies = Hierarchy(config)

        lst = hierarchies.list(self.remote_app)

        self.assertEqual(lst, [('tm1cmTestCube01_Dim2', 'tm1cmTestCube01_Dim2')])

        self._cleanup_remote()

    def test_get_local(self):
        hierarchies = Hierarchy(self.config)

        lst = hierarchies.list(self.local_app)
        lst = hierarchies.get(self.local_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_get_remote(self):
        self._setup_remote()

        hierarchies = Hierarchy(self.config)

        lst = hierarchies.list(self.remote_app)
        lst = hierarchies.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        hierarchies = Hierarchy(self.config)

        lst = hierarchies.list(self.local_app)

        self.assertEqual(lst, [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1'),
                               ('tm1cmTestCube01_Dim2', 'tm1cmTestCube01_Dim2')])

    def test_list_remote(self):
        self._setup_remote()

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
            'exclude_dimension_hierarchy_attribute': '*TestIgnore',
        }}
        hierarchies = Hierarchy(config)

        original = hierarchies.list(self.local_app)
        original = hierarchies.get(self.local_app, original)

        modified = hierarchies.list(self.remote_app)
        modified = hierarchies.get(self.remote_app, modified)

        self.assertEqual(original, modified)

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)


if __name__ == '__main__':
    unittest.main()
