import unittest

from tests.tm1cm.types import base
from tm1cm.types.rule import Rule


class RuleTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(RuleTest, self).__init__(*args, **kwargs)

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

    def test_get_local(self):
        rules = Rule(self.config)

        lst = rules.list(self.local_app)
        lst = rules.get(self.local_app, lst)

        self.assertEqual(lst, [('tm1cmTestCube01', 'SKIPCHECK;\n# This is a rule'), ('tm1cmTestCube02', 'SKIPCHECK;\n# This is a rule')])

    def test_get_remote(self):
        self._setup_remote()

        rules = Rule(self.config)

        lst = rules.list(self.remote_app)
        lst = rules.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        rules = Rule(self.config)

        self.assertEqual(rules.list(self.local_app), ['tm1cmTestCube01', 'tm1cmTestCube02'])

    def test_list_remote(self):
        self._setup_remote()

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

    def _setup_remote(self):
        self._setup_remote_object(self.cubes)
        self._setup_remote_object(self.rules)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.cubes)


if __name__ == '__main__':
    unittest.main()
