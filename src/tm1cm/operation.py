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
        return self.target == self.target and self.scope == other.scope and self.operation == other.operation and self._name == other.name

    def __hash__(self):
        return hash(self.type.value + str(self._arguments))

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
        val = self.Order[self._scope.type].value * -1 if self._operation == 'DELETE' else 1
        return val

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
