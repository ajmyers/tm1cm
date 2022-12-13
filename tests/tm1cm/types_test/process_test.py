import unittest

from tests.tm1cm.types_test import base


class ProcessTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(ProcessTest, self).__init__(*args, **kwargs)

        self.type = self.processes

        self.filter_config = {'exclude_process': '*Import'}
        self.filter_result = [('tm1cm.Core.Data.Generic View Import')]

    def _setup_remote(self):
        self._setup_remote_object(self.processes)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.processes)


if __name__ == '__main__':
    unittest.main()
