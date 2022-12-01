import tempfile
import unittest

from tests.tm1cm import util
from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Cube import Cube
from tm1cm.types.Rule import Rule


class RuleTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(RuleTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

    def test_filter_local(self):
        config = {**self.config, **{'include_rule': '*', 'exclude_rule': '*01'}}
        rules = Rule(config)

        self.assertEqual(rules.filter(self.local_app, rules.list(self.local_app)), ['tm1cmTestCube02'])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_cube': 'tm1cm*', 'exclude_cube': '*01', 'include_rule': 'tm1cm*', 'exclude_rule': '*01'}}
        rules = Rule(config)

        lst = rules.list(self.remote_app)

        self.assertEqual(lst, ['tm1cmTestCube02'])

        self._cleanup_remote()

    def test_get_local(self):
        rules = Rule(self.config)

        lst = rules.list(self.local_app)
        lst = rules.get(self.local_app, lst)

        self.assertEqual(lst, [('tm1cmTestCube01', 'SKIPCHECK;\n# This is a rule'), ('tm1cmTestCube02', 'SKIPCHECK;\n# This is a rule')])

    def test_get_remote(self):
        rules = Rule(self.config)

        lst = rules.list(self.remote_app)
        lst = rules.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        rules = Rule(self.config)

        self.assertEqual(rules.list(self.local_app), ['tm1cmTestCube01', 'tm1cmTestCube02'])

    def test_list_remote(self):
        rules = Rule(self.config)

        rule_list = rules.list(self.remote_app)

        self.assertTrue(len(rule_list) > 0)

    def test_update_local(self):
        rules = Rule(self.config)

        original = rules.list(self.local_app)
        original = rules.get(self.local_app, original)

        for name, item in original:
            rules.update(self.temp_app, name, item)

        modified = rules.list(self.temp_app)
        modified = rules.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()

        config = {**self.config, **{'include_cube': 'tm1cm*', 'exclude_cube': '', 'include_rule': 'tm1cm*', 'exclude_rule': ''}}
        rules = Rule(config)

        lst = rules.list(self.remote_app)
        lst = rules.get(self.remote_app, lst)

        self.assertEqual(lst, [('tm1cmTestCube01', 'SKIPCHECK;\n# This is a rule'), ('tm1cmTestCube02', 'SKIPCHECK;\n# This is a rule')])

        self._cleanup_remote()

    def _setup_remote(self):
        config = {**self.config, **{'include_cube': 'tm1cm*', 'exclude_cube': '', 'include_rule': 'tm1cm*', 'exclude_rule': ''}}
        cubes = Cube(config)

        lst = cubes.list(self.local_app)
        lst = cubes.get(self.local_app, lst)

        for name, item in lst:
            cubes.update(self.remote_app, name, item)

        rules = Rule(config)

        lst = rules.list(self.local_app)
        lst = rules.get(self.local_app, lst)

        for name, item in lst:
            rules.update(self.remote_app, name, item)

    def _cleanup_remote(self):
        config = {**self.config, **{'include_cube': 'tm1cm*', 'exclude_cube': ''}}
        cubes = Cube(config)

        lst = cubes.list(self.local_app)
        lst = cubes.get(self.local_app, lst)

        for name, _ in lst:
            self.remote_app.session.cubes.delete(name)

        for _, item in lst:
            for dimension in item['Dimensions']:
                self.remote_app.session.dimensions.delete(dimension['Name'])


if __name__ == '__main__':
    unittest.main()
