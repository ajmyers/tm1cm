import os

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
    path = os.path.split(__file__)[0]
    path = os.path.abspath(os.path.join(path, 'include/local'))
    return path


def get_remote_config():
    # TODO: Look at this
    with open('/Users/andrewmyers/afcostrep/config/pg/connect.yaml', 'r') as fp:
        connect = yaml.safe_load(fp)

    with open('/Users/andrewmyers/afcostrep/config/pg/credentials.yaml', 'r') as fp:
        credentials = yaml.safe_load(fp)

    return {**connect, **credentials}
