import unittest

from tests.tm1cm.types_test import base


class ViewTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(ViewTest, self).__init__(*args, **kwargs)

        self.type = self.views

        self.filter_config = {'exclude_cube_view': '*View2'}
        self.filter_result = [('tm1cmTestCube01', 'tm1cmTestCube01_View2')]

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.subsets)
        self._setup_remote_object(self.cubes)
        self._setup_remote_object(self.views)


if __name__ == '__main__':
    unittest.main()
