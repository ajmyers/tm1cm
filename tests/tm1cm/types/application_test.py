import unittest

from tests.tm1cm.types import base


class ApplicationTest(base.Wrapper.Base):

    def __init__(self, *args, **kwargs):
        super(ApplicationTest, self).__init__(*args, **kwargs)

        self.type = self.applications

        self.filter_config = {'exclude_application': '*Binary*'}
        self.filter_result = [('tm1cmTest', 'subfolder', 'subfolder2', 'BinaryReferenceTest.xlsx', 'blob')]

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
