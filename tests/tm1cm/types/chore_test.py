import unittest

from tests.tm1cm.types import base
from tm1cm.types.chore import Chore


class ChoreTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(ChoreTest, self).__init__(*args, **kwargs)

    def test_filter_local(self):
        config = {**self.config, **{'exclude_chore': '*1'}}
        chores = Chore(config)

        original = chores.list(self.local_app)
        original = chores.filter(self.local_app, original)

        self.assertEqual(original, ['tm1cm.TestChore2'])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'exclude_chore': '*1'}}
        chores = Chore(config)

        lst = chores.list(self.remote_app)

        self.assertEqual(lst, ['tm1cm.TestChore2'])

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
        self._setup_remote()

        chores = Chore(self.config)

        lst = chores.list(self.remote_app)
        lst = chores.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        chores = Chore(self.config)

        lst = (chores.list(self.local_app))

        self.assertEqual(lst, ['tm1cm.TestChore1', 'tm1cm.TestChore2'])

    def test_list_remote(self):
        self._setup_remote()

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

    def _setup_remote(self):
        self._setup_remote_object(self.processes)
        self._setup_remote_object(self.chores)


if __name__ == '__main__':
    unittest.main()
