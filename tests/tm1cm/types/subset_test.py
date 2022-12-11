import unittest

from tests.tm1cm.types import base


class SubsetTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(SubsetTest, self).__init__(*args, **kwargs)

        self.type = self.subsets

        self.filter_config = {'exclude_dimension_hierarchy_subset': '*2'}
        self.filter_result = [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1', 'tm1cmTestSubset2')]

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.subsets)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.subsets)
        self._cleanup_remote_object(self.hierarchies)
        self._cleanup_remote_object(self.dimensions)


if __name__ == '__main__':
    unittest.main()
