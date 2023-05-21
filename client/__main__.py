from socket import socket, AF_INET, SOCK_STREAM
import sys
import select

HOST = "127.0.0.1"
PORT = 1234
s = socket(AF_INET, SOCK_STREAM)
s.connect((HOST, PORT))

# TODO: crypto

while True:
    socket_list = [sys.stdin, s]

    # Get the list sockets which are readable
    read_sockets, write_sockets, error_sockets = select.select(socket_list, [], [])

    for sock in read_sockets:
        # incoming message from remote server
        if sock == s:
            data = sock.recv(1024)
            if not data:
                print("\nDisconnected from server")
                s.close()
                exit(0)
            else:
                sys.stdout.write(data.decode())

        # user entered a message
        else:
            msg = sys.stdin.readline()
            s.send(msg.encode())
