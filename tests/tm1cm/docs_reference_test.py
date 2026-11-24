"""The docs site's reference is written from the code (docs-site/extract/reference.py): every
connection setting, argument, exit code and tm1cm.yaml setting needs its description there."""
import importlib.util
import os

PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'docs-site', 'extract', 'reference.py')


def extractor():
    spec = importlib.util.spec_from_file_location('docs_reference', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_everything_the_reference_shows_is_described():
    if not os.path.exists(PATH):
        # An installed package's tests: the docs site isn't there
        return
    reference, problems = extractor().build()

    assert problems == []
    assert {s['name'] for s in reference['settings']} >= {'base_url', 'user', 'password', 'namespace', 'cam_passport'}
    assert [c['code'] for c in reference['exit_codes']] == [0, 2, 3, 4, 5, 70, 130]
    assert any(a['flags'] == ['--connect', '-c'] for a in reference['command_line']['arguments'])
    assert {f['type'] for f in reference['files']} >= {'process', 'cube', 'subset', 'application'}
    assert any(s['title'] == 'Cubes' for s in reference['tm1cm_yaml'])
