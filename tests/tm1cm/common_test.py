import os

import pytest
import yaml

from tm1cm.common import filter_list
from tm1cm.common import get_config
from tm1cm.common import get_default_config


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as fp:
        yaml.safe_dump(data, fp)


def test_get_config_falls_back_to_packaged_default(tmp_path):
    assert get_config(str(tmp_path), 'tm1cm') == get_default_config('tm1cm')


def test_get_config_reads_project_default(tmp_path):
    _write(str(tmp_path / 'config' / 'default' / 'connect.yaml'), {'base_url': 'http://default'})

    assert get_config(str(tmp_path), 'connect') == {'base_url': 'http://default'}


def test_get_config_environment_overrides_default(tmp_path):
    _write(str(tmp_path / 'config' / 'default' / 'connect.yaml'), {'base_url': 'http://default', 'verify': False})
    _write(str(tmp_path / 'config' / 'prod' / 'connect.yaml'), {'base_url': 'http://prod'})

    assert get_config(str(tmp_path), 'connect', 'prod') == {'base_url': 'http://prod', 'verify': False}


def test_get_config_missing_environment_uses_default(tmp_path):
    _write(str(tmp_path / 'config' / 'default' / 'connect.yaml'), {'base_url': 'http://default'})

    assert get_config(str(tmp_path), 'connect', 'staging') == {'base_url': 'http://default'}


NAMES = ['Sales', 'Sales Detail', 'Costs', '}ClientGroups']


@pytest.mark.parametrize('include, exclude, expected', [
    ('*', '', NAMES),
    ('Sales*', '', ['Sales', 'Sales Detail']),
    ('*', '}*', ['Sales', 'Sales Detail', 'Costs']),
    (['Sales', 'Costs'], '', ['Sales', 'Costs']),
    ('*', ['}*', '*Detail'], ['Sales', 'Costs']),
    ('', '', []),
    ('Sales*', 'Sales*', []),
])
def test_filter_list(include, exclude, expected):
    assert filter_list(NAMES, include, exclude) == expected


def test_filter_list_keeps_input_order():
    assert filter_list(['b', 'a', 'c'], '*', '') == ['b', 'a', 'c']


def test_filter_list_tuples_with_name_func():
    items = [('Cube1', 'View1'), ('Cube1', 'View2'), ('Cube2', 'View1')]

    result = filter_list(items, 'Cube1/*', '*/View2', name_func=lambda item, extra: '/'.join(item))

    assert result == [('Cube1', 'View1')]


def test_filter_list_dict():
    result = filter_list({'a': 1, 'b': 2}, 'a', '', name_func=lambda item, extra: item if isinstance(item, str) else item[0])

    assert result == {'a': 1}
