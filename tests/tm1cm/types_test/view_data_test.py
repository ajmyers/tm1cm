import unittest

import pytest

from tests.tm1cm import tm1_objects
from tests.tm1cm.types_test import base
from skipcheck_tm1.errors import Tm1ApiError

CUBE = 'tm1cmTestCube01'


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

    @pytest.mark.requires_tm1
    def test_get_locked_cube(self):
        """A locked cube's view data reads in full, and the cube is locked again afterwards.

        While a cube is locked, TM1 flags every cell as not updateable, the same flag that marks
        rule-derived cells, which reading skips.
        """
        self._setup_remote()
        name = (CUBE, 'tm1cmTestCube01_View1')
        expected = dict(self.views_data.get([name], self.remote_app))[name]

        cubes = self.remote_app.session.client.cubes
        cubes.lock(CUBE)
        try:
            got = dict(self.views_data.get([name], self.remote_app)).get(name)
            self.assertEqual(got, expected)
            self._assert_locked()
        finally:
            cubes.unlock(CUBE)

    def _assert_locked(self):
        # TM1's REST API has no lock property: still locked if a write is refused
        with self.assertRaises(Tm1ApiError):
            tm1_objects.write_value(self.remote_app.session, CUBE, ['tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim2'], ['Test Element 2', 'Test Element 2'], 1)

    @pytest.mark.requires_tm1
    def test_update_locked_cube(self):
        """View data is written into a locked cube, and the cube is locked again afterwards."""
        # The cube and its views, without their data, so the update has cells to write
        for object_type in [self.dimensions, self.hierarchies, self.subsets, self.cubes, self.views]:
            self._setup_remote_object(object_type)
        name = (CUBE, 'tm1cmTestCube01_View1')
        item = dict(self.views_data.get([name], self.local_app))[name]

        cubes = self.remote_app.session.client.cubes
        cubes.lock(CUBE)
        try:
            self.views_data.update(name, item, self.remote_app)

            written = dict(self.views_data.get([name], self.remote_app))[name]
            self.assertEqual(sorted(map(tuple, written)), sorted(map(tuple, item)))
            self._assert_locked()
        finally:
            cubes.unlock(CUBE)


class ViewDataJsonTest(ViewDataTest):
    """The same tests, with objects stored as JSON instead of YAML."""
    output_format = 'JSON'


if __name__ == '__main__':
    unittest.main()
