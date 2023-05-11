from socket import socket
from .types import Address


class Client:
    def __init__(self, address: Address, socket: socket):
        self.address = address
        self.socket = socket
        self.ready = False
        self.hand = ""

    def send(self, message: bytes) -> None:
        self.socket.sendall(message)
