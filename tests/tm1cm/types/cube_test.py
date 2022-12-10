import copy
import unittest

from tests.tm1cm.types import base
from tm1cm.types.cube import Cube


class CubeTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(CubeTest, self).__init__(*args, **kwargs)

    def test_filter_local(self):
        config = {**self.config, **{'exclude_cube': '*01'}}
        cubes = Cube(config)

        lst = cubes.list(self.local_app)
        lst = cubes.filter(self.local_app, lst)

        self.assertEqual(lst, ['tm1cmTestCube02', 'tm1cmTestCube03', 'tm1cmTestCube04'])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'exclude_cube': '*01'}}
        cubes = Cube(config)

        lst = cubes.list(self.remote_app)
        self.assertEqual(lst, ['tm1cmTestCube02', 'tm1cmTestCube03', 'tm1cmTestCube04'])

    def test_get_local(self):
        cubes = Cube(self.config)

        lst = cubes.list(self.local_app)
        lst = cubes.get(self.local_app, lst)

        self.assertEqual(lst, [('tm1cmTestCube01', {'Dimensions': [{'Name': 'tm1cmTestCube01_Dim1'}, {'Name': 'tm1cmTestCube01_Dim2'}], 'Name': 'tm1cmTestCube01'}),
                               ('tm1cmTestCube02', {'Dimensions': [{'Name': 'tm1cmTestCube02_Dim01'}, {'Name': 'tm1cmTestCube02_Dim02'}, {'Name': 'tm1cmTestCube02_Dim03'}], 'Name': 'tm1cmTestCube02'}),
                               ('tm1cmTestCube03', {'Dimensions': [{'Name': 'tm1cmTestCube03_Dim01'}, {'Name': 'tm1cmTestCube03_Dim02'}], 'Name': 'tm1cmTestCube03'}),
                               ('tm1cmTestCube04',
                                {'Dimensions': [{'Name': 'tm1cmTestCube04_Dim01'}, {'Name': 'tm1cmTestCube04_Dim02'}, {'Name': 'tm1cmTestCube04_Dim03'}, {'Name': 'tm1cmTestCube04_Dim04'}, {'Name': 'tm1cmTestCube04_Dim05'}],
                                 'Name': 'tm1cmTestCube04'})])

    def test_get_remote(self):
        self._setup_remote()

        cubes = Cube(self.config)

        lst = cubes.list(self.remote_app)
        lst = cubes.get(self.remote_app, lst)

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        cubes = Cube(self.config)

        self.assertEqual(cubes.list(self.local_app), ['tm1cmTestCube01', 'tm1cmTestCube02', 'tm1cmTestCube03', 'tm1cmTestCube04'])

    def test_list_remote(self):
        self._setup_remote()
        cubes = Cube(self.config)

        cube_list = cubes.list(self.remote_app)

        self.assertTrue(len(cube_list) > 0)

    def test_transform_local(self):
        cubes = Cube(self.config)

        items = cubes.list(self.local_app)
        items = cubes._get_local(self.local_app, items)

        original = copy.deepcopy(items)

        modified = copy.deepcopy(items)

        modified = [(name, cubes._transform_to_local(name, item)) for name, item in modified]
        modified = [(name, cubes._transform_from_local(name, item)) for name, item in modified]

        self.assertEqual(original, modified)

    def test_update_local(self):
        cubes = Cube(self.config)

        original = cubes.list(self.local_app)
        original = cubes.get(self.local_app, original)

        for name, item in original:
            cubes.update(self.temp_app, name, item)

        modified = cubes.list(self.temp_app)
        modified = cubes.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.cubes)


if __name__ == '__main__':
    unittest.main()