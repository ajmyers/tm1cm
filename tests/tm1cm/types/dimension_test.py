import unittest

from tests.tm1cm.types import base
from tm1cm.types.dimension import Dimension


class DimensionTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(DimensionTest, self).__init__(*args, **kwargs)

    def test_filter_local(self):
        config = {**self.config, **{'exclude_dimension': 'tm1cmTestCube01*'}}
        dimensions = Dimension(config)

        original = dimensions.list(self.local_app)
        original = dimensions.filter(self.local_app, original)

        self.assertEqual(original, ['tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'exclude_dimension': '*01_*'}}
        dimensions = Dimension(config)

        lst = dimensions.list(self.remote_app)

        self.assertEqual(lst, ['tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

    def test_get_local(self):
        dimensions = Dimension(self.config)

        lst = dimensions.list(self.local_app)
        lst = dimensions.get(self.local_app, lst)

        self.assertEqual(lst, [('tm1cmTestCube01_Dim1', {'Name': 'tm1cmTestCube01_Dim1'}), ('tm1cmTestCube01_Dim2', {'Name': 'tm1cmTestCube01_Dim2'}), ('tm1cmTestCube02_Dim1', {'Name': 'tm1cmTestCube02_Dim1'}),
                               ('tm1cmTestCube02_Dim2', {'Name': 'tm1cmTestCube02_Dim2'}), ('tm1cmTestCube02_Dim3', {'Name': 'tm1cmTestCube02_Dim3'})])

    def test_get_remote(self):
        self._setup_remote()

        dimensions = Dimension(self.config)

        lst = dimensions.list(self.remote_app)
        lst = dimensions.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        dimensions = Dimension(self.config)

        lst = (dimensions.list(self.local_app))

        self.assertEqual(lst, ['tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim2', 'tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

    def test_list_remote(self):
        self._setup_remote()

        dimensions = Dimension(self.config)

        lst = dimensions.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        dimensions = Dimension(self.config)

        original = dimensions.list(self.local_app)
        original = dimensions.get(self.local_app, original)

        for name, item in original:
            dimensions.update(self.temp_app, name, item)

        modified = dimensions.list(self.temp_app)
        modified = dimensions.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.dimensions)


if __name__ == '__main__':
    unittest.main()
