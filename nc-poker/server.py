import os
import socket
import threading
from time import sleep

from dotenv import load_dotenv

from .types import Address
from .client import Client

load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "1234"))
DRAW: dict[str, bytes] = {"clear": b"\x1b[2J\x1b[H"}


class Server:
    def __init__(self, *, host: str, port: int):
        self.clients: dict[Address, Client] = {}
        self.host = host
        self.port = port
        self.server = self.setup_server()

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

    def handle_client_connection(self, conn: socket.socket, addr: Address) -> None:
        self.clients[addr] = Client(address=addr, socket=conn)
        print(f"✔ CONNECTED: {conn=}, {addr=}")

        welcome_message = f"Welcome to Netcat Poker. Lobby #1 ({len(self.clients.keys())} / 6)\nWaiting for game to start..."

        # send welcome message to all self.clients (including freshly connected one)
        self.broadcast(message=DRAW["clear"])
        self.broadcast(message=welcome_message.encode())

        # send and receive data with the client on this thread
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(b"You said: " + data + b"\n")

        print(f"❌ DISCONNECTED {self.clients[addr]}")
        del self.clients[addr]
        conn.close()

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
        while True:
            conn, addr = self.server.accept()

            # start a new thread to handle the client connection
            t = threading.Thread(
                target=self.handle_client_connection, args=(conn, addr)
            )
            t.start()

    def start_lobby(self) -> None:
        t = threading.Thread(target=self.serve_forever)
        try:
            t.start()
            while t.is_alive():  # HACK: allows KeyboardInterrupt to hit thread
                t.join(0.5)
        except (KeyboardInterrupt, SystemExit):
            self.kill_server_and_connections()

    def start_game(self) -> None:
        print("STARTING GAME")
        pass


def main():
    server = Server(host=HOST, port=PORT)
    server.run()


if __name__ == "__main__":
    main()
