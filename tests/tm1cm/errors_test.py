"""tm1cm.errors: what the user is told, the exit code, and the report kept for support."""
import logging

import pytest
import yaml
from git import exc as git_errors
from skipcheck_tm1 import errors as tm1_errors

from tm1cm import errors
from tm1cm.tm1 import Tm1RestError


def transport_error(cause):
    return tm1_errors.Tm1TransportError(tm1_errors.Tm1TransportError.Phase.CONNECT, True, 'GET', 'https://tm1:1/api/v1/x', cause)


def rejected_login():
    return tm1_errors.Tm1ApiError.of_kind(401, tm1_errors.Tm1ErrorKind.CREDENTIAL_REJECTED, None, 'GET', 'https://tm1:1/api/v1/ActiveSession')


def raised(error, cause=None):
    """The error as Python leaves it once raised (with a traceback, and its cause)."""
    try:
        if cause is not None:
            try:
                raise cause
            except BaseException:
                raise error
        raise error
    except BaseException as e:
        return e


# --- Secrets ----------------------------------------------------------------------------------

def test_registered_secrets_are_masked():
    errors.secret('apple-pie')

    assert errors.redact("user admin, password apple-pie") == 'user admin, password ***'


def test_short_values_are_not_registered_so_text_stays_readable():
    errors.secret('a')

    assert errors.redact('a cat') == 'a cat'


@pytest.mark.parametrize('text, expected', [
    ("{'Authorization': 'Basic YWRtaW46YXBwbGU='}", "{'Authorization': 'Basic ***'}"),
    ('Authorization: CAMPassport MTsxMDE6abc', 'Authorization: CAMPassport ***'),
    ("password: 'apple'", "password: '***'"),
    ('cam_passport=MTsxMDE6abc; Path=/', 'cam_passport=***; Path=/'),
], ids=['header in a dict', 'header', 'setting', 'cookie'])
def test_credentials_in_text_are_masked(text, expected):
    assert errors.redact(text) == expected


def test_settings_are_masked_by_key():
    assert errors.redact_settings({'user': 'admin', 'password': 'apple', 'cam_passport': '', 'base_url': 'x'}) == \
        {'user': 'admin', 'password': '***', 'cam_passport': '', 'base_url': 'x'}


def test_the_log_filter_masks_messages_and_tracebacks():
    errors.secret('apple-pie')
    record = logging.LogRecord('tm1cm', logging.ERROR, __file__, 1, 'logging in with %s', ('apple-pie',),
                               (ValueError, ValueError('bad apple-pie'), None))

    errors.RedactingFilter().filter(record)

    assert record.getMessage() == 'logging in with ***'
    assert 'apple-pie' not in record.exc_text


# --- Translating -------------------------------------------------------------------------------

@pytest.mark.parametrize('error, kind, code', [
    (transport_error(ConnectionRefusedError('refused')), errors.ServerUnreachable, errors.UNREACHABLE),
    (raised(Tm1RestError(404, 'Cube not found', 'GET', '/api/v1/Cubes')), errors.TM1Refused, errors.TM1),
    (rejected_login(), errors.LoginRejected, errors.LOGIN),
    (yaml.YAMLError('bad'), errors.ConfigError, errors.CONFIG),
    (git_errors.GitCommandNotFound('git', 'not found'), errors.ConfigError, errors.CONFIG),
    (KeyboardInterrupt(), errors.Cancelled, errors.CANCELLED),
    (errors.LoginError('no'), errors.LoginError, errors.LOGIN),
], ids=['unreachable', 'TM1 refused', 'login refused', 'YAML', 'no git', 'Ctrl-C', 'ours'])
def test_known_errors_get_their_kind_and_exit_code(error, kind, code):
    assert isinstance(errors.translate(error), kind)
    assert errors.exit_code(error) == code


def test_tm1s_refusal_is_found_through_the_chain():
    error = raised(RuntimeError('while updating'), Tm1RestError(400, "Invalid element 'x'", 'POST', '/api/v1/Cubes'))

    assert "Invalid element 'x'" in errors.translate(error).message


def test_an_untrusted_certificate_gets_its_hint():
    error = transport_error(OSError('[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed'))

    assert 'verify in connect.yaml' in errors.translate(error).hint


def test_unexpected_errors_are_bugs():
    assert errors.translate(KeyError('Name')) is None
    assert errors.exit_code(KeyError('Name')) == errors.BUG


# --- Messages ---------------------------------------------------------------------------------

def test_a_known_error_shows_its_message_hint_and_report():
    text = errors.message(errors.ConfigError('No TM1 server is set.', 'Set base_url.'), report_file='/logs/p.log')

    assert text.splitlines() == ['tm1cm: No TM1 server is set.', 'Set base_url.',
                                 f'The full report is in /logs/p.log. Attach it if you report an issue at {errors.ISSUES}']


def test_an_unexpected_error_says_what_tm1cm_was_doing_and_that_its_a_bug():
    with pytest.raises(KeyError) as caught:
        with errors.doing('performing UPDATE_CUBE: Sales'):
            raise KeyError('Dimensions')

    text = errors.message(caught.value)

    assert 'unexpected error while performing UPDATE_CUBE: Sales. This is likely a bug.' in text
    assert "KeyError: 'Dimensions'" in text
    assert 'Traceback' not in text


def test_debug_shows_the_traceback():
    assert 'Traceback' in errors.message(raised(KeyError('x')), debug=True)


def test_a_cancel_has_no_report_to_attach():
    assert 'report' not in errors.message(KeyboardInterrupt(), report_file='/logs/p.log')


def test_failed_operations_are_listed_with_tms_reasons():
    failures = [(f'UPDATE_PROCESS: p{i}', Tm1RestError(400, f'bad {i}', 'PATCH', '/x')) for i in range(12)]

    error = errors.OperationsFailed(failures, 40)

    assert error.message.startswith('12 of 40 operations failed:')
    assert 'UPDATE_PROCESS: p0: TM1 refused PATCH (400): bad 0' in error.message
    assert 'p10' not in error.message and '...and 2 more' in error.message
    assert error.exit_code == errors.TM1


# --- The report -------------------------------------------------------------------------------

def test_the_report_has_what_support_needs_and_no_secrets():
    errors.secret('apple-pie')
    errors.connected('https://tm1:8010', '11.8.02300.1')
    with pytest.raises(RuntimeError) as caught:
        with errors.doing('performing UPDATE_CUBE: Sales'):
            raise raised(RuntimeError('wrapped apple-pie'), ValueError('the cause'))

    text = errors.report_text(caught.value)

    for part in ['Command: ', 'Doing: performing UPDATE_CUBE: Sales', 'tm1cm ', 'skipcheck-tm1 ', 'Python ',
                 'TM1 servers: https://tm1:8010 (11.8.02300.1)', 'ValueError: the cause', 'RuntimeError: wrapped ***']:
        assert part in text
    assert 'apple-pie' not in text


def test_the_report_goes_to_the_log_file_only(tmp_path, monkeypatch, capsys):
    from tm1cm.__main__ import close_logger
    from tm1cm.__main__ import setup_logger

    # The real report, not conftest's stand-in
    monkeypatch.setattr(errors, 'report', REAL_REPORT)
    log = setup_logger(str(tmp_path / 'run.log'), None, False, stream=False)
    try:
        code = errors.handle(raised(KeyError('x')))
    finally:
        close_logger()

    assert code == errors.BUG
    console = capsys.readouterr()
    assert 'Traceback' not in console.err + console.out
    assert f'The full report is in {log}' in console.err
    assert 'Traceback' in open(log, encoding='utf-8').read()


def test_without_a_log_file_the_report_gets_a_file_of_its_own(monkeypatch, capsys):
    from tm1cm.__main__ import close_logger
    from tm1cm.__main__ import setup_logger

    monkeypatch.setattr(errors, 'report', REAL_REPORT)
    setup_logger(None, None, False, file=False, stream=False)
    try:
        errors.handle(raised(KeyError('x')))
    finally:
        close_logger()

    path = capsys.readouterr().err.split('The full report is in ')[1].split('. Attach')[0]
    assert 'KeyError' in open(path, encoding='utf-8').read()


REAL_REPORT = errors.report


def test_a_refused_login_wrapped_as_tm1_rest_error_is_a_login_error():
    error = raised(Tm1RestError(401, '', 'GET', '/x'), cause=rejected_login())

    assert isinstance(errors.translate(error), errors.LoginRejected)
    assert errors.exit_code(error) == errors.LOGIN
