import unittest

from tests.tm1cm.types import base


class HierarchyTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(HierarchyTest, self).__init__(*args, **kwargs)

        self.type = self.hierarchies

        self.filter_config = {'exclude_dimension_hierarchy': '*Dim1'}
        self.filter_result = [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1')]

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)


if __name__ == '__main__':
    unittest.main()
