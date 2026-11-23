from enum import IntEnum
from enum import auto


class Operation:

    def __init__(self, target, scope, operation, name):
        self._target = target
        self._scope = scope
        self._operation = operation.upper()
        self._name = name

    def __str__(self):
        if self._scope.type == 'application':
            name = '/'.join(self._name[:-1])
        elif isinstance(self._name, str):
            name = self._name
        else:
            name = ':'.join(self._name)
        return f'{self._operation.upper()}_{self._scope.type.upper()}: {name}'

    def __repr__(self):
        return '<Operation ({})>'.format(self.__str__())

    def __eq__(self, other):
        if not isinstance(other, Operation):
            return NotImplemented
        return self.target is other.target and self.scope is other.scope and self.operation == other.operation and self.name == other.name

    def __hash__(self):
        name = self._name if isinstance(self._name, str) else tuple(self._name)
        return hash((self._scope.type, self._operation, name))

    def do(self, target=None):
        if not target:
            target = self._target

        if self._operation == 'UPDATE':
            item = self._scope.get([self._name])
            self._scope.update(*next(item), target)
        elif self._operation == 'DELETE':
            self._scope.delete(self._name, target)

    @property
    def target(self):
        return self._target

    @property
    def scope(self):
        return self._scope

    @property
    def operation(self):
        return self._operation

    @property
    def name(self):
        return self._name

    @property
    def sort_order(self):
        """Updates first, in dependency order, then deletes, in reverse dependency order.

        Updates must create what other objects need before them: dimensions before the cubes
        made of them, processes before the chores that run them. Deletes run last, so nothing
        still uses an object when it goes (a cube updated to a new dimension, before its old
        dimension is deleted), and from the top down (views before their cube).
        """
        order = self.Order[self._scope.type].value
        return (1, -order) if self._operation == 'DELETE' else (0, order)

    @staticmethod
    def sort(operations):
        return sorted(operations, key=lambda x: x.sort_order)

    class Order(IntEnum):
        """This enum defines all the possible operations that can take place as part
        of tm1cm against a TM1 application. It also defines the order in which those
        operations must take place.
        """

        process = auto()
        chore = auto()
        dimension = auto()
        hierarchy = auto()
        cube = auto()
        rule = auto()
        subset = auto()
        view = auto()
        application = auto()
        view_data = auto()
