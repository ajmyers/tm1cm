import tempfile

from TM1py.Services import TM1Service
from git import Repo

from tm1cm.types.application import Application as _Application
from tm1cm.types.chore import Chore
from tm1cm.types.cube import Cube
from tm1cm.types.dimension import Dimension
from tm1cm.types.hierarchy import Hierarchy
from tm1cm.types.process import Process
from tm1cm.types.rule import Rule
from tm1cm.types.subset import Subset
from tm1cm.types.view import View
from tm1cm.types.view_data import ViewData


class Application:
    def __init__(self, config):
        self.config = config

        self._application = _Application(config, self)
        self._chore = Chore(config, self)
        self._cube = Cube(config, self)
        self._dimension = Dimension(config, self)
        self._hierarchy = Hierarchy(config, self)
        self._process = Process(config, self)
        self._rule = Rule(config, self)
        self._subset = Subset(config, self)
        self._view = View(config, self)
        self._view_data = ViewData(config, self)

    @property
    def applications(self):
        return self._application

    @property
    def chores(self):
        return self._chore

    @property
    def cubes(self):
        return self._cube

    @property
    def dimensions(self):
        return self._dimension

    @property
    def hierarchies(self):
        return self._hierarchy

    @property
    def processes(self):
        return self._process

    @property
    def rules(self):
        return self._rule

    @property
    def subsets(self):
        return self._subset

    @property
    def views(self):
        return self._view

    @property
    def views_data(self):
        return self._view_data

    @property
    def scopes(self):
        return [self._application, self._chore, self._cube, self._dimension, self._hierarchy, self._process, self._rule, self._subset, self._view, self._view_data]


class RemoteApplication(Application):
    def __init__(self, config, session=None, session_config=None):
        if session:
            self._connected = True
            self._address = session._tm1_rest._address
            self._address = session._tm1_rest._port
            self._session = session
            # self._update_config()
        else:
            self._connected = False
            self._base_url = session_config.get('base_url', '')
            self._address = session_config.get('address', '')
            self._port = session_config.get('port', '')
            self._session_config = session_config

        super().__init__(config)

    def __str__(self):
        return 'url={} connected={}'.format(self._base_url, self._connected)

    def __repr__(self):
        return '<RemoteApplication ({})>'.format(self.__str__())

    def __del__(self):
        try:
            self._session.logout()
        except Exception:
            pass

    @property
    def session(self):
        self.connect()
        return self._session

    def connect(self, session_config=None):
        if session_config:
            self._session_config = session_config

        if not self._connected:
            self._session = TM1Service(**self._session_config)
            self._connected = True


class LocalApplication(Application):
    def __init__(self, config, path):
        self.path = path

        super().__init__(config)

        self.repo = Repo.init(self.path)

    def commit_changes(self):
        pass


class TemporaryApplication(LocalApplication):
    def __init__(self, config):
        path = tempfile.mkdtemp(prefix='tm1cm_')
        super().__init__(config, path)
