"""A process read from TM1 and the same process read back from its file are the same, so an
unchanged process doesn't show as changed (#41). Without TM1: TM1's answer is stood in for."""
import pytest

from tests.tm1cm import util
from tm1cm.application import LocalApplication

GENERATED = '#****Begin: Generated Statements***\r\n#****End: Generated Statements****'


@pytest.mark.parametrize('code', [
    GENERATED,                                  # an empty procedure, as TM1 has it
    GENERATED + '\r\nX = 1;',                  # code straight after the generated statements
    GENERATED + '\r\n\r\nX = 1;\r\n',          # with the blank line already
    'X = 1;\r\nY = 2;',                        # no generated statements
    '',
], ids=['empty', 'code after', 'blank line', 'none', 'nothing'])
def test_a_process_from_tm1_reads_back_the_same_from_its_file(tmp_path, code):
    app = LocalApplication(util.get_tm1cm_config(), str(tmp_path / 'project'))
    scope = app.processes
    from_tm1 = scope._transform_from_remote('p', {
        'Name': 'p', 'HasSecurityAccess': False, 'Parameters': [], 'Variables': [], 'DataSource': {'Type': 'None'},
        'PrologProcedure': code, 'MetadataProcedure': code, 'DataProcedure': code, 'EpilogProcedure': code,
    })

    scope.update('p', from_tm1, app)
    from_file = dict(scope.get(['p'], app))['p']

    assert from_file == from_tm1
