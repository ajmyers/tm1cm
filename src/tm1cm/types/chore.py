import copy
import json
import logging
import urllib.parse

from TM1py.Objects.Chore import Chore as TM1PyChore

from tm1cm.types.base import Base


class Chore(Base):

    def __init__(self, config, app=None):
        self.type = 'chore'
        super().__init__(config, app)

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Chores?$select=Name'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    def _get_remote(self, app, items):
        filter = ['Name eq \'' + urllib.parse.quote(item, safe='') + '\'' for item in items]
        request = '/api/v1/Chores?$select=Name,Active,StartTime,DSTSensitive,ExecutionMode,Frequency,Tasks&$expand=Tasks($expand=Process($select=Name))&$filter='

        results = self._do_filter_request(app, request, filter)
        results = {result['Name']: result for result in results}
        results = [(item, results[item]) for item in items]

        for name, item in results:
            yield name, self._transform_from_remote(name, item)

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        chore = TM1PyChore.from_dict(item)
        session.chores.update_or_create(chore)

    def _delete_remote(self, app, name):
        session = app.session

        if session.chores.exists(name):
            session.chores.delete(name)

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        if item is None:
            item = {}
        item['Name'] = name
        for step, task in enumerate(item['Tasks']):
            task['Step'] = step
            task['Process'] = {'Name': task['Process']}

        return item

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']
        for task in item['Tasks']:
            del task['Step']
            task['Process'] = task['Process']['Name']

        return item


logger = logging.getLogger(Chore.__name__)
