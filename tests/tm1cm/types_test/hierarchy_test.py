import copy
import unittest

import pytest

from tests.tm1cm.types_test import base
from tm1cm.types.hierarchy import Hierarchy


class HierarchyTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(HierarchyTest, self).__init__(*args, **kwargs)

        self.type = self.hierarchies

        self.filter_config = {'exclude_dimension_hierarchy': '*Dim1'}
        self.filter_result = [('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1')]

    def _setup_remote(self):
        self._setup_remote_object(self.dimensions)
        self._setup_remote_object(self.hierarchies)

    @pytest.mark.requires_tm1
    def test_update_with_elements_excluded_keeps_edges(self):
        """Adding an attribute to a hierarchy whose elements are excluded leaves its edges alone.

        Migrating a hierarchy reads it from the source through the filters, then updates the
        target with what it read. With elements excluded, the source hierarchy has no edges, and
        the update used to write that empty list over the target's edges, flattening it.
        """
        name = ('tm1cmTestCube01_Dim1', 'tm1cmTestCube01_Dim1')
        self._setup_remote()

        before = dict(self.hierarchies.get([name], self.remote_app))[name]
        self.assertTrue(before['Edges'])

        # As a migration does: read the source through the filters into the stage's files, change
        # it there, then read it back from the files and update the target with it
        filtered = Hierarchy({**self.config, 'exclude_dimension_hierarchy_element': '*/*'})
        source = copy.deepcopy(dict(filtered.get([name], self.remote_app))[name])
        source['ElementAttributes'].append({'Name': 'Added', 'Type': 'String'})
        filtered.update(name, source, self.temp_app)
        staged = dict(filtered.get([name], self.temp_app))[name]

        filtered.update(name, staged, self.remote_app)

        after = dict(self.hierarchies.get([name], self.remote_app))[name]
        self.assertEqual(sorted(before['Edges'], key=str), sorted(after['Edges'], key=str))
        self.assertEqual(sorted(e['Name'] for e in before['Elements']), sorted(e['Name'] for e in after['Elements']))
        self.assertIn('Added', [attribute['Name'] for attribute in after['ElementAttributes']])


if __name__ == '__main__':
    unittest.main()
