import socket
import threading
import json
import struct
import argparse


HOST = "0.0.0.0"
GAME_ID = "GAME-001"

clients = []
clients_lock = threading.Lock()
game_lock = threading.Lock()

board = [
    ["", "", ""],
    ["", "", ""],
    ["", "", ""]
]

current_turn = "P1"
state_version = 0
game_started = False
game_over = False

scores = {
    "P1": 0,
    "P2": 0,
    "draws": 0
}


def validate_port(value):
    try:
        port = int(value)

    except ValueError:
        raise argparse.ArgumentTypeError(
            "Port must be an integer."
        )

    if port < 1024 or port > 65535:
        raise argparse.ArgumentTypeError(
            "Port must be between 1024 and 65535."
        )

    return port


def parse_args():
    parser = argparse.ArgumentParser(
        description="Tic-Tac-Toe TCP server"
    )

    parser.add_argument(
        "-p",
        "--port",
        type=validate_port,
        required=True,
        help="Port number for the server (1024-65535)"
    )

    return parser.parse_args()


def recv_exact(sock, length):
    data = b""

    while len(data) < length:
        chunk = sock.recv(
            length - len(data)
        )

        if not chunk:
            return None

        data += chunk

    return data


def receive_message(sock):
    header = recv_exact(
        sock,
        4
    )

    if header is None:
        return None

    length = struct.unpack(
        "!I",
        header
    )[0]

    payload = recv_exact(
        sock,
        length
    )

    if payload is None:
        return None

    return json.loads(
        payload.decode("utf-8")
    )


def send_message(sock, message):
    payload = json.dumps(
        message
    ).encode("utf-8")

    header = struct.pack(
        "!I",
        len(payload)
    )

    sock.sendall(
        header + payload
    )


def send_error(
    client_socket,
    request_id,
    player_id,
    error_message
):
    message = {
        "version": 1,
        "msg_type": "ERROR",
        "request_id": request_id,
        "game_id": GAME_ID,
        "player_id": player_id,
        "state_version": state_version,
        "payload": {
            "message": error_message
        }
    }

    send_message(
        client_socket,
        message
    )


def get_clients_snapshot():
    with clients_lock:
        return list(clients)


def broadcast(message):
    client_list = get_clients_snapshot()

    for client in client_list:
        try:
            send_message(
                client["socket"],
                message
            )

        except OSError:
            pass


def check_winner():
    lines = []

    for row in board:
        lines.append(row)

    for column in range(3):
        lines.append(
            [
                board[0][column],
                board[1][column],
                board[2][column]
            ]
        )

    lines.append(
        [
            board[0][0],
            board[1][1],
            board[2][2]
        ]
    )

    lines.append(
        [
            board[0][2],
            board[1][1],
            board[2][0]
        ]
    )

    for line in lines:
        if (
            line[0]
            and line[0] == line[1]
            and line[1] == line[2]
        ):
            return line[0]

    return None


def board_is_full():
    return all(
        cell != ""
        for row in board
        for cell in row
    )


def make_game_start_message():
    with clients_lock:
        players = []

        for client in clients:
            symbol = (
                "X"
                if client["player_id"] == "P1"
                else "O"
            )

            players.append(
                {
                    "player_id":
                        client["player_id"],
                    "player_name":
                        client["player_name"],
                    "symbol":
                        symbol
                }
            )

    return {
        "version": 1,
        "msg_type": "GAME_START",
        "request_id": None,
        "game_id": GAME_ID,
        "player_id": None,
        "state_version": state_version,
        "payload": {
            "players": players,
            "first_turn": current_turn,
            "board": [
                row[:]
                for row in board
            ]
        }
    }


def make_state_update_message():
    return {
        "version": 1,
        "msg_type": "STATE_UPDATE",
        "request_id": None,
        "game_id": GAME_ID,
        "player_id": None,
        "state_version": state_version,
        "payload": {
            "board": [
                row[:]
                for row in board
            ],
            "current_turn":
                current_turn
        }
    }


def make_game_over_message(
    result,
    winner_player_id
):
    return {
        "version": 1,
        "msg_type": "GAME_OVER",
        "request_id": None,
        "game_id": GAME_ID,
        "player_id": None,
        "state_version": state_version,
        "payload": {
            "board": [
                row[:]
                for row in board
            ],
            "result":
                result,
            "winner_player_id":
                winner_player_id,
            "scores":
                scores.copy()
        }
    }


def process_move(
    client_socket,
    message,
    player_id
):
    global current_turn
    global state_version
    global game_over

    request_id = message.get(
        "request_id"
    )

    payload = message.get(
        "payload",
        {}
    )

    update_message = None
    game_over_message = None

    with game_lock:
        if not game_started:
            send_error(
                client_socket,
                request_id,
                player_id,
                "Game has not started"
            )

            return

        if game_over:
            send_error(
                client_socket,
                request_id,
                player_id,
                "Game is already over"
            )

            return

        if player_id != current_turn:
            send_error(
                client_socket,
                request_id,
                player_id,
                "It is not your turn"
            )

            return

        row = payload.get(
            "row"
        )

        col = payload.get(
            "col"
        )

        if (
            not isinstance(row, int)
            or not isinstance(col, int)
            or row < 0
            or row > 2
            or col < 0
            or col > 2
        ):
            send_error(
                client_socket,
                request_id,
                player_id,
                "Row and column must be between 0 and 2"
            )

            return

        if board[row][col] != "":
            send_error(
                client_socket,
                request_id,
                player_id,
                "Board position is already occupied"
            )

            return

        symbol = (
            "X"
            if player_id == "P1"
            else "O"
        )

        board[row][col] = symbol

        state_version += 1

        winner_symbol = check_winner()

        if winner_symbol is not None:
            winner_player_id = (
                "P1"
                if winner_symbol == "X"
                else "P2"
            )

            scores[
                winner_player_id
            ] += 1

            game_over = True

            game_over_message = (
                make_game_over_message(
                    "WIN",
                    winner_player_id
                )
            )

        elif board_is_full():
            scores["draws"] += 1

            game_over = True

            game_over_message = (
                make_game_over_message(
                    "DRAW",
                    None
                )
            )

        else:
            if current_turn == "P1":
                current_turn = "P2"

            else:
                current_turn = "P1"

            update_message = (
                make_state_update_message()
            )

    if update_message is not None:
        broadcast(
            update_message
        )

    if game_over_message is not None:
        broadcast(
            game_over_message
        )


def handle_client(
    client_socket,
    address
):
    global game_started

    player_id = None

    try:
        message = receive_message(
            client_socket
        )

        if message is None:
            return

        print(
            f"Received from {address}: "
            f"{message}"
        )

        if message.get(
            "msg_type"
        ) != "CONNECT":
            send_error(
                client_socket,
                message.get(
                    "request_id"
                ),
                None,
                "First message must be CONNECT"
            )

            return

        payload = message.get(
            "payload",
            {}
        )

        player_name = payload.get(
            "player_name",
            ""
        )

        if (
            not isinstance(
                player_name,
                str
            )
            or not player_name.strip()
        ):
            send_error(
                client_socket,
                message.get(
                    "request_id"
                ),
                None,
                "Player name cannot be empty"
            )

            return

        player_name = (
            player_name.strip()
        )

        with clients_lock:
            if len(clients) >= 2:
                too_many_players = True

            else:
                too_many_players = False

                if len(clients) == 0:
                    player_id = "P1"

                else:
                    player_id = "P2"

                clients.append(
                    {
                        "socket":
                            client_socket,
                        "address":
                            address,
                        "player_id":
                            player_id,
                        "player_name":
                            player_name
                    }
                )

        if too_many_players:
            send_error(
                client_socket,
                message.get(
                    "request_id"
                ),
                None,
                "Game already has two players"
            )

            return

        print(
            f"{player_id} joined the game"
        )

        if player_id == "P1":
            lobby_wait = {
                "version": 1,
                "msg_type":
                    "LOBBY_WAIT",
                "request_id":
                    message.get(
                        "request_id"
                    ),
                "game_id":
                    GAME_ID,
                "player_id":
                    "P1",
                "state_version":
                    state_version,
                "payload": {
                    "message":
                        "Waiting for Player 2"
                }
            }

            send_message(
                client_socket,
                lobby_wait
            )

        with clients_lock:
            ready_to_start = (
                len(clients) == 2
            )

        if ready_to_start:
            with game_lock:
                if not game_started:
                    game_started = True

                    game_start_message = (
                        make_game_start_message()
                    )

                else:
                    game_start_message = None

            if (
                game_start_message
                is not None
            ):
                broadcast(
                    game_start_message
                )

        while True:
            message = receive_message(
                client_socket
            )

            if message is None:
                break

            print(
                f"Received from {address}: "
                f"{message}"
            )

            msg_type = message.get(
                "msg_type"
            )

            if msg_type == "MOVE":
                process_move(
                    client_socket,
                    message,
                    player_id
                )

            elif (
                msg_type
                == "DISCONNECT"
            ):
                break

            else:
                send_error(
                    client_socket,
                    message.get(
                        "request_id"
                    ),
                    player_id,
                    "Unsupported message type"
                )

    except (
        ConnectionResetError,
        BrokenPipeError,
        json.JSONDecodeError,
        OSError
    ) as error:
        print(
            f"Connection error from "
            f"{address}: {error}"
        )

    finally:
        with clients_lock:
            clients[:] = [
                client
                for client in clients
                if client["socket"]
                is not client_socket
            ]

        try:
            client_socket.close()

        except OSError:
            pass

        print(
            f"Client disconnected: "
            f"{address}"
        )


def main():
    args = parse_args()

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server_socket.bind(
        (
            HOST,
            args.port
        )
    )

    server_socket.listen()

    print(
        f"Server listening on port "
        f"{args.port}"
    )

    try:
        while True:
            client_socket, address = (
                server_socket.accept()
            )

            print(
                f"Client connected: "
                f"{address}"
            )

            client_thread = (
                threading.Thread(
                    target=handle_client,
                    args=(
                        client_socket,
                        address
                    ),
                    daemon=True
                )
            )

            client_thread.start()

    except KeyboardInterrupt:
        print(
            "\nServer shutting down."
        )

    finally:
        try:
            server_socket.close()

        except OSError:
            pass


if __name__ == "__main__":
    main()