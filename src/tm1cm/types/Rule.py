import json
import logging
import os

from TM1py.Objects.Rules import Rules as TM1PyRules

from tm1cm.types.base import Base


class Rule(Base):

    def __init__(self, config):
        self.type = 'rule'
        super().__init__(config)

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
                results.append(fp.read())

        return [(name, self._transform_from_local(name, item)) for name, item in zip(items, results)]

    def _get_remote(self, app, items):
        if items is None:
            return []

        rest = app.session._tm1_rest

        filter = 'or '.join(['Name eq \'' + item + '\'' for item in items])
        request = '/api/v1/Cubes?$select=Name,Rules&$filter=' + filter

        response = rest.GET(request)
        results = json.loads(response.text)['value']
        results = {result['Name']: result for result in results}
        results = [(item, results[item]['Rules']) for item in items]

        return [(name, self._transform_from_remote(name, result)) for name, result in results]

    def _update_local(self, app, name, item):
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        path = self.config.get(self.type + '_path', 'data/' + self.type)
        path = os.path.join(app.path, path, name + ext)

        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(name, item)

        with open(path, 'w') as fp:
            fp.write(item)

    def _update_remote(self, app, name, item):
        session = app.session
        item = self._transform_to_remote(name, item)

        try:
            if session.cubes.exists(name):
                cube = session.cubes.get(name)
                cube.rules = TM1PyRules(item)
                session.cubes.update(cube)
            else:
                logger.error('Unable to update cube rule because cube {} does not exist'.format(name))
        except Exception:
            logger.exception('Encountered error while updating rule in cube {}'.format(name))

    def _delete_remote(self, app, name, item):
        session = app.session

        try:
            if session.cubes.exists(name):
                empty_rule = TM1PyRules('')
                cube = session.cubes.get(name)
                cube.rules = empty_rule
                session.cubes.update(cube)
                logger.info('Removed rule from cube {}'.format(name))
            else:
                logger.error('Unable to delete rule because cube {} does not exist'.format(name))
        except Exception:
            logger.exception('Encountered error while deleting cube {}'.format(name))
            raise

    def _transform_from_remote(self, name, item):
        if not item:
            return ''
        else:
            return item


logger = logging.getLogger(Rule.__name__)
