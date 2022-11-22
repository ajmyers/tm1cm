import cmd
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
from fnmatch import fnmatch

from termcolor import colored

from tm1cm.application import RemoteApplication, LocalApplication
from tm1cm.common import get_config
from tm1cm.migration import Migration


class Interactive(cmd.Cmd):

    def __init__(self, path=None):
        self.intro = 'Welcome to TM1 Code Migrate interactive!\n'
        self.prompt = '(tm1cm) $ '
        self.migration = None
        self.apps = {}
        self.stage = []

        if path:
            self.config_apps_from_path(path)

        super().__init__()

    def config_apps_from_path(self, path):
        logger = logging.getLogger(__name__)

        if not os.path.exists(path):
            return

        if os.path.exists(os.path.join(path, 'config', 'default')):
            app_name = os.path.basename(path)
            environments = os.listdir(os.path.join(path, 'config'))
            for environment in environments:
                if environment == 'default':
                    self.add_local_path('{}.{}'.format(app_name, 'local'), path)
                elif not environment.startswith('.'):
                    logger.info('Adding app: {} with environment: {}'.format(app_name, environment))
                    self.add_path('{}.{}'.format(app_name, environment), path, environment)
        else:
            apps = os.listdir(path)
            for app in apps:
                app_path = os.path.join(path, app)
                app_config_path = os.path.join(path, app, 'config')
                if os.path.exists(os.path.join(app_config_path, 'default')):
                    environments = os.listdir(app_config_path)
                    for environment in environments:
                        if environment == 'default':
                            self.add_local_path('{}.{}'.format(app, 'local'), app_path)
                        elif not environment.startswith('.'):
                            logger.info('Adding app: {} with environment: {}'.format(app, environment))
                            self.add_path('{}.{}'.format(app, environment), app_path, environment)

    def do_path(self, args):
        """Adds a project or collection or projects at the specified path"""
        logger = logging.getLogger(__name__)
        try:
            self.config_apps_from_path(args)
            self.do_ls('app')
        except Exception:
            print('Error occurred:', '\n', traceback.format_exc())
            logger.exception('Error occurred')

    def add_local_path(self, name, path):
        config = get_config(path, 'tm1cm', None)
        self.apps[name] = LocalApplication(config, path)

    def add_path(self, name, path, environment):
        config = get_config(path, 'tm1cm', environment)
        credentials = get_config(path, 'credentials', environment)
        connect = get_config(path, 'connect', environment)

        session_config = {**connect, **credentials}

        self.apps[name] = RemoteApplication(config, session_config=session_config)

    def do_do(self, arg):
        """Execute the currently staged operations. Optionally, specify 'all'
        to run all operations bypassing the staging process"""
        logger = logging.getLogger(__name__)
        try:
            if arg == 'all':
                ops = self.migration.operations
                message = 'Perform ALL operations? ({}/{})'.format(len(ops), len(ops))
            else:
                ops = self.stage
                message = 'Perform STAGED operations? ({}/{})'.format(len(ops), len(self.migration.operations))

            while True:
                print(message)
                confirm = input('[y/n]? ')
                if confirm in ['y', 'n']:
                    break

            spinner = Spinner()

            if confirm == 'y':
                do_backup = self.migration.target.config.get('backup_on_migrate', False)
                allow_override = self.migration.target.config.get('backup_allow_override', True)
                backup_process = self.migration.target.config.get('backup_process', None)

                if backup_process:
                    if allow_override:
                        while True:
                            print('Backup target prior to migration?')
                            confirm = input('[y/n]? ')
                            if confirm in ['y', 'n']:
                                do_backup = True if confirm == 'y' else False
                                break
                    if do_backup:
                        spinner.start()
                        self.migration.target.session.processes.execute(backup_process)
                        spinner.stop()
                pass

                target = self.migration.target
                for op in ops:
                    print(colored('Doing: {}'.format(str(op)), 'green'))
                    spinner.start()
                    op.do(target)
                    spinner.stop()
        except Exception:
            print('Error occurred:', traceback.format_exc())
            logger.exception('Error occurred')

    def do_ls(self, arg):
        logger = logging.getLogger(__name__)
        try:
            if not arg:
                arg = 'operations'
            if arg in ['app', 'apps', 'applications']:
                for app, _ in self.apps.items():
                    print(app)
            if arg in ['migration', 'operations']:
                if self.migration:
                    for op in self.migration.operations:
                        color = 'green' if op in self.stage else 'red'
                        print(colored(op, color))
            if arg in ['stage']:
                for op in self.stage:
                    print(colored(op, 'green'))
        except Exception:
            print('Error occurred:', '\n', traceback.format_exc())
            logger.exception('Error occurred')

    def do_migrate(self, args):
        logger = logging.getLogger(__name__)
        spinner = Spinner()
        self.stage = []
        try:
            app_from, app_to = args.split(' ', maxsplit=2)

            spinner.start()

            app_from = self.apps[app_from].refresh()
            app_to = self.apps[app_to].refresh()

            self.migration = Migration(app_from, app_to)
        except Exception:
            print('Error occurred:', '\n', traceback.format_exc())
            logger.exception('Error occurred')
        finally:
            spinner.stop()

    def do_add(self, arg):
        logger = logging.getLogger(__name__)
        try:
            if not self.migration:
                print('no migration defined')
                return

            ops = [x for x in self.migration.operations if fnmatch(str(x), arg) and x not in self.stage]

            for op in ops:
                self.stage.append(op)
                print(colored('Add: {}'.format(op), 'green'))

            self.stage = sorted(self.stage, key=lambda x: x.type)
        except Exception:
            print('Error occurred:', '\n', traceback.format_exc())
            logger.exception('Error occurred')

    def do_rm(self, arg):
        logger = logging.getLogger(__name__)
        try:
            if not self.migration:
                print('no migration defined')
                return

            ops = [x for x in self.stage if fnmatch(str(x), arg)]

            for op in ops:
                self.stage.remove(op)
                print(colored('Remove: {}'.format(op), 'red'))

            self.stage = sorted(self.stage, key=lambda x: x.type)
        except Exception:
            print('Error occurred:', '\n', traceback.format_exc())
            logger.exception('Error occurred')

    def do_gui(self, arg):
        logger = logging.getLogger(__name__)
        if not self.migration:
            print('no migration')
            return
        try:
            exe = '/usr/local/bin/github'
            print(self.migration.path)
            subprocess.run([exe, self.migration.path], check=True)
        except Exception:
            print('Error. You may need to install github command line tools from the github desktop application')
            logger.exception('Error running github gui')


class Spinner:
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in '|/-\\':
                yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay):
            self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def start(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def stop(self):
        self.busy = False
        time.sleep(self.delay)
