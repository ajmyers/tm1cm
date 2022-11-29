import json
import os
from glob import iglob

import yaml

from tm1cm.__main__ import setup_logger
from tm1cm.application import RemoteApplication
from tm1cm.common import filter_list, Dumper


class Base:

    def __init__(self, config):
        self.config = config
        setup_logger(None, None, True, True, False)

    def list(self, app):
        func = self._list_remote if isinstance(app, RemoteApplication) else self._list_local
        items = func(app)
        return self.filter(app, items)

    def get(self, app, items):
        func = self._get_remote if isinstance(app, RemoteApplication) else self._get_local
        return func(app, items)

    def filter(self, app, items):
        func = self._filter_remote if isinstance(app, RemoteApplication) else self._filter_local
        return func(items)

    def update(self, app, item):
        func = self._update_remote if isinstance(app, RemoteApplication) else self._update_local
        func(app, item)

    def delete(self, app, item):
        func = self._delete_remote if isinstance(app, RemoteApplication) else self._delete_local
        func(app, item)

    def _filter_local(self, items):
        include = self.config.get('include_' + self.type, '*')
        exclude = self.config.get('exclude_' + self.type, '')

        return filter_list(items, include, exclude, name_func=lambda x, extra: x)

    def _list_local(self, app):
        ext = self.config.get(self.type + '_ext', self.type)

        path = app.path
        path = os.path.join(path, self.config.get(self.type + '_path', 'data/' + self.type), '*' + ext)

        return sorted([os.path.basename(os.path.splitext(fn)[0]) for fn in iglob(path)])

    def _get_local(self, app, items):
        file_format = self.config.get('text_output_format', 'YAML').upper()
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        items = [os.path.join(app.path, self.config.get(self.type + '_path', 'data/' + self.type), item + ext) for item in items]

        results = []
        for item in items:
            with open(item, 'r') as fp:
                if file_format == 'YAML':
                    results.append(yaml.safe_load(fp))
                else:
                    results.append(json.safe_load(fp, indent=4, sort_keys=True, ensure_ascii=False))

        return [self._transform_from_local(result) for result in results]

    def _update_local(self, app, item):
        file_format = self.config.get('text_output_format', 'YAML').upper()
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        path = self.config.get(self.type + '_path', 'data/' + self.type)
        path = os.path.join(app.path, path, item['Name'] + ext)

        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(item)

        with open(path, 'w') as fp:
            if file_format == 'YAML':
                text = yaml.dump(item, Dumper=Dumper, width=255)
            else:
                text = json.dumps(item, indent=4, sort_keys=True, ensure_ascii=False)

            fp.write(text)

    def _delete_local(self, _, item):
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        path = self.config.get(self.type + '_path', 'data/' + self.type)
        path = os.path.join(path, item['Name'] + ext)

        if os.path.exists(path):
            os.remove(path)

    def _transform_from_remote(self, item):
        return item

    def _transform_to_remote(self, item):
        return item

    def _transform_from_local(self, item):
        return item

    def _transform_to_local(self, item):
        return item
