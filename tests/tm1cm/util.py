
import os
import yaml


def get_tm1cm_config():
    with open('../../../src/tm1cm/include/tm1cm.yaml', 'r') as f:
        return yaml.safe_load(f)


def get_local_config():
    path = os.path.split(__file__)[0]
    path = os.path.abspath(os.path.join(path, 'include/local'))

    return path


def get_remote_config():
    # TODO: Look at this
    with open('/Users/andrewmyers/afcostrep/config/dev/connect.yaml', 'r') as fp:
        connect = yaml.safe_load(fp)

    with open('/Users/andrewmyers/afcostrep/config/dev/credentials.yaml', 'r') as fp:
        credentials = yaml.safe_load(fp)

    return {**connect, **credentials}