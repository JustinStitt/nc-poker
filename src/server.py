import socket
import threading
from stypes import Address

HOST = "127.0.0.1"
PORT = 1234

clients: dict[Address, socket.socket] = {}


def process_data(data) -> None:
    print(f"{data=}")


def handle_client(conn: socket.socket, addr: Address) -> None:
    # add the connection to the clients dictionary
    clients[addr] = conn
    print(f"✔ CONNECTED: {conn=}, {addr=}")

    # send a welcome message to the client
    conn.sendall(
        b"Welcome to the poker game!" + bytes(str(addr), encoding="utf-8") + b"\n"
    )

    # send and receive data with the client on this thread
    while True:
        data = conn.recv(1024)
        if not data:
            break
        conn.sendall(b"You said: " + data + b"\n")
        # response = process_data(data)

        # send the response to all clients except the sender
        # for client_addr, client_conn in clients.items():
        #     if client_addr != addr:
        #         client_conn.sendall(response)

    print(f"❌ DISCONNECTED {clients[addr]}")
    del clients[addr]
    conn.close()


def setup_server(*, host: str, port: int) -> socket.socket:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()

    print(f"Started server on: {host=}, {port=}. Awaiting Connections...")

    return server


def kill_server_and_connections(server: socket.socket):
    print("☠ Killing Server...")
    print("🤼 Disconnecting Clients" if len(clients.keys()) else "")
    for _, client_socket in clients.items():
        client_socket.shutdown(socket.SHUT_RDWR)
        client_socket.close()
    server.shutdown(socket.SHUT_RDWR)  # gracefully kill server
    server.close()


# wait for clients to connect
def serve_forever(server: socket.socket):
    while True:
        try:
            conn, addr = server.accept()
            # start a new thread to handle the client connection
            t = threading.Thread(target=handle_client, args=(conn, addr))
            t.start()
        except KeyboardInterrupt:
            kill_server_and_connections(server)
            exit(0)  # gracefully kill interpreter


if __name__ == "__main__":
    server = setup_server(host=HOST, port=PORT)
    serve_forever(server)
