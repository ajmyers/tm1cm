import copy
import json
import logging

from tm1cm.types.Base import Base


class Chore(Base):

    def __init__(self, config):
        self.type = 'chore'
        super().__init__(config)

    # def _list_local(self, app):
    #     pass

    def _list_remote(self, app):
        rest = app.session._tm1_rest

        request = '/api/v1/Chores?$select=Name'
        response = rest.GET(request)
        results = json.loads(response.text)['value']

        return sorted([result['Name'] for result in results])

    # def _get_local(self, app, items):
    #     pass

    def _get_remote(self, app, items):
        if items is None:
            return []

        rest = app.session._tm1_rest

        filter = 'or '.join(['Name eq \'' + item + '\'' for item in items])
        request = '/api/v1/Chores?$select=Name,StartTime,DSTSensitive,ExecutionMode,Frequency,Tasks&$expand=Tasks($expand=Process($select=Name))&$filter=' + filter

        response = rest.GET(request)
        results = json.loads(response.text)['value']
        results = {result['Name']: result for result in results}
        results = [(item, results[item]) for item in items]

        return [(name, self._transform_from_remote(name, item)) for name, item in results]

    # def _filter_local(self, items):
    #     pass

    def _filter_remote(self, items):
        return self._filter_local(items)

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        try:
            if not session.chores.exists(name):
                request = '/api/v1/Chores'
                session._tm1_rest.POST(url=request, data=json.dumps(item))
            else:
                request = '/api/v1/Chores(\'{}\')'.format(name)
                session._tm1_rest.PATCH(url=request, data=json.dumps(item))

        except Exception:
            logger.exception(f'Encountered error while updating chore {name}')
            raise

    # def _update_local(self, app, name, item):
    #     pass

    def _delete_remote(self, app, name, item):
        session = app.session

        try:
            if session.chores.exists(name):
                session.chores.delete(name)
        except Exception:
            logger.exception(f'Encountered error while deleting chore {name}')

    def _transform_to_remote(self, name, item):
        for task in item['Tasks']:
            task['Process@odata.bind'] = 'Processes(\'{}\')'.format(task['Process']['Name'])
            del task['Process']

        return item

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
    # def _delete_local(self, app, name, item):
    #     pass


logger = logging.getLogger(Chore.__name__)
