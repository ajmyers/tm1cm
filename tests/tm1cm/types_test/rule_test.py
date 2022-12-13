import unittest

from tests.tm1cm.types_test import base


class RuleTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(RuleTest, self).__init__(*args, **kwargs)

        self.type = self.rules

        self.filter_config = {'exclude_rule': '*01'}
        self.filter_result = ['tm1cmTestCube01']

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.cubes)
        self._setup_remote_object(self.rules)

    def _cleanup_remote(self):
        self._cleanup_remote_object(self.cubes)


if __name__ == '__main__':
    unittest.main()
