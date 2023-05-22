import os
import socket
import threading
from time import sleep
from textwrap import dedent

from dotenv import load_dotenv

from .types import Address
from .client import Client
from .state import State, StateError
from .logic import get_random_hand

load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "1234"))
DRAW: dict[str, bytes] = {"clear": b"\x1b[2J\x1b[H"}  # ] ]


class Server:
    MAX_LOBBY_SIZE = 2
    MAX_ROUNDS = 3

    def __init__(self, *, host: str, port: int):
        self.clients: dict[Address, Client] = {}
        self.host = host
        self.port = port
        self.server = self.setup_server()
        self.state = State.LOBBY
        self.round: int = 0
        self._number_of_clients_chosen: int = 0

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
        return self.number_of_players() >= Server.MAX_LOBBY_SIZE

    def get_welcome_message(self) -> bytes:
        return dedent(
            f"""\tWelcome to Netcat Poker.\n
        You're in Lobby #1 ({self.number_of_players()} / {Server.MAX_LOBBY_SIZE})\n
        Waiting for the game to start...\n
        """
        ).encode()

    def handle_client_connection(self, conn: socket.socket, addr: Address) -> None:
        if self.state != State.LOBBY:
            raise StateError(current_state=self.state, expected_state=State.LOBBY)

        self.clients[addr] = Client(address=addr, socket=conn)
        print(f"CLIENT CONNECTED: {conn=}, {addr=}")

        self.broadcast(message=DRAW["clear"])
        self.broadcast(message=self.get_welcome_message())

        if self.is_lobby_full():
            self.start_game()

        # send and receive data with the client on this thread
        while True:
            data = conn.recv(1024)
            self.handle_client_data(client=self.clients[addr], data=data)
            if not data:
                break

        print(f"❌ DISCONNECTED {self.clients[addr]}")
        del self.clients[addr]
        conn.close()

    def determine_round_winners(self) -> list[Client]:
        choices: list[tuple[Client, int]] = []

        # set client->choice pairings
        for _, client in self.clients.items():
            assert (
                client.choice
            ), "When determining round winner, missing a choice for a client"
            choices.append((client, client.choice))

        best = ([], -1)
        # determine winner of round
        for client, choice in choices:
            if choice > best[1]:
                best = ([client], choice)
            elif choice == best[1]:
                best[0].append(client)

        print(f"{best=}", flush=True)

        return best[0]

    def handle_client_data(self, client: Client, data: bytes) -> None:
        print(f"{client=}, {data=}", flush=True)
        if self.state != State.GAME:  # user input doesnt do anything in non-game state
            return

        if not client.can_choose:  # client is not elligible to make a choice atm
            return

        if not client.valid_choice(data):
            client.send("\tInvalid Choice, Try Again\n\tChoice: ".encode())
            return

        client.set_choice(data)
        client.can_choose = False
        self._number_of_clients_chosen += 1

        assert (
            self._number_of_clients_chosen <= self.number_of_players()
        ), "Can't have more choices than players!"

        message = (
            f"\tYou chose: {client.choice}\n\tWaiting for other player(s)...\n".encode()
        )
        client.send(message)

        if self._number_of_clients_chosen == Server.MAX_LOBBY_SIZE:
            self.handle_post_choice_proceedings()

    def handle_post_choice_proceedings(self) -> None:
        self.show_clients_their_opponents_choices()
        winners = self.determine_round_winners()

        assert winners and len(winners), "Determining winner resulted in no winners!"

        losers = [c for _, c in self.clients.items() if c not in winners]

        for loser in losers:
            loser.send(f"\n\t❌ You LOST this round!\n".encode())

        for winner in winners:
            winner.send(f"\n\t🎉 You WON this round!\n".encode())
            winner.score += 1

        self.broadcast(message=f"\tStarting next round in\n".encode())
        for i in range(3, 0, -1):
            self.broadcast(message=f"\t\t{i}\n".encode())
            sleep(1.3)

        self.broadcast(message=DRAW["clear"])
        self.start_new_round()

    def show_clients_their_opponents_choices(self) -> None:
        for _, client in self.clients.items():
            other_clients = [
                c.choice for _, c in self.clients.items() if c != client and c.choice
            ]
            message = f"\n\tOpposition: {other_clients}\n"
            client.send(message.encode())

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

    def number_of_players(self) -> int:
        return len(self.clients.keys())

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

        assert (
            self.number_of_players() == Server.MAX_LOBBY_SIZE
        ), f"Must have exactly {Server.MAX_LOBBY_SIZE} players to start the game!"

        self.state = State.GAME
        print("STARTING GAME")

        self.broadcast(message=DRAW["clear"])
        # generate each player's hand
        for _, client in self.clients.items():
            client.set_hand(get_random_hand(3, 1, 15))

        self.start_new_round()

    def show_endgame_screen(self) -> None:
        highest_score = max([c.score for _, c in self.clients.items()])
        print(f"{highest_score=}")
        winners = [c for _, c in self.clients.items() if c.score == highest_score]
        everyone_else = [c for _, c in self.clients.items() if c not in winners]

        assert winners and len(
            winners
        ), "No winners were found when showing endgame screen!"

        self.broadcast(DRAW["clear"])

        standalone = len(winners) == 1  # did a single person win? or was it a tie

        for winner in winners:
            message = f"You {'WON' if standalone else 'TIED FOR'} FIRST PLACE! 🎉🙌🏼"
            winner.send(message.encode())

        for client in everyone_else:
            message = f"You LOST 😭!"
            client.send(message.encode())

        self.broadcast("Killing server in ".encode())
        for i in range(3, 0, -1):
            self.broadcast(f"{i}... ".encode())
            sleep(1.1)
        self.kill_server_and_connections()

    def start_new_round(self) -> None:
        self.round += 1
        if self.round > Server.MAX_ROUNDS:
            self.show_endgame_screen()

        self._number_of_clients_chosen = 0
        for _, client in self.clients.items():
            hand_message = f"""
            Round # {self.round}\n
            Score: {client.score}\n
            Your hand is: {client.get_remaining_choices()}\n
            Choice: """

            client.send(hand_message.encode())
            client.can_choose = True


def main():
    server = Server(host=HOST, port=PORT)
    server.run()


if __name__ == "__main__":
    main()
