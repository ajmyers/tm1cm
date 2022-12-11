import unittest

from tests.tm1cm.types import base


class ViewDataTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(ViewDataTest, self).__init__(*args, **kwargs)

        self.type = self.views_data

        self.filter_config = {'exclude_cube_view_data': '*View2'}
        self.filter_result = [('tm1cmTestCube01', 'tm1cmTestCube01_View2')]

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.subsets)
        self._setup_remote_object(self.cubes)
        self._setup_remote_object(self.views)
        self._setup_remote_object(self.views_data)


if __name__ == '__main__':
    unittest.main()
