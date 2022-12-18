import contextlib
import os
from shutil import rmtree

import git

from tm1cm.application import TemporaryApplication
from tm1cm.operation import Operation

AUTHOR = 'tm1cm <tm1cm@local>'


class Migration:
    def __init__(self, source, target):
        self._source = source
        self._target = target

        self._stage = TemporaryApplication(self._target.config)

        self.refresh()

    @property
    def source(self):
        return self._source

    @property
    def target(self):
        return self._target

    @property
    def stage(self):
        return self._stage

    @property
    def operations(self):
        commits = list(self._stage.repo.iter_commits())
        source_commit = commits[0]
        target_commit = commits[1]

        operations = []
        for diff in target_commit.diff(source_commit):
            change_type = diff.change_type[:1]

            scope_a = self._get_scope_from_path(diff.a_path)
            scope_b = self._get_scope_from_path(diff.b_path)

            if scope_a is not scope_b:
                raise Exception('Encountered different scope between a + b file diff')

            scope = scope_a

            operation = 'DELETE' if change_type == 'D' else 'UPDATE'
            operations.append(self._get_operation(scope, operation, diff))

            if change_type == 'R':
                operation = 'DELETE'
                operations.append(self._get_operation(scope, operation, diff))

        return Operation.sort(operations)

    def refresh(self):
        for step in [self._target, self._source]:
            if step:
                for scope in sorted(step.scopes, key=lambda x: Operation.Order[x.type]):
                    with contextlib.suppress(git.exc.GitCommandError):
                        self._stage.repo.git.rm('-r', scope.path)
                    with contextlib.suppress(OSError):
                        rmtree(os.path.join(self._stage.path, scope.path), ignore_errors=True)

                    lst = scope.list()
                    items = scope.get(lst)
                    for name, item in items:
                        scope.update(name, item, self._stage)
                with contextlib.suppress(git.exc.GitCommandError):
                    self._stage.repo.git.add('*')

            self._stage.repo.git.commit('--allow-empty', '-m', 'initial', author=AUTHOR)

    def _get_scope_from_path(self, path):
        for scope in self._stage.scopes:
            scope_path = scope.path

            if path.startswith(scope_path + os.sep):
                return scope

        raise Exception(f'Could not determine scope from {path}')

    def _get_operation(self, scope, operation, diff):
        path = diff.b_path.split(os.sep)
        path = path[len(scope.path.split(os.sep)):]

        if scope.type == 'application':
            blob = diff.a_blob if operation == 'DELETE' else diff.b_blob
            name = scope.transform_type(os.path.join(self._stage.path, scope.path), os.sep.join(path), blob)
            name = *name[0].split(os.sep), name[1]
        else:
            name = *path[:-1], path[-1].rsplit('.', 1)[0]
            name = ''.join(name) if len(name) == 1 else name

        return Operation(self.target, scope, operation, name)
