import logging
import os
from fnmatch import fnmatch

import yaml


def get_config(path, config_name, environment=None):
    logger = logging.getLogger(__name__)
    config_path = os.path.join(path, 'config', 'default', config_name + '.yaml')
    logger.debug('Attempting to open file: {}'.format(config_path))
    try:
        config1 = yaml.safe_load(open(config_path))
    except FileNotFoundError:
        config1 = get_default_config(config_name)
    except Exception:
        raise

    if environment:
        config_path = os.path.join(path, 'config', environment, config_name + '.yaml')
        if os.path.isfile(config_path):
            try:
                config2 = yaml.safe_load(open(config_path))
            except FileNotFoundError:
                config2 = {}
            except Exception:
                raise

            return {**config1, **config2}

    return config1


def get_default_config(config_name):
    include_path = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'include')
    path = os.path.join(include_path, config_name + '.yaml')
    with open(path) as fp:
        return yaml.safe_load(fp)


def filter_list(lst, include, exclude, name_func=None, filter_func=None, extra={}):
    if not name_func:
        def name_func(obj, extra={}):
            return str(obj)

    if not filter_func:
        def filter_func(obj, pattern, extra={}):
            result = fnmatch(name_func(obj, extra), pattern)
            return result

    if not isinstance(include, list):
        include = [include]
    if not isinstance(exclude, list):
        exclude = [exclude]

    if isinstance(lst, dict):
        iterator = lst.items()
    else:
        iterator = lst

    include_list = []
    for obj in iterator:
        obj_name = name_func(obj, extra)
        for pattern in include:
            if filter_func(obj, pattern, extra):
                include_list.append(obj_name)
                break

    exclude_list = []
    for obj in iterator:
        obj_name = name_func(obj, extra)
        for pattern in exclude:
            if filter_func(obj, pattern, extra):
                exclude_list.append(obj_name)
                break

    name_list = set(include_list) - set(exclude_list)

    if isinstance(lst, dict):
        return {key: val for key, val in lst.items() if name_func((key, val), extra) in name_list}
    else:
        return [obj for obj in iterator if name_func(obj, extra) in name_list]


class Dumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(Dumper, self).increase_indent(flow, False)
