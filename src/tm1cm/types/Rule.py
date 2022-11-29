
import copy
import json
import logging
import os

from urllib.parse import quote

from tm1cm.application import RemoteApplication
from tm1cm.types.Base import Base
from tm1cm.common import filter_list

from TM1py.Objects.Rules import Rules as TM1PyRules


class Rule(Base):

    def __init__(self, config):
        self.type = 'rule'
        super().__init__(config)

    # def _list_local(self, app):
    #     pass

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Cubes?$select=Name&$filter=Rules ne null'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    def _get_local(self, app, items):
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        files = [os.path.join(app.path, self.config.get(self.type + '_path', 'data/' + self.type), item + ext) for item in items]

        results = []
        for file, item in zip(files, items):
            with open(file, 'r') as fp:
                results.append((item, fp.read()))

        return [self._transform_from_local(result) for result in results]

    def _get_remote(self, app, items):
        if items is None:
            return []

        rest = app.session._tm1_rest

        filter = 'or '.join(['Name eq \'' + item + '\'' for item in items])
        request = '/api/v1/Cubes?$select=Name,Rules&$filter=' + filter

        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return [(result['Name'], self._transform_from_remote(result['Rules'])) for result in results]

    # def _filter_local(self, items):
    #     pass

    def _filter_remote(self, items):
        return self._filter_local(items)

    def _update_local(self, app, item):
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        path = self.config.get(self.type + '_path', 'data/' + self.type)
        path = os.path.join(app.path, path, item[0] + ext)

        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(item)

        with open(path, 'w') as fp:
            fp.write(item[1])

    def _update_remote(self, app, item):
        session = app.session
        item = self._transform_to_remote(item)

        cube_name = item[0]

        try:
            if session.cubes.exists(cube_name):
                cube = session.cubes.get(cube_name)
                cube.rules = TM1PyRules(item[1])
                session.cubes.update(cube)
            else:
                logger.error('Unable to update cube rule because cube {} does not exist'.format(cube_name))
        except Exception:
            logger.exception('Encountered error while updating rule in cube {}'.format(cube_name))

    # def _update_local(self, app, item):
    #     pass

    def _delete_remote(self, app, item):
        session = app.session

        try:
            if session.cubes.exists(cube_name):
                empty_rule = TM1PyRules('')
                cube = session.cubes.get(cube_name)
                cube.rules = empty_rule
                session.cubes.update(cube)
                logger.info('Removed rule from cube {}'.format(cube_name))
            else:
                logger.error('Unable to delete rule because cube {} does not exist'.format(cube_name))
        except Exception:
            logger.exception('Encountered error while deleting cube {}'.format(cube_name))
            raise

    # def _delete_local(self, app, item):
    #     pass

    def _transform_from_remote(self, item):
        if not item:
            return ''
        else:
            return item

logger = logging.getLogger(Rule.__name__)