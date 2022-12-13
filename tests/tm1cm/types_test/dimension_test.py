import unittest

from tests.tm1cm.types_test import base


class DimensionTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(DimensionTest, self).__init__(*args, **kwargs)

        self.type = self.dimensions

        self.filter_config = {'exclude_dimension': 'tm1cmTestCube01*'}
        self.filter_result = [('tm1cmTestCube01_Dim1'), ('tm1cmTestCube01_Dim2')]

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.dimensions)


if __name__ == '__main__':
    unittest.main()
