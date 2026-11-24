import argparse
import contextlib
import logging
import os
import sys
import tempfile
import textwrap
from shutil import rmtree

from tm1cm import errors
from tm1cm import files
from tm1cm import tm1 as tm1_client
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.common import get_config
from tm1cm.interactive import Interactive
from tm1cm.migration import Migration
from tm1cm.scaffold import create_scaffold


def main(mode, path, environment, overrides=None, paths=None):
    """Runs one mode. Raises a TM1cmError for what went wrong; :func:`start` reports it.

    ``overrides`` are connection settings (from --connect) that win over connect.yaml and
    credentials.yaml, in every environment. ``paths``, for get and put, are the object files to
    get or put, instead of everything tm1cm.yaml selects (see tm1cm.files)."""
    overrides = overrides or {}
    paths = paths or []
    if paths and mode not in ['get', 'put']:
        raise errors.ConfigError(f'Files are for get and put, not {mode}.', 'Leave the files out, or use --mode get or --mode put.')
    logger = logging.getLogger(main.__name__)

    if mode == 'scaffold':
        with errors.doing(f'creating a project at {path}'):
            create_scaffold(path)

    if mode in ['get', 'put']:
        check_project(path, environment)
        where = f'config/{environment}' if environment else 'config/default'
        with errors.doing(f'reading the settings in {os.path.join(path, where)}'):
            credentials = get_config(path, 'credentials', environment)
            connect = get_config(path, 'connect', environment)
            local_config = get_config(path, 'tm1cm', environment)

        local = LocalApplication(local_config, path)
        if paths:
            files.check(paths, local)

        remote_config = {**connect, **credentials, **overrides}
        try:
            remote_session = tm1_client.connect(**remote_config)
        except errors.ConfigError as e:
            # Say which environment's files to fix
            e.hint = f'{e.hint} ({where} in {path})' if e.hint else f'See {where} in {path}.'
            raise

        remote = RemoteApplication(local_config, remote_session)
        source, target = (remote, local) if mode == 'get' else (local, remote)

        if paths:
            with errors.doing(f'working out what to {mode} for the files given'):
                operations = files.operations(mode, local, remote, paths)
        else:
            if mode == 'get':
                for scope in target.scopes:
                    with contextlib.suppress(OSError):
                        rmtree(os.path.join(target.path, scope.path), ignore_errors=True)

            with errors.doing(f'working out what to {mode}'):
                migration = Migration(source, target)
                operations = migration.operations

        failures = []
        for op in operations:
            logger.info(f'Performing operation {op}')
            try:
                with errors.doing(f'performing {op}'):
                    op.do(target)
            except (KeyboardInterrupt, errors.LoginError, errors.ServerUnreachable):
                raise
            except Exception as e:
                # TM1 gone, or refusing the login: the rest would fail the same way, one timeout each
                if isinstance(errors.translate(e), (errors.LoginError, errors.ServerUnreachable)):
                    raise
                logger.exception(f'Encountered exception while performing operation {op}')
                failures.append((op, e))
        if failures:
            raise errors.OperationsFailed(failures, len(operations))

    if mode in ['interactive']:
        Interactive(path, overrides).cmdloop()


def connect_setting(text):
    """One --connect KEY=VALUE: the key a connection setting, the value read as YAML reads it
    (true, 8010, 'text'), so it means what it would in connect.yaml."""
    import yaml

    key, equals, value = text.partition('=')
    key = key.strip()
    if not equals or not key:
        raise argparse.ArgumentTypeError(f'"{errors.redact(text)}" is not KEY=VALUE, e.g. base_url=https://tm1:8010')
    if key not in tm1_client.SETTINGS:
        raise argparse.ArgumentTypeError(f'"{key}" is not a connection setting. Settings: {", ".join(sorted(tm1_client.SETTINGS))}')
    try:
        parsed = yaml.safe_load(value) if value.strip() else ''
    except yaml.YAMLError:
        parsed = value
    if isinstance(parsed, (dict, list)):
        parsed = value
    errors.secret(str(parsed) if key in errors.SECRET_KEYS else None)
    return key, parsed


def check_project(path, environment):
    """Refuses a folder that isn't a tm1cm project, or an environment it doesn't have."""
    config = os.path.join(path, 'config')
    if not os.path.isdir(config):
        raise errors.ConfigError(f'{path} is not a tm1cm project: it has no config folder.',
                                 'Run tm1cm in a project folder, or give one with --path. --mode scaffold creates one.')
    if environment and not os.path.isdir(os.path.join(config, environment)):
        found = sorted(e for e in os.listdir(config) if e != 'default' and not e.startswith('.') and os.path.isdir(os.path.join(config, e)))
        raise errors.ConfigError(f'The project at {path} has no environment {environment}.',
                                 f'Its environments: {", ".join(found) or "none"}. Each is a folder under config.')


_handlers = []


def close_logger():
    """Removes and closes the handlers setup_logger added, leaving any others."""
    root = logging.getLogger()
    while _handlers:
        handler = _handlers.pop()
        root.removeHandler(handler)
        errors.support.removeHandler(handler)
        handler.close()
    errors.log_path = None


def setup_logger(log, path, debug, stream=True, file=True):
    """Logs to the console (unless ``stream`` is False) and to a file (unless ``file`` is False):
    ``log``, or <project folder name>.log in the current folder, or a temporary file. Error
    reports go to the file only. Returns the file's path, or None."""
    if not log:
        if not path:
            fd, log_path = tempfile.mkstemp(prefix='tm1cm_', suffix='.log')
            os.close(fd)
        else:
            basename = os.path.basename(os.path.normpath(path))
            log_path = os.path.join(os.getcwd(), '{}.log'.format(basename))
    else:
        log_path = log
    log_path = os.path.abspath(log_path)

    redacting = errors.RedactingFilter()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s(%(lineno)d) - %(levelname)s - %(message)s')

    close_logger()
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    if stream:
        handler = logging.StreamHandler()
        handler.addFilter(redacting)
        handler.setFormatter(formatter)
        root.addHandler(handler)
        _handlers.append(handler)

    errors.log_path = None
    if file:
        try:
            handler = logging.FileHandler(log_path, encoding='utf-8')
        except OSError as e:
            print(f'tm1cm: could not write the log file {log_path} ({e}): logging to the console only.', file=sys.stderr)
        else:
            handler.addFilter(redacting)
            handler.setFormatter(formatter)
            root.addHandler(handler)
            errors.support.addHandler(handler)
            _handlers.append(handler)
            errors.log_path = log_path
    return errors.log_path


def start(argv=None):
    """The tm1cm command. Returns its exit code (see tm1cm.errors)."""
    splash = '''\
            ----------------------------------
            TM1 Code Migrate
            ----------------------------------                                                      
            Created By: Andrew Myers (me@ajmyers.net) -- https://www.linkedin.com/in/andrew-myers-3112248/
            Homepage: https://github.com/ajmyers/tm1cm
            Issues & Bugs: https://github.com/ajmyers/tm1cm/issues
            -----------------------------------
            '''

    print(textwrap.dedent(splash))

    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', help='get from TM1, put to TM1, create a project (scaffold), or pick operations interactively', required=False, choices=['get', 'put', 'scaffold', 'interactive'], default='interactive')
    parser.add_argument('--path', help='the project folder (default: the current folder)', required=False, default=os.path.abspath(os.getcwd()))
    parser.add_argument('--environment', help="the environment under config/ to get from or put to", required=False, default=None)
    parser.add_argument('--log', help='the log file (default: <project>.log in the current folder)', required=False, default=None)
    parser.add_argument('--connect', '-c', help='a connection setting to use instead of the one in connect.yaml or '
                        'credentials.yaml, e.g. -c user=admin -c verify=true. Repeat for each setting', required=False,
                        action='append', default=[], metavar='KEY=VALUE', type=connect_setting)
    parser.add_argument('files', nargs='*', metavar='FILE', help='for get and put: only the objects these files are '
                        "(e.g. data/process/Load.process), whatever tm1cm.yaml's filters select. put deletes from TM1 "
                        "the object of a file that's gone; get deletes the file of an object TM1 hasn't got")
    parser.add_argument('--debug', help='log debug messages, and show the full traceback of an error', required=False, action='store_true')

    args = parser.parse_args(argv)
    setup_logger(args.log, args.path, args.debug, file=True, stream=False if args.mode == 'interactive' else True)

    try:
        main(args.mode, args.path, args.environment, dict(args.connect), args.files)
    except BaseException as e:
        if isinstance(e, SystemExit):
            raise
        return errors.handle(e, debug=args.debug)
    return errors.OK


if __name__ == '__main__':
    sys.exit(start())
