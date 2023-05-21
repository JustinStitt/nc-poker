import os
import socket
import threading
from time import sleep
from textwrap import dedent

from dotenv import load_dotenv

from .types import Address
from .client import Client
from .state import State, StateError

load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "1234"))
DRAW: dict[str, bytes] = {"clear": b"\x1b[2J\x1b[H"}  # ] ]


class Server:
    def __init__(self, *, host: str, port: int):
        self.clients: dict[Address, Client] = {}
        self.host = host
        self.port = port
        self.server = self.setup_server()
        self.state = State.LOBBY

    def setup_server(self) -> socket.socket:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen()

        # TODO: replace with logging
        print(f"Started server on: {self.host=}, {self.port=}. Awaiting Connections...")
        return server

    def broadcast(self, message: bytes) -> None:
        for _, client in self.clients.items():
            client.send(message)

    def is_lobby_full(self) -> bool:
        return len(self.clients.keys()) >= 2

    def get_welcome_message(self) -> bytes:
        return dedent(
            f"""\tWelcome to Netcat Poker.\n
        You're in Lobby #1 ({len(self.clients.keys())} / 2)\n
        Waiting for the game to start...\n
        """
        ).encode()

    def handle_client_connection(self, conn: socket.socket, addr: Address) -> None:
        if self.state != State.LOBBY:
            raise StateError(current_state=self.state, expected_state=State.LOBBY)

        self.clients[addr] = Client(address=addr, socket=conn)
        print(f"CLIENT CONNECTED: {conn=}, {addr=}")

        if self.is_lobby_full():
            self.start_game()

        # send welcome message to all self.clients (including freshly connected one)
        self.broadcast(message=DRAW["clear"])
        self.broadcast(message=self.get_welcome_message())

        # send and receive data with the client on this thread
        while True:
            data = conn.recv(1024)
            self.handle_client_data(client=self.clients[addr], data=data)
            if not data:
                break

        print(f"❌ DISCONNECTED {self.clients[addr]}")
        del self.clients[addr]
        conn.close()

    def handle_client_data(self, client: Client, data: bytes) -> None:
        message = f"You said: {data.decode()}".encode()
        client.send(message)
        if data.decode() == "s\n":
            client.send(message)

    def kill_server_and_connections(self) -> None:
        print("☠ Killing Server... ", self)
        print("🤼 Disconnecting Clients" if len(self.clients.keys()) else "")
        self.broadcast("🧇SERVER CLOSED🧇".encode())
        for _, client in self.clients.items():
            client.socket.shutdown(socket.SHUT_RDWR)
            client.socket.close()

        self.server.shutdown(socket.SHUT_RDWR)  # gracefully kill server
        self.server.close()

    def run(self) -> None:
        self.start_lobby()

    def _ping(self) -> None:
        sleep(3)
        self.broadcast(b"pong")

    def serve_forever(self) -> None:
        """Spawn threads to handle new client connections"""
        while True:
            conn, addr = self.server.accept()

            # start a new thread to handle the client connection
            if self.state != State.LOBBY:
                conn.sendall("Game has started already.".encode())
                break

            t = threading.Thread(
                target=self.handle_client_connection, args=(conn, addr)
            )
            t.start()

    def start_lobby(self) -> None:
        """During the lobby state, players are able to connect"""
        if self.state == State.GAME:  # game already started, don't start a new lobby
            return

        t = threading.Thread(target=self.serve_forever)
        try:
            t.start()
            while t.is_alive():  # HACK: allows KeyboardInterrupt to hit thread
                t.join(0.5)
        except (KeyboardInterrupt, SystemExit):
            self.kill_server_and_connections()

    def start_game(self) -> None:
        """Exit the lobby state and enter the game state"""
        if self.state != State.LOBBY:  # can only start a game once, from the lobby
            return
        print("STARTING GAME")
        self.state = State.GAME


def main():
    server = Server(host=HOST, port=PORT)
    server.run()


if __name__ == "__main__":
    main()
