import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Process import Process


class ProcessTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(ProcessTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

    def test_filter_local(self):
        config = {**self.config, **{'include_process': '*', 'exclude_process': '*Import'}}
        processes = Process(config)

        original = processes.list(self.local_app)
        original = processes.filter(self.local_app, original)

        self.assertEqual(original, ['tm1cm.Core.Data.Generic View Export'])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_process': 'tm1cm*', 'exclude_process': '*Import'}}
        processes = Process(config)

        lst = processes.list(self.remote_app)

        self.assertEqual(lst, ['tm1cm.Core.Data.Generic View Export'])

        self._cleanup_remote()

    def test_get_local(self):
        processes = Process(self.config)

        lst = processes.list(self.local_app)
        lst = processes.get(self.local_app, lst)

        self.assertTrue(len(lst) == 2)

    def test_get_remote(self):
        processes = Process(self.config)

        lst = processes.list(self.remote_app)
        lst = processes.get(self.remote_app, [lst[0]])

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        processes = Process(self.config)

        lst = (processes.list(self.local_app))

        self.assertEqual(lst, ['tm1cm.Core.Data.Generic View Export', 'tm1cm.Core.Data.Generic View Import'])

    def test_list_remote(self):
        processes = Process(self.config)

        lst = processes.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        processes = Process(self.config)

        original = processes.list(self.local_app)
        original = processes.get(self.local_app, original)

        self.maxDiff = None
        for name, item in original:
            processes.update(self.temp_app, name, item)

        modified = processes.list(self.temp_app)
        modified = processes.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_process': 'tm1cm*', 'exclude_process': ''}}
        processes = Process(config)

        original = processes.list(self.local_app)
        original = processes.get(self.local_app, original)

        modified = processes.list(self.remote_app)
        modified = processes.get(self.remote_app, modified)

        for name, item in modified:
            processes.update(self.temp_app, name, item)

        self.assertEqual(original, modified)

        self._cleanup_remote()

    def _setup_remote(self):
        config = {**self.config, **{'include_process': 'tm1cm*', 'exclude_process': ''}}
        processes = Process(config)

        lst = processes.list(self.local_app)
        lst = processes.get(self.local_app, lst)

        for name, item in lst:
            processes.update(self.remote_app, name, item)

    def _cleanup_remote(self):
        config = {**self.config, **{'include_process': 'tm1cm*', 'exclude_process': ''}}
        processes = Process(config)

        lst = processes.list(self.local_app)
        lst = processes.get(self.local_app, lst)

        for name, item in lst:
            self.remote_app.session.processes.delete(name)


if __name__ == '__main__':
    unittest.main()
