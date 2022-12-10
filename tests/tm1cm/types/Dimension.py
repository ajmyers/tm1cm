import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Dimension import Dimension


class DimensionTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(DimensionTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

    def setUp(self):
        self._cleanup_remote()
        
    def test_filter_local(self):
        config = {**self.config, **{'include_dimension': '*', 'exclude_dimension': 'tm1cmTestCube01*'}}
        dimensions = Dimension(config)

        original = dimensions.list(self.local_app)
        original = dimensions.filter(self.local_app, original)

        self.assertEqual(original, ['tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_dimension': 'tm1cm*', 'exclude_dimension': '*01_*'}}
        dimensions = Dimension(config)

        lst = dimensions.list(self.remote_app)

        self.assertEqual(lst, ['tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

        self._cleanup_remote()

    def test_get_local(self):
        dimensions = Dimension(self.config)

        lst = dimensions.list(self.local_app)
        lst = dimensions.get(self.local_app, lst)

        self.assertEqual(lst, [('tm1cmTestCube01_Dim1', {'Name': 'tm1cmTestCube01_Dim1'}), ('tm1cmTestCube01_Dim2', {'Name': 'tm1cmTestCube01_Dim2'}), ('tm1cmTestCube02_Dim1', {'Name': 'tm1cmTestCube02_Dim1'}),
                               ('tm1cmTestCube02_Dim2', {'Name': 'tm1cmTestCube02_Dim2'}), ('tm1cmTestCube02_Dim3', {'Name': 'tm1cmTestCube02_Dim3'})])

    def test_get_remote(self):
        dimensions = Dimension(self.config)

        lst = dimensions.list(self.remote_app)
        lst = dimensions.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        dimensions = Dimension(self.config)

        lst = (dimensions.list(self.local_app))

        self.assertEqual(lst, ['tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim2', 'tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

    def test_list_remote(self):
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
        self._cleanup_remote()

    def _setup_remote(self):
        config = {**self.config, **{'include_dimension': 'tm1cm*', 'exclude_dimension': ''}}
        dimensions = Dimension(config)

        lst = dimensions.list(self.local_app)
        lst = dimensions.get(self.local_app, lst)

        for name, item in lst:
            dimensions.update(self.remote_app, name, item)

    def _cleanup_remote(self):
        config = {**self.config, **{'include_dimension': 'tm1cm*', 'exclude_dimension': ''}}
        dimensions = Dimension(config)

        lst = dimensions.list(self.local_app)
        lst = dimensions.get(self.local_app, lst)

        for name, _ in lst:
            self.remote_app.session.dimensions.delete(name)


if __name__ == '__main__':
    unittest.main()
