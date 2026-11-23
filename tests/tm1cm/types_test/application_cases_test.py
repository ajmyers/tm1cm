"""Applications beyond the checked-in test data: spreadsheets without an extension, deletes, folders
and references named with characters that need encoding, and missing applications."""
import copy
import os
import tempfile

import pytest

from tests.tm1cm import tm1_objects
from tests.tm1cm import util
from tm1cm import tm1 as tm1_client
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication

XLSX_PATH = ('data', 'application', 'tm1cmTest', 'subfolder', 'subfolder2', 'BinaryReferenceTest.xlsx')


def _document(name):
    with open(os.path.join(util.get_local_config(), *XLSX_PATH), 'rb') as fp:
        return {'@odata.type': '#ibm.tm1.api.v1.Document', 'Name': name, 'Content': fp.read()}


@pytest.fixture
def remote(tm1_connection):
    app = RemoteApplication(util.get_tm1cm_config(), None, tm1_connection)
    _clean(app)
    yield app
    _clean(app)


def _clean(app):
    for name in app.applications.list(app):
        app.applications.delete(name, app)
    for folder in ['tm1cmApp', 'tm1cm #Folder 50%', 'tm1cmRef']:
        if app.applications._exists(app, '', 'FOLDER', folder):
            tm1_client.delete_application(app.session, '', 'FOLDER', folder)
    tm1_objects.delete_process(app.session, 'tm1cmApp Proc#1')


@pytest.mark.requires_tm1
@pytest.mark.parametrize('folder', ['tm1cmApp', 'tm1cm #Folder 50%'])
def test_spreadsheet_without_extension(remote, folder):
    """Uploaded under a temporary .xlsx name and renamed, so TM1Web opens it; overwriting works too."""
    applications = remote.applications
    name = (folder, 'Report', 'blob')
    document = _document('Report')

    for _ in range(2):
        applications.update(name, copy.deepcopy(document), remote)

        assert [n for n in applications.list(remote) if n[0] == folder] == [name]
        assert dict(applications.get([name], remote))[name]['Content'] == document['Content']


@pytest.mark.requires_tm1
def test_delete(remote):
    applications = remote.applications
    name = ('tm1cmApp', 'Report', 'blob')
    applications.update(name, _document('Report'), remote)

    applications.delete(name, remote)

    assert name not in applications.list(remote)


def test_delete_local():
    local = LocalApplication(util.get_tm1cm_config(), tempfile.mkdtemp(prefix='tm1cm_test_'))
    applications = local.applications
    name = ('tm1cmApp', 'Report', 'blob')
    applications.update(name, _document('Report'), local)
    assert applications.list(local) == [name]

    applications.delete(name, local)

    assert applications.list(local) == []


@pytest.mark.requires_tm1
def test_reference_to_object_named_with_hash(remote):
    """TM1 encodes the name in the reference (Processes('...Proc%231')): the file holds it plain."""
    session = remote.session
    tm1_objects.create_process(session, 'tm1cmApp Proc#1')
    tm1_objects.create_folder(session, '', 'tm1cmRef')
    tm1_objects.create_process_reference(session, 'tm1cmRef', 'proc', 'tm1cmApp Proc#1')
    applications = remote.applications
    name = ('tm1cmRef', 'proc', 'process')

    got = dict(applications.get([name], remote))[name]
    local = LocalApplication(util.get_tm1cm_config(), tempfile.mkdtemp(prefix='tm1cm_test_'))
    applications.update(name, got, local)
    with open(os.path.join(local.path, 'data', 'application', 'tm1cmRef', 'proc.application')) as fp:
        assert 'Process: tm1cmApp Proc#1' in fp.read()

    from_files = dict(applications.get([name], local))[name]
    assert from_files == got
    applications.delete(name, remote)
    applications.update(name, from_files, remote)
    assert dict(applications.get([name], remote))[name] == got


@pytest.mark.requires_tm1
def test_get_missing_application_yields_nothing(remote):
    assert list(remote.applications.get([('tm1cmApp', 'Nope', 'blob')], remote)) == []
