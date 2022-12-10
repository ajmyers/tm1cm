import unittest

from tests.tm1cm.types import base
from tm1cm.types.subset import Subset


class SubsetTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(SubsetTest, self).__init__(*args, **kwargs)

    def test_filter_local(self):
        config = {**self.config, **{'exclude_dimension_hierarchy_subset': '*2'}}
        subsets = Subset(config)

        original = subsets.list(self.local_app)
        original = subsets.filter(self.local_app, original)

        self.assertEqual(original, [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset')])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'exclude_dimension_hierarchy_subset': '*2'}}
        subsets = Subset(config)

        lst = subsets.list(self.remote_app)

        self.assertEqual(lst, [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset')])

    def test_get_local(self):
        subsets = Subset(self.config)

        lst = subsets.list(self.local_app)
        lst = subsets.get(self.local_app, lst)

        self.assertEqual(lst, [(('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset'), {'Alias': '', 'Expression': 'TM1SORT(TM1FILTERBYLEVEL(TM1SUBSETALL( [tm1cmTestCube01_Dim1] ),0),ASC)', 'Name': 'tm1cmTestSubset'}),
                               (('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset2'), {'Alias': '', 'Elements': [{'Name': 'Test Element 1'}, {'Name': 'Test Element 2'}], 'Name': 'tm1cmTestSubset2'})])

    def test_get_remote(self):
        self._setup_remote()

        subsets = Subset(self.config)

        lst = subsets.list(self.remote_app)
        lst = subsets.get(self.remote_app, [lst[0]])

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        subsets = Subset(self.config)

        lst = (subsets.list(self.local_app))

        self.assertEqual(lst, [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset'),
                               ('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset2')])

    def test_list_remote(self):
        self._setup_remote()

        subsets = Subset(self.config)

        lst = subsets.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        subsets = Subset(self.config)

        original = subsets.list(self.local_app)
        original = subsets.get(self.local_app, original)

        for name, item in original:
            subsets.update(self.temp_app, name, item)

        modified = subsets.list(self.temp_app)
        modified = subsets.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.subsets)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.dimensions)


if __name__ == '__main__':
    unittest.main()
