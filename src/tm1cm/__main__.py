import argparse
import contextlib
import logging
import os
import tempfile
import textwrap
from shutil import rmtree

import git
from TM1py.Services import TM1Service

from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.common import get_config
from tm1cm.interactive import Interactive
from tm1cm.migration import Migration
from tm1cm.scaffold import create_scaffold


def main(mode, path, environment):
    logger = logging.getLogger(main.__name__)

    if mode == 'scaffold':
        create_scaffold(path)

    if mode in ['get', 'put']:
        credentials = get_config(path, 'credentials', environment)
        connect = get_config(path, 'connect', environment)

        remote_config = {**connect, **credentials}
        remote_session = TM1Service(**remote_config)

        local_config = get_config(path, 'tm1cm', environment)
        local_path = path

        source = RemoteApplication(local_config, remote_session)
        target = LocalApplication(local_config, local_path)

        if mode == 'put':
            source, target = target, source
        else:
            pass
            for scope in target.scopes:
                with contextlib.suppress(git.exc.GitCommandError):
                    target.repo.git.rm('-r', scope.path)
                with contextlib.suppress(OSError):
                    rmtree(os.path.join(target.path, scope.path), ignore_errors=True)

        migration = Migration(source, target)
        operations = migration.operations

        for op in operations:
            logger.info(f'Performing operation {op}')
            try:
                op.do(target)
            except Exception:
                logger.exception(f'Encountered exception while performing operation {op}')

    if mode in ['interactive']:
        Interactive(path).cmdloop()


def setup_logger(log, path, debug, stream=True, file=True):
    if not log:
        if not path:
            _, log_path = tempfile.mkstemp(prefix='tm1cm_')
        else:
            basename = os.path.basename(path)
            log_path = os.path.join(os.getcwd(), '{}.log'.format(basename))
    else:
        log_path = log

    handlers = []
    if stream:
        handlers.append(logging.StreamHandler())

    if file:
        handlers.append(logging.FileHandler(os.path.abspath(log_path)))

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(funcName)s(%(lineno)d) - %(levelname)s - %(message)s',
        handlers=handlers
    )


def start():
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
    parser.add_argument('--mode', help='', required=False, choices=['get', 'put', 'scaffold', 'interactive'], default='interactive')
    parser.add_argument('--path', help='', required=False, default=os.path.abspath(os.getcwd()))
    parser.add_argument('--environment', help='', required=False, default=None)
    parser.add_argument('--log', help='', required=False, default=None)
    parser.add_argument('--debug', help='', required=False, action='store_true')

    args = parser.parse_args()
    setup_logger(args.log, args.path, args.debug, file=True, stream=False if args.mode == 'interactive' else True)

    main(args.mode, args.path, args.environment)


if __name__ == '__main__':
    start()
