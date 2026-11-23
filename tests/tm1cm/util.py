import os
import shutil
import tempfile

import yaml


def get_tm1cm_config():
    path = os.path.split(__file__)[0]
    path = os.path.join(path, '../../src/tm1cm/include', 'tm1cm.yaml')
    path = os.path.abspath(path)
    with open(path, 'r') as f:
        config = yaml.safe_load(f)

    for key, val in config.items():
        if key.startswith('include_'):
            config[key] = 'tm1cm*'
        if key.startswith('exclude_'):
            config[key] = ''

    return config


def get_local_config():
    """A copy of the checked-in test application, in a temporary directory.

    LocalApplication runs `git init` in its path, so the tests must not point it at tests/
    itself, or they leave a nested repository inside this one.
    """
    path = os.path.split(__file__)[0]
    path = os.path.abspath(os.path.join(path, 'include/local'))
    return shutil.copytree(path, os.path.join(tempfile.mkdtemp(prefix='tm1cm_test_'), 'local'))
