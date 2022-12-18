import contextlib
import json
import logging
import os
from glob import iglob

import git
import yaml

from tm1cm.common import Dumper
from tm1cm.common import filter_list


class Base:

    def __init__(self, config, app):
        self.config = config
        self.app = app

        self.include = self.config.get('include_' + self.type, '*')
        self.exclude = self.config.get('exclude_' + self.type, '')

        self.file_format = self.config.get('text_output_format', 'YAML').upper()
        self.ext = self.config.get(self.type + '_ext', '.' + self.type)

        self.path = self.config.get(self.type + '_path', 'data' + os.sep + self.type)
        self.path = os.path.normpath(self.path)

    def list(self, app=None):
        if not app:
            app = self.app
        func = self._list_remote if type(app).__name__ == 'RemoteApplication' else self._list_local
        items = func(app)
        return self.filter(items, app)

    def get(self, items, app=None):
        if not app:
            app = self.app
        if not items:
            return
        func = self._get_remote if type(app).__name__ == 'RemoteApplication' else self._get_local
        for result in func(app, items):
            if result[1]:
                yield result

    def filter(self, items, app=None):
        if not app:
            app = self.app
        func = self._filter_remote if type(app).__name__ == 'RemoteApplication' else self._filter_local
        return func(items)

    def update(self, name, item, app=None):
        if not app:
            app = self.app
        func = self._update_remote if type(app).__name__ == 'RemoteApplication' else self._update_local
        func(app, name, item)

    def delete(self, name, app=None):
        if not app:
            app = self.app
        func = self._delete_remote if type(app).__name__ == 'RemoteApplication' else self._delete_local
        func(app, name)

    def _list_local(self, app):
        path = app.path
        path = os.path.join(path, self.path)

        full_path = os.path.join(path, '**', '*' + self.ext)

        items = [fn for fn in iglob(full_path, recursive=True) if os.path.isfile(fn)]
        items = [item[len(path) + 1:-len(self.ext)] for item in items]
        items = [tuple(item.split(os.sep)) if os.sep in item else item for item in items]
        items = sorted(items)

        return items

    def _get_local(self, app, items):

        files = [os.sep.join(item) if not isinstance(item, str) else item for item in items]
        files = [os.path.join(app.path, self.path, file + self.ext) for file in files]

        for item, file in zip(items, files):
            with open(file, 'rb') as fp:
                if self.file_format == 'YAML':
                    result = yaml.safe_load(fp)
                else:
                    result = json.safe_load(fp, indent=4, sort_keys=True, ensure_ascii=False)

            yield item, self._transform_from_local(item, result)

    def _filter_local(self, items):
        return filter_list(items, self.include, self.exclude, name_func=self._filter_name_func)

    def _filter_remote(self, items):
        return self._filter_local(items)

    def _update_local(self, app, name, item):
        path = os.path.join(app.path, self.path, os.sep.join(name) + self.ext if not isinstance(name, str) else name + self.ext)
        os.makedirs(os.path.split(path)[0], exist_ok=True)

        item = self._transform_to_local(name, item)

        with open(path, 'w') as fp:
            if self.file_format == 'YAML':
                text = yaml.dump(item, Dumper=Dumper, width=255, sort_keys=True)
            else:
                text = json.dumps(item, indent=4, sort_keys=True, ensure_ascii=False)

            fp.write(text)

    def _delete_local(self, app, name):
        path = os.sep.join(name) if not isinstance(name, str) else name
        path = os.path.join(self.path, path + self.ext)
        full_path = os.path.join(app.path, path)
        if os.path.exists(full_path):
            with contextlib.suppress(git.exc.GitCommandError):
                app.repo.git.rm(path)
            with contextlib.suppress(OSError):
                os.remove(full_path)

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

    @staticmethod
    def _do_filter_request(app, request, filter):
        request_text = None
        for f in filter:
            if not request_text:
                request_text = request + f

            if len(request_text + ' or ' + f) > 6000:
                response = app.session._tm1_rest.GET(request_text)
                response = json.loads(response.text)['value']
                for item in response:
                    yield item

                request_text = request + f
            else:
                request_text = request_text + ' or ' + f

        if request_text:
            response = app.session._tm1_rest.GET(request_text)
            response = json.loads(response.text)['value']
            for item in response:
                yield item


logger = logging.getLogger(Base.__name__)
