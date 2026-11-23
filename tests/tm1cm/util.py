import os
import shutil
import tempfile

import yaml

from tm1cm.application import LocalApplication


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


def convert_local(path, config):
    """A copy of the local application at path, rewritten in config's text_output_format.

    The checked-in test application is YAML; reading it as YAML and writing it with config's types
    gives the same objects in JSON.
    """
    source = LocalApplication({**config, 'text_output_format': 'YAML'}, path)
    target = LocalApplication(config, os.path.join(tempfile.mkdtemp(prefix='tm1cm_test_'), 'local'))
    for source_scope, target_scope in zip(source.scopes, target.scopes):
        for name, item in source_scope.get(source_scope.list(source), source):
            target_scope.update(name, item, target)
    return target.path
