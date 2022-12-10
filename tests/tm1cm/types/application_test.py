import unittest

from tests.tm1cm.types import base
from tm1cm.types.application import Application


class ApplicationTest(base.Base):

    def __init__(self, *args, **kwargs):
        super(ApplicationTest, self).__init__(*args, **kwargs)

    def test_filter_local(self):
        config = {**self.config, **{'exclude_application': '*Binary*'}}
        applications = Application(config)

        original = applications.list(self.local_app)
        original = applications.filter(self.local_app, original)

        self.assertEqual(original, [('tm1cmTest', 'DimensionReferenceTest', 'dimension'), ('tm1cmTest', 'LinkTest', 'extr'), ('tm1cmTest', 'ProcessReferenceTest', 'process'), ('tm1cmTest', 'SubsetReferenceTest', 'subset'),
                                    ('tm1cmTest', 'ViewReferenceTest', 'view'), ('tm1cmTest', 'subfolder', 'ChoreReferenceTest', 'chore'), ('tm1cmTest', 'subfolder', 'CubeReferenceTest', 'cube')])

    def test_filter_remote(self):
        self._setup_remote()

        config = {**self.config, **{'exclude_application': '*Binary*'}}
        applications = Application(config)

        lst = applications.list(self.remote_app)

        self.assertEqual(lst, [('tm1cmTest', 'DimensionReferenceTest', 'dimension'), ('tm1cmTest', 'LinkTest', 'extr'), ('tm1cmTest', 'ProcessReferenceTest', 'process'), ('tm1cmTest', 'SubsetReferenceTest', 'subset'),
                               ('tm1cmTest', 'ViewReferenceTest', 'view'), ('tm1cmTest', 'subfolder', 'ChoreReferenceTest', 'chore'), ('tm1cmTest', 'subfolder', 'CubeReferenceTest', 'cube')])

    def test_get_local(self):
        config = {**self.config, **{'exclude_application': '*Binary*'}}

        applications = Application(config)

        lst = applications.list(self.local_app)
        lst = applications.get(self.local_app, lst)

        self.assertEqual(lst, [
            (('tm1cmTest', 'DimensionReferenceTest', 'dimension'), {'Name': 'tm1cmTest\\DimensionReferenceTest.dimension', 'Dimension@odata.bind': "Dimensions('tm1cmTestCube01_Dim1')", '@odata.type': 'tm1.DimensionReference'}),
            (('tm1cmTest', 'LinkTest', 'extr'), {'URL': 'http://googles.com', 'Name': 'tm1cmTest\\LinkTest.extr', '@odata.type': '#ibm.tm1.api.v1.Link'}),
            (('tm1cmTest', 'ProcessReferenceTest', 'process'), {'Name': 'tm1cmTest\\ProcessReferenceTest.process', 'Process@odata.bind': "Processes('Actual.Call.Load Actual Data')", '@odata.type': 'tm1.ProcessReference'}), (
                ('tm1cmTest', 'SubsetReferenceTest', 'subset'),
                {'Name': 'tm1cmTest\\SubsetReferenceTest.subset', 'Subset@odata.bind': "Dimensions('tm1cmTestCube01_Dim1')/Hierarchies('tm1cmTestCube01_Dim1')/Subsets('tm1cmTestSubset')", '@odata.type': 'tm1.SubsetReference'}),
            (('tm1cmTest', 'ViewReferenceTest', 'view'), {'Name': 'tm1cmTest\\ViewReferenceTest.view', 'View@odata.bind': "Cubes('tm1cmTestCube01')/Views('tm1cmTestCube01_View1')", '@odata.type': 'tm1.ViewReference'}),
            (('tm1cmTest', 'subfolder', 'ChoreReferenceTest', 'chore'), {'Name': 'tm1cmTest\\subfolder\\ChoreReferenceTest.chore', 'Chore@odata.bind': "Chores('Admin.Refresh Security')", '@odata.type': 'tm1.ChoreReference'}),
            (('tm1cmTest', 'subfolder', 'CubeReferenceTest', 'cube'), {'Name': 'tm1cmTest\\subfolder\\CubeReferenceTest.cube', 'Cube@odata.bind': "Cubes('tm1cmTestCube01')", '@odata.type': 'tm1.CubeReference'})])

    def test_get_remote(self):
        self._setup_remote()

        applications = Application(self.config)

        lst = applications.list(self.remote_app)
        lst = applications.get(self.remote_app, [lst[1]])

        self.assertTrue(len(lst) > 0)

    def test_list_local(self):
        applications = Application(self.config)

        lst = applications.list(self.local_app)

        self.assertEqual(lst, [('tm1cmTest', 'DimensionReferenceTest', 'dimension'), ('tm1cmTest', 'LinkTest', 'extr'), ('tm1cmTest', 'ProcessReferenceTest', 'process'), ('tm1cmTest', 'SubsetReferenceTest', 'subset'),
                               ('tm1cmTest', 'ViewReferenceTest', 'view'), ('tm1cmTest', 'subfolder', 'ChoreReferenceTest', 'chore'), ('tm1cmTest', 'subfolder', 'CubeReferenceTest', 'cube'),
                               ('tm1cmTest', 'subfolder', 'subfolder2', 'BinaryReferenceTest.xlsx', 'blob')])

    def test_list_remote(self):
        self._setup_remote()

        applications = Application(self.config)

        lst = applications.list(self.remote_app)

        self.assertTrue(len(lst) > 0)

    def test_update_local(self):
        applications = Application(self.config)

        original = applications.list(self.remote_app)
        original = applications.get(self.remote_app, original[:10])

        for name, item in original:
            applications.update(self.temp_app, name, item)

        modified = applications.list(self.temp_app)
        modified = applications.get(self.temp_app, modified)

        self.assertEqual(original, modified)

    def test_update_remote(self):
        self._setup_remote()

    def _setup_remote(self):
        self._setup_remote_object(self.processes)
        self._setup_remote_object(self.chores)
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)
        self._setup_remote_object(self.subsets)
        self._setup_remote_object(self.cubes)
        self._setup_remote_object(self.views)
        self._setup_remote_object(self.applications)


if __name__ == '__main__':
    unittest.main()
