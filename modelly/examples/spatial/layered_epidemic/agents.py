from enum import IntEnum

from modelly import Agent


class State(IntEnum):
    SUSCEPTIBLE = 0
    INFECTED = 1
    RECOVERED = 2


class Person(Agent):
    """A person: a node of the contact network, an age and an infection state.

    The states of everybody live in one numpy array on the model (``model.state``), so a
    step updates the whole population with one sparse product; ``person.state`` reads it.
    """

    def __init__(self, model, node, age):
        super().__init__(model)
        self.node = node
        self.age = age

    @property
    def state(self):
        return State(int(self.model.state[self.node]))
