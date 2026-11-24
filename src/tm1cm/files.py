"""get and put of the objects named by files, rather than of everything tm1cm.yaml selects.

Each path names one object by where its file is in the project: data/process/Load.process is the
process Load, data/hierarchy/Region/Region.hierarchy the hierarchy Region of dimension Region.
Only those objects are got or put, and the object filters of tm1cm.yaml (include_process,
exclude_cube...) are not applied: the files say which objects. The filters that shape what an
object's file holds (the elements, edges, attributes and attribute values of a hierarchy) still
apply, as they did when the file was written, so a put never sends what a get left out.

A file that's there is the object as it should be. A file that isn't names an object to delete:

- put: the file is updated to TM1, or, when it's gone, the object is deleted from TM1;
- get: the object is written to its file, or, when TM1 hasn't got it, its file is deleted.

So the files a commit changed, deleted ones included (git diff --name-only), put exactly that
commit.
"""
import logging
import os

from tm1cm.errors import ConfigError
from tm1cm.operation import Operation

logger = logging.getLogger(__name__)

# How many parts each type's names have (dimension/hierarchy/subset...): files deeper or
# shallower in a type's folder aren't one of its objects. Applications nest in folders.
DEPTH = {'hierarchy': 2, 'subset': 3, 'view': 2, 'view_data': 2}


def resolve(path, project):
    """The path as a full path inside the project. A relative path is taken from the current
    folder when that's in the project and the file is there, else from the project (as git
    prints them), so files deleted since are found either way."""
    project = os.path.abspath(project)

    def inside(candidate):
        return candidate.startswith(project + os.sep)

    if os.path.isabs(path):
        candidates = [os.path.normpath(path)]
    else:
        here, there = os.path.abspath(path), os.path.normpath(os.path.join(project, path))
        candidates = [here, there] if inside(here) and os.path.exists(here) else [there, here]
    for candidate in candidates:
        if inside(candidate):
            return candidate
    raise ConfigError(f'{path} is not in the project at {project}.', 'Give files inside the project, relative to it or to the current folder.')


def _scope_of(full_path, local):
    for scope in local.scopes:
        root = os.path.join(local.path, scope.path)
        if full_path.startswith(root + os.sep):
            return scope, full_path[len(root) + 1:]
    folders = ', '.join(sorted(scope.path.replace(os.sep, '/') for scope in local.scopes))
    raise ConfigError(f'{os.path.relpath(full_path, local.path)} is not an object file: objects are in {folders}.')


class Names:
    """The objects of a type each side has, by name, unfiltered; listed once, when first asked."""

    def __init__(self):
        self._names = {}

    def of(self, scope, app):
        key = (scope.type, id(app))
        if key not in self._names:
            self._names[key] = list(scope._list_remote(app) if type(app).__name__ == 'RemoteApplication' else scope._list_local(app))
        return self._names[key]


def object_of(full_path, local, remote, names):
    """(scope, name) of the object a file stands for, or (scope, None) for a reference that
    neither side has. The scope is the local application's."""
    scope, inside = _scope_of(full_path, local)
    shown = os.path.relpath(full_path, local.path)

    if scope.type == 'application':
        root = os.path.join(local.path, scope.path)
        if not inside.endswith(scope.ext):
            # A document: any other file in the folder, as it is
            return scope, (*inside.split(os.sep), 'blob')
        parts = tuple(inside[:-len(scope.ext)].split(os.sep))
        if os.path.isfile(full_path):
            folder_name, suffix = scope.transform_type(root, inside)
            return scope, (*folder_name.split(os.sep), suffix)
        # Gone from the project: which kind of reference it was, TM1 says
        for name in names.of(scope, remote):
            if tuple(name[:-1]) == parts and name[-1] != 'blob':
                return scope, tuple(name)
        return scope, None

    return scope, _name(scope, inside, shown)


def _name(scope, inside, shown):
    if not inside.endswith(scope.ext):
        raise ConfigError(f'{shown} is not a {scope.type} file: they end in {scope.ext}.')
    parts = inside[:-len(scope.ext)].split(os.sep)
    depth = DEPTH.get(scope.type, 1)
    if len(parts) != depth:
        example = '/'.join(['<name>'] * depth) + scope.ext
        raise ConfigError(f'{shown} is not a {scope.type} file: they are {scope.path.replace(os.sep, "/")}/{example}.')
    return parts[0] if depth == 1 else tuple(parts)


def check(paths, local):
    """Refuses a path that isn't an object file of the project, before anything is asked of TM1."""
    for path in paths:
        full_path = resolve(path, local.path)
        scope, inside = _scope_of(full_path, local)
        if scope.type != 'application':
            _name(scope, inside, os.path.relpath(full_path, local.path))


def _folded(name):
    return name.casefold() if isinstance(name, str) else tuple(part.casefold() for part in name)


def _has(names, name):
    """Whether TM1 has the object: its names ignore case."""
    return name in names or any(_folded(n) == _folded(name) for n in names)


def operations(mode, local, remote, paths, names=None):
    """The operations that get or put the objects the files name, in dependency order. A file
    naming an object neither side has is skipped, with a message in the log. ``names`` lists what
    TM1 has (a :class:`Names`, by default)."""
    names = names or Names()
    target = remote if mode == 'put' else local
    planned = []
    seen = set()
    for path in paths:
        full_path = resolve(path, local.path)
        scope, name = object_of(full_path, local, remote, names)
        if (scope.type, name) in seen:
            continue
        seen.add((scope.type, name))
        in_project = os.path.isfile(full_path)
        in_tm1 = name is not None and _has(names.of(scope, remote), name)
        if mode == 'put':
            source_scope = scope
            operation = 'UPDATE' if in_project else 'DELETE' if in_tm1 else None
        else:
            source_scope = next(s for s in remote.scopes if s.type == scope.type)
            operation = 'UPDATE' if in_tm1 else 'DELETE' if in_project else None
        if operation is None:
            logger.info(f'Skipping {path}: neither the project nor TM1 has that {scope.type}')
            continue
        planned.append(Operation(target, source_scope, operation, name))
    return Operation.sort(planned)
