import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Chore import Chore
from tm1cm.types.Process import Process


class ChoreTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(ChoreTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

    def setUp(self):
        self._cleanup_remote()
        
    def test_filter_local(self):
        config = {**self.config, **{'include_chore': 'tm1cm*', 'exclude_chore': '*1'}}
        chores = Chore(config)

        original = chores.list(self.local_app)
        original = chores.filter(self.local_app, original)

        self.assertEqual(original, ['tm1cm.TestChore2'])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_chore': 'tm1cm*', 'exclude_chore': '*1'}}
        chores = Chore(config)

        lst = chores.list(self.remote_app)

        self.assertEqual(lst, ['tm1cm.TestChore2'])

        self._cleanup_remote()

    def test_get_local(self):
        chores = Chore(self.config)

        lst = chores.list(self.local_app)
        lst = chores.get(self.local_app, lst)

        self.assertEqual(lst, [
            ('tm1cm.TestChore1', {'DSTSensitive': False, 'ExecutionMode': 'SingleCommit', 'Frequency': 'P100DT00H00M00S', 'StartTime': '2022-02-13T20:00Z', 'Tasks': [
                {'Parameters': [{'Name': 'pCube', 'Value': ''}, {'Name': 'pFile', 'Value': ''}, {'Name': 'pPath', 'Value': ''}, {'Name': 'pUseActiveSandbox', 'Value': ''}, {'Name': 'pView', 'Value': ''}],
                 'Process': {'Name': 'tm1cm.Core.Data.Generic View Export'}, 'Step': 0}], 'Name': 'tm1cm.TestChore1'}),
            ('tm1cm.TestChore2',
             {'DSTSensitive': False, 'ExecutionMode': 'SingleCommit', 'Frequency': 'P55DT00H00M00S', 'StartTime': '2022-02-13T20:00Z',
              'Tasks': [{'Parameters': [{'Name': 'pCube', 'Value': ''}, {'Name': 'pFile', 'Value': ''}, {'Name': 'pPath', 'Value': ''},
                                        {'Name': 'pUseActiveSandbox', 'Value': ''}, {'Name': 'pView', 'Value': ''}],
                         'Process': {'Name': 'tm1cm.Core.Data.Generic View Export'}, 'Step': 0}], 'Name': 'tm1cm.TestChore2'})]
                         )

    def test_get_remote(self):
        chores = Chore(self.config)

        lst = chores.list(self.remote_app)
        lst = chores.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        chores = Chore(self.config)

        lst = (chores.list(self.local_app))

        self.assertEqual(lst, ['tm1cm.TestChore1', 'tm1cm.TestChore2'])

    def test_list_remote(self):
        chores = Chore(self.config)

        lst = chores.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        chores = Chore(self.config)

        original = chores.list(self.local_app)
        original = chores.get(self.local_app, original)

        for name, item in original:
            chores.update(self.temp_app, name, item)

        modified = chores.list(self.temp_app)
        modified = chores.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()
        self._cleanup_remote()

    def _setup_remote(self):
        config = {**self.config, **{'include_chore': 'tm1cm*', 'exclude_chore': '', 'include_process': 'tm1cm*', 'exclude_process': ''}}
        processes = Process(config)

        lst = processes.list(self.local_app)
        lst = processes.get(self.local_app, lst)

        for name, item in lst:
            processes.update(self.remote_app, name, item)

        chores = Chore(config)

        lst = chores.list(self.local_app)
        lst = chores.get(self.local_app, lst)

        for name, item in lst:
            chores.update(self.remote_app, name, item)

    def _cleanup_remote(self):
        config = {**self.config, **{'include_chore': 'tm1cm*', 'exclude_chore': ''}}
        chores = Chore(config)

        lst = chores.list(self.remote_app)
        lst = chores.get(self.remote_app, lst)

        for name, item in lst:
            chores.delete(self.remote_app, name, item)


if __name__ == '__main__':
    unittest.main()
