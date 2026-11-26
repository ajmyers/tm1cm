import unittest

import pytest

from tests.tm1cm.types_test import base


class ChoreTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(ChoreTest, self).__init__(*args, **kwargs)

        self.type = self.chores

        self.filter_config = {'exclude_chore': '*1'}
        self.filter_result = [('tm1cm.TestChore1')]

    def _setup_remote(self):
        self._setup_remote_object(self.processes)
        self._setup_remote_object(self.chores)

    @pytest.mark.requires_tm1
    def test_create_active_dst_sensitive(self):
        """An active chore whose start time follows daylight saving time is created, and active.

        TM1 refuses SetServerLocalStartTime while a chore is active, so it's created inactive,
        its start time set, then activated."""
        self._setup_remote_object(self.processes)
        name = 'tm1cm.TestChoreDST'
        item = dict(self.chores.get(['tm1cm.TestChore1'], self.local_app))['tm1cm.TestChore1']
        item = {**item, 'Name': name, 'DSTSensitive': True, 'Active': True}

        self.chores.update(name, item, self.remote_app)

        got = dict(self.chores.get([name], self.remote_app))[name]
        self.assertTrue(got['Active'])
        self.assertTrue(got['DSTSensitive'])
        self.assertEqual(got['StartTime'], item['StartTime'])


class ChoreJsonTest(ChoreTest):
    """The same tests, with objects stored as JSON instead of YAML."""
    output_format = 'JSON'


if __name__ == '__main__':
    unittest.main()
