import unittest

from tests.tm1cm.types_test import base


class CubeTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(CubeTest, self).__init__(*args, **kwargs)

        self.type = self.cubes

        self.filter_config = {'exclude_cube': '*01'}
        self.filter_result = [('tm1cmTestCube01')]

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.cubes)


if __name__ == '__main__':
    unittest.main()
