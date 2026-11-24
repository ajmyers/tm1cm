import pytest

from tm1cm.ti_format import format_procedure

CASES = {
    'spacing and case': (
        "vCube='Sales';\r\nif(CubeExists(vCube)=1);\r\nnSum=nA+nB*-1;\r\nendif;\r\n",
        "vCube = 'Sales';\nIF(CUBEEXISTS(vCube) = 1);\n   nSum = nA + nB * -1;\nENDIF;\n",
    ),
    'nested blocks': (
        "IF(x=1);\nWHILE(i<=10);\ni=i+1;\nEND;\nELSEIF(x=2);\nItemSkip;\nELSE;\nItemReject('no');\nENDIF;\n",
        "IF(x = 1);\n   WHILE(i <= 10);\n      i = i + 1;\n   END;\nELSEIF(x = 2);\n   ITEMSKIP;\nELSE;\n   ITEMREJECT('no');\nENDIF;\n",
    ),
    'one statement per line': (
        "a=1; b=2;\n",
        "a = 1;\nb = 2;\n",
    ),
    'execute process parameters one pair per line': (
        "ExecuteProcess('Proc', 'pA', 1, 'pB', 'x y');\n",
        "ExecuteProcess('Proc'\n   , 'pA', 1\n   , 'pB', 'x y'\n);\n",
    ),
}


@pytest.mark.parametrize('text, expected', CASES.values(), ids=CASES.keys())
def test_format_procedure(text, expected):
    assert format_procedure(text) == expected


@pytest.mark.parametrize('text, expected', CASES.values(), ids=CASES.keys())
def test_format_procedure_is_idempotent(text, expected):
    # Formatting runs on every get: formatting formatted code must not change it, or every get
    # would show a diff
    assert format_procedure(expected) == expected


@pytest.mark.parametrize('text', [
    "s = 'hello  world  ';\n",
    "s = 'it''s';\n",
    "s = '# not a comment';\n",
    "s = 'a=b+c';\n",
], ids=['spaces', 'escaped quote', 'hash', 'operators'])
def test_format_procedure_leaves_strings_alone(text):
    assert format_procedure(text) == text


def test_format_procedure_leaves_comments_alone():
    text = "# keep   this=as+is\nx=1;\n"
    assert format_procedure(text) == "# keep   this=as+is\nx = 1;\n"
