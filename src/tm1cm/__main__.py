import argparse
import logging
import os
import tempfile

from TM1py.Services import TM1Service

from tm1cm.application import LocalApplication, RemoteApplication
from tm1cm.common import get_config
from tm1cm.interactive import Interactive
from tm1cm.migration import Migration
from tm1cm.scaffold import create_scaffold


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', help='', required=False, choices=['get', 'put', 'scaffold', 'interactive'], default='interactive')
    parser.add_argument('--path', help='', required=False, default=os.path.abspath(os.getcwd()))
    parser.add_argument('--log', help='', required=False, default=None)
    parser.add_argument('--environment', help='', required=False, default=None)
    parser.add_argument('--debug', help='', required=False, action='store_true')

    args = parser.parse_args()

    show_splash()

    if args.mode in ['scaffold']:
        setup_logger(args.log, args.path, args.debug)
        create_scaffold(args.path)

    if args.mode in ['get', 'put']:
        setup_logger(args.log, args.path, args.debug)
        function = globals().get(args.mode)

        credentials = get_config(args.path, 'credentials', args.environment)
        connect = get_config(args.path, 'connect', args.environment)

        remote_config = {**connect, **credentials}

        remote_session = TM1Service(**remote_config)

        local_config = get_config(args.path, 'tm1cm', args.environment)
        local_path = args.path

        function(local_config, local_path, remote_session)

    if args.mode in ['interactive']:
        setup_logger(args.log, args.path, args.debug, True)
        interactive(args.path)


def get(tm1cm_config, data_path, remote_session):
    app = RemoteApplication(tm1cm_config, remote_session).refresh(False)
    app.to_local(data_path, clear=True)


def put(config, path, session):
    app_from = LocalApplication(config, path).refresh(True)
    app_to = RemoteApplication(config, session).refresh(None)

    migration = Migration(app_from, app_to)
    migration.do_all_operations()


def interactive(path):
    Interactive(path).cmdloop()


def setup_logger(log, path, debug, nostream=False):
    if not log:
        if not path:
            _, log_path = tempfile.mkstemp(prefix='tm1cm_')
        else:
            basename = os.path.basename(path)
            log_path = os.path.join(os.getcwd(), '{}.log'.format(basename))
    else:
        log_path = log

    if nostream:
        handlers = [logging.FileHandler(os.path.abspath(log_path))]
    else:
        handlers = [
            logging.FileHandler(os.path.abspath(log_path)),
            logging.StreamHandler()
        ]

    # setup logger
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(module)s - %(funcName)s(%(lineno)d) - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def show_splash():
    splash = r'''----------------------------------
TM1 Code Migrate
----------------------------------                                                      
 Created By: Andrew Myers (me@ajmyers.net) -- https://www.linkedin.com/in/andrew-myers-3112248/
 Homepage: https://github.com/ajmyers/tm1cm
 Issues & Bugs: https://github.com/ajmyers/tm1cm/issues
-----------------------------------
'''
    print(splash)


if __name__ == '__main__':
    main()
