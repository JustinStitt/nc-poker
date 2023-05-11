import os
import socket
import threading

from dotenv import load_dotenv

from .types import Address

load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "1234"))
DRAW: dict[str, bytes] = {"clear": b"\x1b[2J\x1b[H"}


class Server:
    def __init__(self, *, host: str, port: int):
        self.clients: dict[Address, socket.socket] = {}
        self.server = self.setup_server(host=host, port=port)

    def setup_server(self, *, host: str, port: int) -> socket.socket:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()

        # TODO: replace with logging
        print(f"Started server on: {host=}, {port=}. Awaiting Connections...")
        return server

    def broadcast(self, message: bytes) -> None:
        for _, conn in self.clients.items():
            conn.sendall(message)

    def handle_client_connection(self, conn: socket.socket, addr: Address) -> None:
        self.clients[addr] = conn
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
        for _, client_socket in self.clients.items():
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()

        self.server.shutdown(socket.SHUT_RDWR)  # gracefully kill server
        self.server.close()

    def serve_forever(self) -> None:
        while True:
            try:
                conn, addr = self.server.accept()
                # start a new thread to handle the client connection
                t = threading.Thread(
                    target=self.handle_client_connection, args=(conn, addr)
                )
                t.start()
            except KeyboardInterrupt:
                self.kill_server_and_connections()
                exit(0)  # gracefully kill interpreter


def main():
    server = Server(host=HOST, port=PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
