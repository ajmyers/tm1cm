import unittest

from tm1cm.__main__ import main


class TestMain(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestMain, self).__init__(*args, **kwargs)

    def test_get(self):
        main('get', '/Users/andrewmyers/afcostrep', 'dev')
