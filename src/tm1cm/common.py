import logging
import os
from fnmatch import fnmatch
from urllib.parse import quote

import yaml


def _read(config_path):
    """A config file's text: UTF-8, or else the system's encoding, which 1.0 read them in (a
    Windows editor's ANSI)."""
    import locale

    from tm1cm.errors import ConfigError

    try:
        with open(config_path, encoding='utf-8') as fp:
            return fp.read()
    except UnicodeDecodeError:
        encoding = locale.getpreferredencoding(False)
    try:
        with open(config_path, encoding=encoding) as fp:
            return fp.read()
    except (UnicodeDecodeError, LookupError) as e:
        raise ConfigError(f'{config_path} is neither UTF-8 nor {encoding} text.', 'Save it as UTF-8.') from e


def _load(config_path):
    from tm1cm.errors import ConfigError

    try:
        config = yaml.safe_load(_read(config_path))
    except yaml.YAMLError as e:
        raise ConfigError(f'{config_path} is not valid YAML: {e}') from e
    if config is None:
        return {}
    if not isinstance(config, dict):
        raise ConfigError(f'{config_path} should hold settings (name: value), and holds a {type(config).__name__}.')
    return config


def get_config(path, config_name, environment=None):
    logger = logging.getLogger(__name__)
    config_path = os.path.join(path, 'config', 'default', config_name + '.yaml')
    logger.debug('Attempting to open file: {}'.format(config_path))
    if os.path.isfile(config_path):
        config1 = _load(config_path)
    else:
        config1 = get_default_config(config_name)

    if environment:
        config_path = os.path.join(path, 'config', environment, config_name + '.yaml')
        if os.path.isfile(config_path):
            return {**config1, **_load(config_path)}

    return config1


def odata_key(name):
    """name as a quoted OData key or string literal's content, ready for a request URL.

    OData escapes ' inside a quoted literal by doubling it; the result is then percent-encoded,
    so characters that mean something in a URL (#, %, &, ?, spaces) reach TM1 as part of the name.
    """
    return quote(name.replace("'", "''"), safe='')


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
