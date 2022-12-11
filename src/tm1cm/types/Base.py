import json
import os
from glob import iglob

import yaml

from tm1cm.application import RemoteApplication
from tm1cm.common import Dumper
from tm1cm.common import filter_list


class Base:

    def __init__(self, config):
        self.config = config

        self.include = self.config.get('include_' + self.type, '*')
        self.exclude = self.config.get('exclude_' + self.type, '')

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

    def update(self, app, name, item):
        func = self._update_remote if isinstance(app, RemoteApplication) else self._update_local
        func(app, name, item)

    def delete(self, app, name):
        func = self._delete_remote if isinstance(app, RemoteApplication) else self._delete_local
        func(app, name)

    def _list_local(self, app):
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        path = app.path
        path = os.path.join(path, self.config.get(self.type + '_path', 'data' + os.sep + self.type))

        full_path = os.path.join(path, '**', '*' + ext)

        items = [fn for fn in iglob(full_path, recursive=True) if os.path.isfile(fn)]
        items = [item[len(path) + 1:-len(ext)] for item in items]
        items = [tuple(item.split(os.sep)) if os.sep in item else item for item in items]
        items = sorted(items)

        return items

    def _get_local(self, app, items):
        file_format = self.config.get('text_output_format', 'YAML').upper()
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        files = [os.sep.join(item) if not isinstance(item, str) else item for item in items]
        files = [os.path.join(app.path, self.config.get(self.type + '_path', 'data' + os.sep + self.type), file + ext) for file in files]

        results = []
        for file in files:
            with open(file, 'rb') as fp:
                if file_format == 'YAML':
                    results.append(yaml.safe_load(fp))
                else:
                    results.append(json.safe_load(fp, indent=4, sort_keys=True, ensure_ascii=False))

        return [(name, self._transform_from_local(name, item)) for name, item in zip(items, results)]

    def _filter_local(self, items):
        return filter_list(items, self.include, self.exclude, name_func=self._filter_name_func)

    def _filter_remote(self, items):
        return self._filter_local(items)

    def _update_local(self, app, name, item):
        file_format = self.config.get('text_output_format', 'YAML').upper()
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        path = self.config.get(self.type + '_path', 'data' + os.sep + self.type)
        path = os.path.join(app.path, path, os.sep.join(name) + ext if not isinstance(name, str) else name + ext)

        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(name, item)

        with open(path, 'w') as fp:
            if file_format == 'YAML':
                text = yaml.dump(item, Dumper=Dumper, width=255, sort_keys=False)
            else:
                text = json.dumps(item, indent=4, sort_keys=False, ensure_ascii=False)

            fp.write(text)

    def _delete_local(self, app, name):
        ext = self.config.get(self.type + '_ext', '.' + self.type)

        path = self.config.get(self.type + '_path', 'data' + os.sep + self.type)
        path = os.path.join(app.path, path, name + ext)

        if os.path.exists(path):
            os.remove(path)

    def _transform_from_remote(self, name, item):
        return item

    def _transform_to_remote(self, name, item):
        return item

    def _transform_from_local(self, name, item):
        return item

    def _transform_to_local(self, name, item):
        return item

    def _filter_name_func(self, item, extra):
        return item if isinstance(item, str) else '/'.join(item)
