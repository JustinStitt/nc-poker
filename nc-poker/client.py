from socket import socket
from .types import Address, Hand
from re import findall


class Client:
    CHOICE_PATTERN = r"\d+"

    def __init__(self, address: Address, socket: socket):
        self.address = address
        self.socket = socket
        self.ready = False
        self.hand: Hand | None = None
        self.can_choose: bool = False
        self.choice: int | None = None
        self.chosen: list[int] = []
        self.score: int = 0

    def send(self, message: bytes) -> None:
        self.socket.sendall(message)

    def set_hand(self, hand: Hand) -> None:
        self.hand = hand

    def set_choice(self, choice: bytes) -> None:
        self.choice = Client.get_choice_as_int(raw_choice=choice)
        self.chosen.append(self.choice)

    def get_remaining_choices(self) -> list[int]:
        assert self.hand, "No hand when determining remaining choices!"

        choices = set(self.hand) - set(self.chosen)

        return list(choices)

    @staticmethod
    def get_choice_as_int(raw_choice: bytes) -> int:
        assert raw_choice, "Cannot have a None choice"

        matches = findall(Client.CHOICE_PATTERN, raw_choice.decode())

        if len(matches) != 1:  # they entered some bad stuff
            return -1

        return int(matches[0])

    def valid_choice(self, choice: bytes) -> bool:
        assert self.hand, "No client hand, can't validate choice!"

        as_str = choice.decode()
        matches = findall(Client.CHOICE_PATTERN, as_str)
        if len(matches) != 1:
            return False

        # extract match
        as_int = int(matches[0])

        return as_int in self.hand
