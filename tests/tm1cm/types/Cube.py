import tempfile

from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.types.Cube import Cube
from tests.tm1cm import util

import copy
import unittest
import yaml
import os


class CubeTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(CubeTest, self).__init__(*args, **kwargs)

        self.config = util.get_tm1cm_config()

        self.path = util.get_local_config()

        self.remote = util.get_remote_config()

        self.local_app = LocalApplication(self.config, self.path)
        self.remote_app = RemoteApplication(self.config, None, self.remote)
        self.temp_app = LocalApplication(self.config, tempfile.mkdtemp())

    def test_filter_local(self):
        config = {**self.config, **{'include_cube': '*', 'exclude_cube': '*01'}}
        cubes = Cube(config)

        self.assertEqual(cubes.filter(self.local_app, cubes.list(self.local_app)), ['tm1cmTestCube02', 'tm1cmTestCube03', 'tm1cmTestCube04'])

    def test_filter_remote(self):
        self._setup_remote()

        config2 = {**self.config, **{'include_cube': 'tm1cm*', 'exclude_cube': '*01'}}
        cubes = Cube(config2)

        cube_list = cubes.list(self.remote_app)

        self.assertEqual(cube_list, ['tm1cmTestCube02', 'tm1cmTestCube03', 'tm1cmTestCube04'])

        self._cleanup_remote()

    def test_get_local(self):
        cubes = Cube(self.config)

        cubes_list = cubes.get(self.local_app, cubes.list(self.local_app))

        self.assertEqual(cubes_list, [{'Dimensions': [{'Name': 'tm1cmTestCube01_Dim1'}, {'Name': 'tm1cmTestCube01_Dim2'}], 'Name': 'tm1cmTestCube01'}, {'Dimensions': [{'Name': 'tm1cmTestCube02_Dim01'}, {'Name': 'tm1cmTestCube02_Dim02'}, {'Name': 'tm1cmTestCube02_Dim03'}], 'Name': 'tm1cmTestCube02'}, {'Dimensions': [{'Name': 'tm1cmTestCube03_Dim01'}, {'Name': 'tm1cmTestCube03_Dim02'}], 'Name': 'tm1cmTestCube03'}, {'Dimensions': [{'Name': 'tm1cmTestCube04_Dim01'}, {'Name': 'tm1cmTestCube04_Dim02'}, {'Name': 'tm1cmTestCube04_Dim03'}, {'Name': 'tm1cmTestCube04_Dim04'}, {'Name': 'tm1cmTestCube04_Dim05'}], 'Name': 'tm1cmTestCube04'}])

    def test_get_remote(self):
        cubes = Cube(self.config)

        cube_list = cubes.list(self.remote_app)
        cube_list = cubes.get(self.remote_app, [cube_list[0]])

        self.assertTrue(len(cube_list) > 0)

    def test_list_local(self):
        cubes = Cube(self.config)

        self.assertEqual(cubes.list(self.local_app), ['tm1cmTestCube01', 'tm1cmTestCube02', 'tm1cmTestCube03', 'tm1cmTestCube04'])

    def test_list_remote(self):
        cubes = Cube(self.config)

        cube_list = cubes.list(self.remote_app)

        self.assertTrue(len(cube_list) > 0)

    def test_transform_local(self):
        cubes = Cube(self.config)

        items = cubes.list(self.local_app)
        items = cubes._get_local(self.local_app, items)

        original = copy.deepcopy(items)

        modified = copy.deepcopy(items)
        modified = [cubes._transform_to_local(item) for item in modified]
        modified = [cubes._transform_from_local(item) for item in modified]

        self.assertEqual(original, modified)

    def test_update_local(self):
        cubes = Cube(self.config)

        original = cubes.list(self.local_app)
        original = cubes.get(self.local_app, original)

        for item in original:
            cubes.update(self.temp_app, item)

        modified = cubes.list(self.temp_app)
        modified = cubes.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()
        self._cleanup_remote()

    def _setup_remote(self):
        config = {**self.config, **{'include_cube': 'tm1cm*', 'exclude_cube': ''}}
        cubes = Cube(config)

        cube_list = cubes.list(self.local_app)
        cube_list = cubes.get(self.local_app, cube_list)

        for cube in cube_list:
            cubes.update(self.remote_app, cube)

    def _cleanup_remote(self):
        config = {**self.config, **{'include_cube': 'tm1cm*', 'exclude_cube': ''}}
        cubes = Cube(config)

        cube_list = cubes.list(self.local_app)
        cube_list = cubes.get(self.local_app, cube_list)

        for cube in cube_list:
            self.remote_app.session.cubes.delete(cube['Name'])

        for cube in cube_list:
            for dimension in cube['Dimensions']:
                self.remote_app.session.dimensions.delete(dimension['Name'])


if __name__ == '__main__':
    unittest.main()
