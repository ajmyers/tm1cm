import copy
import datetime
import logging

from tm1cm import tm1 as tm1_client
from tm1cm.types.base import Base


class Chore(Base):

    def __init__(self, config, app=None):
        self.type = 'chore'
        super().__init__(config, app)

    def _list_remote(self, app):
        chores = app.session.client.chores.list(tm1_client.names_query())

        return sorted([chore.name for chore in chores])

    @staticmethod
    def _normalize_start_time(start_time):
        """A chore's StartTime as a UTC instant, written the same whatever server it came from.

        TM1 returns StartTime in the server's time zone ('2022-02-13T12:00-08:00' on one server,
        '2022-02-13T20:00Z' on another, for the same instant), so storing it as given would make
        every chore differ between servers in different zones.
        """
        if not start_time:
            return start_time

        parsed = datetime.datetime.fromisoformat(start_time)
        if parsed.tzinfo is None:
            return start_time

        return parsed.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')

    def _get_remote(self, app, items):
        query = tm1_client.ODataQuery.of(None, select='Name,Active,StartTime,DSTSensitive,ExecutionMode,Frequency,Tasks',
                                         expand='Tasks($expand=Process($select=Name))')

        results = tm1_client.filtered(app.session.client.chores.list, query, items)
        results = {result['Name']: result for result in tm1_client.odata(results)}
        results = [(item, results[item]) for item in items]

        for name, item in results:
            yield name, self._transform_from_remote(name, item)

    def _update_remote(self, app, name, item):
        session = app.session

        item = self._transform_to_remote(name, item)

        tm1_client.create_or_update_chore(session, item)

    def _delete_remote(self, app, name):
        session = app.session

        if tm1_client.chore_exists(session, name):
            session.client.chores.delete(name)

    def _transform_from_local(self, name, item):
        item = copy.deepcopy(item)
        if item is None:
            item = {}
        item['Name'] = name
        if 'StartTime' in item:
            item['StartTime'] = self._normalize_start_time(item['StartTime'])
        if 'Frequency' in item:
            # As the services read it (PT24H): files written before them hold TM1's P01DT00H00M00S
            item['Frequency'] = tm1_client.normalize_frequency(item['Frequency'])
        for step, task in enumerate(item['Tasks']):
            task['Step'] = step
            task['Process'] = {'Name': task['Process']}

        return item

    def _transform_from_remote(self, name, item):
        item = super()._transform_from_remote(name, item)
        if 'StartTime' in item:
            item = {**item, 'StartTime': self._normalize_start_time(item['StartTime'])}

        return item

    def _transform_to_local(self, name, item):
        item = copy.deepcopy(item)
        del item['Name']
        for task in item['Tasks']:
            del task['Step']
            task['Process'] = task['Process']['Name']

        return item

    def _transform_to_remote(self, name, item):
        item = copy.deepcopy(item)
        if item.get('StartTime'):
            # TM1 wants seconds and a numeric offset: 2022-02-13T20:00:00+00:00
            start_time = datetime.datetime.fromisoformat(item['StartTime'])
            item['StartTime'] = start_time.isoformat(timespec='seconds')

        return item


logger = logging.getLogger(Chore.__name__)
