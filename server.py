import socket
import threading
import json
import struct
import argparse

HOST = "0.0.0.0"
GAME_ID = "GAME-001"

clients = []
state_lock = threading.Lock()

board = [
    ["", "", ""],
    ["", "", ""],
    ["", "", ""]
]

current_turn = "P1"
state_version = 0

scores = {
    "P1": 0,
    "P2": 0,
    "draws": 0
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Tic-Tac-Toe TCP server"
    )

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        required=True,
        help="Port number for the server"
    )

    return parser.parse_args()


def recv_exact(sock, length):
    data = b""

    while len(data) < length:
        chunk = sock.recv(length - len(data))

        if not chunk:
            return None

        data += chunk

    return data


def send_message(sock, message):
    payload = json.dumps(message).encode("utf-8")
    header = struct.pack("!I", len(payload))

    sock.sendall(header + payload)


def receive_message(sock):
    header = recv_exact(sock, 4)

    if header is None:
        return None

    length = struct.unpack("!I", header)[0]

    payload = recv_exact(sock, length)

    if payload is None:
        return None

    return json.loads(
        payload.decode("utf-8")
    )


def board_copy():
    return [
        row[:]
        for row in board
    ]


def reset_board():
    global board
    global current_turn
    global state_version

    board = [
        ["", "", ""],
        ["", "", ""],
        ["", "", ""]
    ]

    current_turn = "P1"
    state_version = 0


def get_client_by_socket(client_socket):
    for client in clients:
        if client["socket"] is client_socket:
            return client

    return None


def get_player_list():
    return [
        {
            "player_id": client["player_id"],
            "player_name": client["player_name"],
            "symbol": client["symbol"]
        }
        for client in clients
    ]


def board_is_full():
    return all(
        cell != ""
        for row in board
        for cell in row
    )


def check_winner():
    winning_lines = [
        board[0],
        board[1],
        board[2],

        [
            board[0][0],
            board[1][0],
            board[2][0]
        ],

        [
            board[0][1],
            board[1][1],
            board[2][1]
        ],

        [
            board[0][2],
            board[1][2],
            board[2][2]
        ],

        [
            board[0][0],
            board[1][1],
            board[2][2]
        ],

        [
            board[0][2],
            board[1][1],
            board[2][0]
        ]
    ]

    for line in winning_lines:
        if (
            line[0] != ""
            and line[0] == line[1]
            and line[1] == line[2]
        ):
            return line[0]

    return None


def symbol_to_player_id(symbol):
    if symbol == "X":
        return "P1"

    if symbol == "O":
        return "P2"

    return None


def send_error(
    client_socket,
    request_id,
    player_id,
    message_text
):
    with state_lock:
        version = state_version

    error_message = {
        "version": 1,
        "msg_type": "ERROR",
        "request_id": request_id,
        "game_id": GAME_ID,
        "player_id": player_id,
        "state_version": version,
        "payload": {
            "message": message_text
        }
    }

    send_message(
        client_socket,
        error_message
    )


def handle_connect(
    client_socket,
    address,
    message
):
    waiting_message = None
    game_start_message = None
    recipients = []
    reject = False

    with state_lock:
        existing_client = get_client_by_socket(
            client_socket
        )

        if existing_client is not None:
            return

        if len(clients) >= 2:
            reject = True

        else:
            if len(clients) == 0:
                reset_board()

            used_ids = {
                client["player_id"]
                for client in clients
            }

            if "P1" not in used_ids:
                player_id = "P1"
                symbol = "X"

            else:
                player_id = "P2"
                symbol = "O"

            payload = message.get(
                "payload",
                {}
            )

            player_name = payload.get(
                "player_name",
                player_id
            )

            client_info = {
                "socket": client_socket,
                "address": address,
                "player_id": player_id,
                "player_name": player_name,
                "symbol": symbol
            }

            clients.append(
                client_info
            )

            print(
                f"{player_id} joined the game"
            )

            if len(clients) == 1:
                waiting_message = {
                    "version": 1,
                    "msg_type": "LOBBY_WAIT",
                    "request_id": message.get(
                        "request_id"
                    ),
                    "game_id": GAME_ID,
                    "player_id": player_id,
                    "state_version":
                        state_version,
                    "payload": {
                        "message":
                            "Waiting for Player 2"
                    }
                }

            elif len(clients) == 2:
                game_start_message = {
                    "version": 1,
                    "msg_type": "GAME_START",
                    "request_id": None,
                    "game_id": GAME_ID,
                    "player_id": None,
                    "state_version":
                        state_version,
                    "payload": {
                        "players":
                            get_player_list(),
                        "first_turn":
                            current_turn,
                        "board":
                            board_copy()
                    }
                }

                recipients = [
                    client["socket"]
                    for client in clients
                ]

    if reject:
        send_error(
            client_socket,
            message.get("request_id"),
            None,
            "Game already has two players"
        )

        return

    if waiting_message is not None:
        send_message(
            client_socket,
            waiting_message
        )

    if game_start_message is not None:
        for sock in recipients:
            try:
                send_message(
                    sock,
                    game_start_message
                )

            except OSError:
                pass


def handle_move(
    client_socket,
    message
):
    global current_turn
    global state_version

    error_text = None
    player_id = None
    outgoing_message = None
    recipients = []

    with state_lock:
        client = get_client_by_socket(
            client_socket
        )

        if client is None:
            error_text = (
                "Player is not registered"
            )

        else:
            player_id = client["player_id"]

        if (
            error_text is None
            and len(clients) < 2
        ):
            error_text = (
                "Waiting for Player 2"
            )

        if (
            error_text is None
            and message.get("game_id")
            != GAME_ID
        ):
            error_text = (
                "Invalid game ID"
            )

        if (
            error_text is None
            and message.get("player_id")
            != player_id
        ):
            error_text = (
                "Invalid player ID"
            )

        if (
            error_text is None
            and message.get(
                "state_version"
            ) != state_version
        ):
            error_text = (
                "Stale state version"
            )

        if (
            error_text is None
            and player_id != current_turn
        ):
            error_text = (
                "Not your turn"
            )

        if error_text is None:
            payload = message.get(
                "payload",
                {}
            )

            row = payload.get("row")
            col = payload.get("col")

            if (
                not isinstance(row, int)
                or isinstance(row, bool)
            ):
                error_text = (
                    "Row must be an integer"
                )

            elif (
                not isinstance(col, int)
                or isinstance(col, bool)
            ):
                error_text = (
                    "Column must be an integer"
                )

            elif (
                row < 0
                or row > 2
                or col < 0
                or col > 2
            ):
                error_text = (
                    "Row and column must be "
                    "between 0 and 2"
                )

            elif board[row][col] != "":
                error_text = (
                    "Board position is already "
                    "occupied"
                )

            else:
                board[row][col] = (
                    client["symbol"]
                )

                state_version += 1

                winner_symbol = (
                    check_winner()
                )

                is_draw = (
                    winner_symbol is None
                    and board_is_full()
                )

                recipients = [
                    item["socket"]
                    for item in clients
                ]

                if winner_symbol is not None:
                    winner_player_id = (
                        symbol_to_player_id(
                            winner_symbol
                        )
                    )

                    scores[
                        winner_player_id
                    ] += 1

                    outgoing_message = {
                        "version": 1,
                        "msg_type":
                            "GAME_OVER",
                        "request_id":
                            message.get(
                                "request_id"
                            ),
                        "game_id": GAME_ID,
                        "player_id": None,
                        "state_version":
                            state_version,
                        "payload": {
                            "result": "WIN",
                            "winner_player_id":
                                winner_player_id,
                            "board":
                                board_copy(),
                            "scores":
                                dict(scores)
                        }
                    }

                elif is_draw:
                    scores["draws"] += 1

                    outgoing_message = {
                        "version": 1,
                        "msg_type":
                            "GAME_OVER",
                        "request_id":
                            message.get(
                                "request_id"
                            ),
                        "game_id": GAME_ID,
                        "player_id": None,
                        "state_version":
                            state_version,
                        "payload": {
                            "result": "DRAW",
                            "winner_player_id":
                                None,
                            "board":
                                board_copy(),
                            "scores":
                                dict(scores)
                        }
                    }

                else:
                    if current_turn == "P1":
                        current_turn = "P2"
                    else:
                        current_turn = "P1"

                    outgoing_message = {
                        "version": 1,
                        "msg_type":
                            "STATE_UPDATE",
                        "request_id":
                            message.get(
                                "request_id"
                            ),
                        "game_id": GAME_ID,
                        "player_id": None,
                        "state_version":
                            state_version,
                        "payload": {
                            "board":
                                board_copy(),
                            "current_turn":
                                current_turn,
                            "last_move": {
                                "player_id":
                                    player_id,
                                "row": row,
                                "col": col
                            }
                        }
                    }

    if error_text is not None:
        send_error(
            client_socket,
            message.get(
                "request_id"
            ),
            player_id,
            error_text
        )

        return

    if outgoing_message is not None:
        for sock in recipients:
            try:
                send_message(
                    sock,
                    outgoing_message
                )

            except OSError:
                pass


def handle_client(
    client_socket,
    address
):
    print(
        f"Client connected: {address}"
    )

    try:
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

            if msg_type == "CONNECT":
                handle_connect(
                    client_socket,
                    address,
                    message
                )

            elif msg_type == "MOVE":
                handle_move(
                    client_socket,
                    message
                )

            else:
                with state_lock:
                    client = (
                        get_client_by_socket(
                            client_socket
                        )
                    )

                    if client is None:
                        player_id = None

                    else:
                        player_id = (
                            client["player_id"]
                        )

                send_error(
                    client_socket,
                    message.get(
                        "request_id"
                    ),
                    player_id,
                    "Invalid or unsupported "
                    "message type"
                )

    except (
        ConnectionResetError,
        BrokenPipeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        struct.error,
        OSError
    ) as error:
        print(
            f"Connection error from "
            f"{address}: {error}"
        )

    finally:
        with state_lock:
            clients[:] = [
                client
                for client in clients
                if client["socket"]
                is not client_socket
            ]

            if len(clients) == 0:
                reset_board()

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

            client_thread = threading.Thread(
                target=handle_client,
                args=(
                    client_socket,
                    address
                ),
                daemon=True
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