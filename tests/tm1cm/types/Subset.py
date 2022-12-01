import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Subset import Subset


class SubsetTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(SubsetTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

    def test_filter_local(self):
        config = {**self.config, **{'include_subset': '*', 'exclude_subset': ''}}
        subsets = Subset(config)

        original = subsets.list(self.local_app)
        original = subsets.filter(self.local_app, original)

        self.assertEqual(original, ['tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', ''])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_subset': 'tm1cm*', 'exclude_subset': ''}}
        subsets = Subset(config)

        lst = subsets.list(self.remote_app)

        self.assertEqual(lst, ['tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

        self._cleanup_remote()

    def test_get_local(self):
        subsets = Subset(self.config)

        lst = subsets.list(self.local_app)
        lst = subsets.get(self.local_app, lst)

        self.assertEqual(lst, [{'Name': 'tm1cmTestCube01_Dim1'}, {'Name': 'tm1cmTestCube01_Dim2'}, {'Name': 'tm1cmTestCube02_Dim1'}, {'Name': 'tm1cmTestCube02_Dim2'}, {'Name': 'tm1cmTestCube02_Dim3'}])

    def test_get_remote(self):
        subsets = Subset(self.config)

        lst = subsets.list(self.remote_app)
        lst = subsets.get(self.remote_app, lst)

        import pprint
        pprint.pprint(lst)
        print(lst)
        return

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        subsets = Subset(self.config)

        lst = (subsets.list(self.local_app))

        self.assertEqual(lst, ['tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim2', 'tm1cmTestCube02_Dim1', 'tm1cmTestCube02_Dim2', 'tm1cmTestCube02_Dim3'])

    def test_list_remote(self):
        subsets = Subset(self.config)

        lst = subsets.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        subsets = Subset(self.config)

        original = subsets.list(self.local_app)
        original = subsets.get(self.local_app, original)

        for item in original:
            subsets.update(self.temp_app, item)

        modified = subsets.list(self.temp_app)
        modified = subsets.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()
        self._cleanup_remote()

    def _setup_remote(self):
        config = {**self.config, **{'include_subset': 'tm1cm*', 'exclude_subset': ''}}
        subsets = Subset(config)

        lst = subsets.list(self.local_app)
        lst = subsets.get(self.local_app, lst)

        for item in lst:
            subsets.update(self.remote_app, item)

    def _cleanup_remote(self):
        config = {**self.config, **{'include_subset': 'tm1cm*', 'exclude_subset': ''}}
        subsets = Subset(config)

        lst = subsets.list(self.local_app)
        lst = subsets.get(self.local_app, lst)

        for item in lst:
            self.remote_app.session.subsets.delete(item['Name'])


if __name__ == '__main__':
    unittest.main()
