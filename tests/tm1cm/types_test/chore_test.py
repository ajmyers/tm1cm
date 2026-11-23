import unittest

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


if __name__ == '__main__':
    unittest.main()
