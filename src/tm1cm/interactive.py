import cmd
import logging
import os
import subprocess
import sys
import threading
import time
from fnmatch import fnmatch

from termcolor import colored

from tm1cm import errors
from tm1cm import tm1 as tm1_client
from tm1cm.application import LocalApplication
from tm1cm.application import RemoteApplication
from tm1cm.common import get_config
from tm1cm.migration import Migration
from tm1cm.operation import Operation


class Interactive(cmd.Cmd):

    def __init__(self, path=None, overrides=None):
        self.intro = 'Welcome to TM1 Code Migrate interactive!\n'
        self.prompt = '(tm1cm) $ '
        self.migration = None
        self.apps = {}
        self.stage = []
        self.operations = []
        # Connection settings from --connect, over every environment's own
        self.overrides = overrides or {}

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
                    logger.info('Adding local app: {}'.format(app_name))
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

    def onecmd(self, line):
        """Runs one command. An error ends the command, not the shell: its message is shown, its
        full report goes to the log, and the shell carries on."""
        try:
            return super().onecmd(line)
        except KeyboardInterrupt:
            print('Cancelled.')
        except Exception as e:
            errors.handle(e, stream=sys.stdout)
        return False

    def emptyline(self):
        # Not cmd's default, which repeats the last command: an Enter must not run "do" again
        return False

    def do_path(self, args):
        """Adds a project or collection or projects at the specified path"""
        self.config_apps_from_path(args)
        self.do_ls('app')

    def add_local_path(self, name, path):
        config = get_config(path, 'tm1cm', None)
        self.apps[name] = LocalApplication(config, path)

    def add_path(self, name, path, environment):
        config = get_config(path, 'tm1cm', environment)
        credentials = get_config(path, 'credentials', environment)
        connect = get_config(path, 'connect', environment)

        session_config = {**connect, **credentials, **self.overrides}

        self.apps[name] = RemoteApplication(config, session_config=session_config)

    def _app(self, name):
        if name not in self.apps:
            raise errors.ConfigError(f'There is no app {name}.', f'Apps: {", ".join(sorted(self.apps)) or "none"}. "ls apps" lists them.')
        return self.apps[name]

    def do_do(self, arg):
        """Execute the currently staged operations. Optionally, specify 'all'
        to run all operations bypassing the staging process"""
        if not self.migration:
            print('no migration defined')
            return
        if arg == 'all':
            ops = self.operations
            message = 'Perform ALL operations? ({}/{})'.format(len(ops), len(ops))
        else:
            ops = self.stage
            message = 'Perform STAGED operations? ({}/{})'.format(len(ops), len(self.operations))

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
                    try:
                        with errors.doing(f'running the backup process {backup_process}'):
                            tm1_client.execute_process(self.migration.target.session, backup_process)
                    finally:
                        spinner.stop()

            for op in ops:
                print(colored('Doing: {}'.format(str(op)), 'green'))
                spinner.start()
                try:
                    with errors.doing(f'performing {op}'):
                        op.do()
                finally:
                    spinner.stop()

    def do_ls(self, arg):
        if not arg:
            arg = 'operations'
        if arg in ['app', 'apps', 'applications']:
            for app, _ in self.apps.items():
                print(app)
        if arg in ['migration', 'operations']:
            if self.migration:
                for op in self.operations:
                    color = 'green' if op in self.stage else 'red'
                    print(colored(op, color))
        if arg in ['stage']:
            for op in self.stage:
                print(colored(op, 'green'))

    def do_migrate(self, args):
        self.stage = []
        try:
            app_from, app_to = args.split(' ', maxsplit=2)
        except ValueError:
            raise errors.ConfigError('migrate takes two apps: migrate <from> <to>.', '"ls apps" lists them.') from None
        app_from = self._app(app_from)
        app_to = self._app(app_to)

        # Before the spinner: logging in may ask for a password, or open a browser window
        for app in (app_from, app_to):
            if isinstance(app, RemoteApplication):
                app.connect()

        spinner = Spinner()
        spinner.start()
        try:
            with errors.doing('working out the migration'):
                self.migration = Migration(app_from, app_to)
                self.operations = self.migration.operations
        finally:
            spinner.stop()

    def do_add(self, arg):
        if not self.migration:
            print('no migration defined')
            return

        ops = [x for x in self.operations if fnmatch(str(x), arg) and x not in self.stage]

        for op in ops:
            self.stage.append(op)
            print(colored('Add: {}'.format(op), 'green'))

        self.stage = Operation.sort(self.stage)

    def do_rm(self, arg):
        if not self.migration:
            print('no migration defined')
            return

        ops = [x for x in self.stage if fnmatch(str(x), arg)]

        for op in ops:
            self.stage.remove(op)
            print(colored('Remove: {}'.format(op), 'red'))

        self.stage = Operation.sort(self.stage)

    def do_gui(self, arg):
        logger = logging.getLogger(__name__)
        if not self.migration:
            print('no migration')
            return
        try:
            exe = '/usr/local/bin/github'
            print(self.migration.stage.path)
            subprocess.run([exe, self.migration.stage.path], check=True)
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
