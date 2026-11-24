"""What tm1cm tells the user when something goes wrong, and what it keeps for support.

Known failures are a :class:`TM1cmError`, raised where tm1cm knows what it was doing: a message in
plain words, a hint at what to try, and an exit code. Errors from TM1, the network, git and YAML
are turned into one by :func:`translate`. Anything else is a bug, and says so.

Every error, known or not, also writes a full report to the log file (:func:`report`): the
traceback with its causes, the command, the versions of tm1cm, skipcheck-tm1, Python and the OS,
the TM1 servers connected to, and what tm1cm was doing. Credentials never reach a message or the
log: the secrets tm1cm handles are registered with :func:`secret`, and every record and report is
passed through :func:`redact`.
"""
import contextlib
import logging
import os
import platform
import re
import sys
import tempfile
import traceback

ISSUES = 'https://github.com/ajmyers/tm1cm/issues'

# Exit codes, for scripts and CI
OK = 0
CONFIG = 2          # a setting or argument is missing or wrong (argparse uses 2 as well)
UNREACHABLE = 3     # TM1 or Cognos couldn't be reached
LOGIN = 4           # the login was refused or couldn't be made
TM1 = 5             # TM1 refused an object, or some operations failed
BUG = 70            # an unexpected error (EX_SOFTWARE)
CANCELLED = 130     # the user cancelled (Ctrl-C, or closed the sign-in)

support = logging.getLogger('tm1cm.support')
# Only to the log file: setup_logger gives it the file handler, and the console never sees it
support.propagate = False


class TM1cmError(Exception):
    """A failure tm1cm understands: ``message`` says what happened, ``hint`` what to try."""

    exit_code = BUG

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.message = message
        self.hint = hint


class ConfigError(TM1cmError, ValueError):
    """A config file or setting is missing or invalid. A ValueError too, as tm1cm raised for
    these before."""

    exit_code = CONFIG


class ServerUnreachable(TM1cmError):
    """TM1 or Cognos didn't answer."""

    exit_code = UNREACHABLE


class LoginError(TM1cmError):
    """No login could be made: no password without a terminal to ask for one, no browser..."""

    exit_code = LOGIN


class LoginRejected(LoginError):
    """TM1 refused the credentials."""


class Cancelled(TM1cmError):
    """The user cancelled."""

    exit_code = CANCELLED


class TM1Refused(TM1cmError):
    """TM1 refused a request for an object."""

    exit_code = TM1


class OperationsFailed(TM1cmError):
    """Some operations of a get or put failed; the others were done."""

    exit_code = TM1

    def __init__(self, failures, total):
        self.failures = failures
        shown = '\n'.join(f'  {op}: {describe(error)}' for op, error in failures[:10])
        more = f'\n  ...and {len(failures) - 10} more' if len(failures) > 10 else ''
        super().__init__(f'{len(failures)} of {total} operations failed:\n{shown}{more}',
                         'The other operations were done. Fix what TM1 refused, then run tm1cm again.')


# --- Secrets -------------------------------------------------------------------------------------

_secrets = set()

# Credentials in a header or a setting, wherever they show up in text
_PATTERNS = [
    re.compile(r'(Authorization[\'"]?\s*[:=]\s*[\'"]?(?:Basic|CAMNamespace|CAMPassport|Bearer|Negotiate)\s+)[^\s\'",;}]+', re.IGNORECASE),
    re.compile(r'((?:password|cam_passport|passport|secret|token)[\'"]?\s*[:=]\s*[\'"]?)[^\s\'",;}]+', re.IGNORECASE),
    re.compile(r'(cam_passport=)[^\s;\'",}]+', re.IGNORECASE),
]
REDACTED = '***'
SECRET_KEYS = ('password', 'cam_passport', 'passport', 'secret', 'token')


def secret(value):
    """Registers a secret (a password, a passport) so that it never appears in a message or log."""
    if value and isinstance(value, str) and len(value) >= 3:
        _secrets.add(value)
    return value


def redact(text):
    """The text with every registered secret, and anything that looks like credentials, masked."""
    text = str(text)
    for value in sorted(_secrets, key=len, reverse=True):
        text = text.replace(value, REDACTED)
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + REDACTED, text)
    return text


def redact_settings(settings):
    """A copy of connection settings with the values of secret keys masked."""
    return {k: (REDACTED if v and any(s in str(k).lower() for s in SECRET_KEYS) else v) for k, v in (settings or {}).items()}


class RedactingFilter(logging.Filter):
    """Masks secrets in every record a handler writes."""

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = redact(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        if record.exc_info and not record.exc_text:
            record.exc_text = redact(''.join(traceback.format_exception(*record.exc_info)).rstrip('\n'))
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


# --- What tm1cm was doing ------------------------------------------------------------------------

_activities = []
_servers = {}
log_path = None


@contextlib.contextmanager
def doing(activity):
    """Names what tm1cm is doing, for the messages and the report of an error raised meanwhile."""
    _activities.append(activity)
    try:
        yield
    except BaseException as e:
        # The innermost activity is the one the error happened in
        if not hasattr(e, '_tm1cm_activity'):
            with contextlib.suppress(Exception):
                e._tm1cm_activity = activity
        raise
    finally:
        _activities.pop()


def activity_of(error):
    return getattr(error, '_tm1cm_activity', None) or (_activities[-1] if _activities else None)


def connected(root, version):
    """Notes a TM1 server connected to, for the report."""
    _servers[root] = version


# --- Turning other errors into ours ---------------------------------------------------------------

def _find(error, kind):
    seen = set()
    while error is not None and id(error) not in seen:
        if isinstance(error, kind):
            return error
        seen.add(id(error))
        error = error.__cause__ or error.__context__
    return None


def _untrusted(error):
    text = ''
    seen = set()
    while error is not None and id(error) not in seen:
        text += str(error)
        seen.add(id(error))
        error = error.__cause__ or error.__context__
    return 'CERTIFICATE_VERIFY_FAILED' in text


CERTIFICATE_HINT = ("The server's certificate isn't trusted. If it's self-signed, set verify in connect.yaml to the "
                    'path of a CA bundle that signs it, or to false to not check it.')


def describe(error):
    """An error in a line: TM1's own message for a refusal, else the error's text."""
    from tm1cm.tm1 import Tm1RestError

    if isinstance(error, TM1cmError):
        return redact(error.message)
    if isinstance(error, Tm1RestError):
        return redact(f'TM1 refused {error.method} ({error.status_code}): {error.text}')
    text = str(error) or type(error).__name__
    return redact(text.splitlines()[0] if text else text)


def translate(error):
    """The error as a :class:`TM1cmError`, or None when it's unexpected (a bug)."""
    from skipcheck_tm1 import errors as tm1_errors

    from tm1cm.tm1 import Tm1RestError

    if isinstance(error, TM1cmError):
        return error
    if isinstance(error, KeyboardInterrupt):
        return Cancelled('Cancelled.')
    activity = activity_of(error)
    where = f' while {activity}' if activity else ''

    transport = _find(error, tm1_errors.Tm1TransportError)
    if transport is not None:
        hint = CERTIFICATE_HINT if _untrusted(error) else 'Check base_url (or address, port and ssl) in connect.yaml, and that the server is running.'
        return ServerUnreachable(redact(f"Couldn't reach TM1{where}: {transport}"), hint)

    # Before Tm1RestError: tm1.Rest wraps every refusal in one, a refused login too
    api = _find(error, tm1_errors.Tm1ApiError)
    if api is not None and api.kind == tm1_errors.Tm1ErrorKind.CREDENTIAL_REJECTED:
        return LoginRejected(redact(f'TM1 refused the login{where}.'), 'Check user, password and namespace in credentials.yaml.')

    refused = _find(error, Tm1RestError)
    if refused is not None:
        return TM1Refused(redact(f'TM1 refused a request{where}: {refused.text}'), f'{refused.method} {refused.url} answered {refused.status_code}.')

    api = _find(error, tm1_errors.Tm1ApiError)
    if api is not None:
        if api.kind == tm1_errors.Tm1ErrorKind.CREDENTIAL_REJECTED:
            return LoginRejected(redact(f'TM1 refused the login{where}.'), 'Check user, password and namespace in credentials.yaml.')
        message = api.error.message if getattr(api, 'error', None) else str(api)
        return TM1Refused(redact(f'TM1 refused a request{where}: {message}'))

    try:
        import yaml
        if isinstance(error, yaml.YAMLError):
            return ConfigError(redact(f'A config file is not valid YAML: {error}'))
    except ImportError:
        pass

    try:
        from git import exc as git_errors
        if _find(error, git_errors.GitCommandNotFound) is not None:
            return ConfigError('tm1cm needs git, and git was not found.', 'Install git, and make sure it is on your PATH.')
        command = _find(error, git_errors.GitCommandError)
        if command is not None:
            return TM1cmError(redact(f'git failed{where}: {command.stderr.strip() or command}'))
    except ImportError:
        pass
    return None


# --- Showing them --------------------------------------------------------------------------------

def message(error, debug=False, report_file=None):
    """What the console shows for an error."""
    known = translate(error)
    lines = []
    if known is not None:
        lines.append(f'tm1cm: {known.message}')
        if known.hint:
            lines.append(known.hint)
    else:
        activity = activity_of(error)
        lines.append(f"tm1cm hit an unexpected error{f' while {activity}' if activity else ''}. This is likely a bug.")
        lines.append(f'{type(error).__name__}: {describe(error)}')
    if debug:
        lines.append(redact(''.join(traceback.format_exception(error)).rstrip()))
    if report_file and not isinstance(known, Cancelled):
        lines.append(f'The full report is in {report_file}. Attach it if you report an issue at {ISSUES}')
    return '\n'.join(lines)


def exit_code(error):
    known = translate(error)
    return known.exit_code if known is not None else BUG


def _version(package):
    try:
        from importlib.metadata import version
        return version(package)
    except Exception:
        return 'unknown'


def report_text(error):
    activity = activity_of(error)
    servers = ', '.join(f'{root} ({version})' for root, version in _servers.items()) or 'none'
    lines = [
        '--- tm1cm error report ---',
        f'Command: {redact(" ".join(sys.argv))}',
        f'Doing: {activity or "unknown"}',
        f'tm1cm {_version("tm1cm")}, skipcheck-tm1 {_version("skipcheck-tm1")}, Python {platform.python_version()}, '
        f'{platform.platform()}',
        f'TM1 servers: {servers}',
        ''.join(traceback.format_exception(error)).rstrip(),
        '--- end of report ---',
    ]
    return redact('\n'.join(lines))


def report(error):
    """Writes the error's full report to the log file, or to a file of its own when there's no log
    file, and returns that file's path."""
    text = report_text(error)
    if log_path:
        support.error(text)
        for handler in support.handlers:
            handler.flush()
        return log_path
    fd, path = tempfile.mkstemp(prefix='tm1cm_error_', suffix='.log')
    with os.fdopen(fd, 'w', encoding='utf-8') as fp:
        fp.write(text + '\n')
    return path


def handle(error, debug=False, stream=None):
    """Reports the error, shows its message, and returns the exit code."""
    stream = stream or sys.stderr
    try:
        path = report(error)
    except Exception:
        path = None
    print(message(error, debug, path), file=stream)
    return exit_code(error)
