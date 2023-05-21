from enum import Enum


class State(Enum):
    LOBBY = 1
    GAME = 2


class StateError(Exception):
    def __init__(self, current_state: State, expected_state: State):
        super().__init__()
        self.current_state = current_state
        self.expected_state = expected_state

    def __str__(self):
        return (
            f"Expected {self.expected_state} was actually in state {self.current_state}"
        )
