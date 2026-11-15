import socket
import json
import struct
import argparse
import sys


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
        description="Tic-Tac-Toe TCP client"
    )

    parser.add_argument(
        "-i",
        "--ip",
        required=True,
        help="Server DNS hostname"
    )

    parser.add_argument(
        "-p",
        "--port",
        type=validate_port,
        required=True,
        help="Server port number (1024-65535)"
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

    payload = recv_exact(
        sock,
        length
    )

    if payload is None:
        return None

    return json.loads(
        payload.decode("utf-8")
    )


def display_board(board):
    print()

    for row_index, row in enumerate(board):
        display_row = [
            cell if cell else " "
            for cell in row
        ]

        print(
            f" {display_row[0]} | "
            f"{display_row[1]} | "
            f"{display_row[2]} "
        )

        if row_index < 2:
            print("---+---+---")

    print()


def get_player_name():
    while True:
        player_name = input(
            "Enter player name: "
        ).strip()

        if player_name:
            return player_name

        print(
            "Player name cannot be empty."
        )


def get_move():
    while True:
        try:
            row = int(
                input(
                    "Enter row (0-2): "
                )
            )

            col = int(
                input(
                    "Enter column (0-2): "
                )
            )

            if (
                row not in range(3)
                or col not in range(3)
            ):
                print(
                    "Row and column must be "
                    "between 0 and 2."
                )

                continue

            return row, col

        except ValueError:
            print(
                "Please enter numbers only."
            )


def make_move_message(
    request_number,
    game_id,
    player_id,
    state_version,
    row,
    col
):
    return {
        "version": 1,
        "msg_type": "MOVE",
        "request_id":
            f"REQ-{request_number:03d}",
        "game_id": game_id,
        "player_id": player_id,
        "state_version": state_version,
        "payload": {
            "row": row,
            "col": col
        }
    }


def send_move(
    client_socket,
    request_number,
    game_id,
    player_id,
    state_version
):
    row, col = get_move()

    move_message = make_move_message(
        request_number,
        game_id,
        player_id,
        state_version,
        row,
        col
    )

    send_message(
        client_socket,
        move_message
    )

    print(
        f"Move sent: "
        f"row={row}, col={col}"
    )

    return request_number + 1


def main():
    args = parse_args()

    client_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    player_id = None
    game_id = None
    state_version = 0
    request_number = 1

    try:
        try:
            server_ip = socket.gethostbyname(
                args.ip
            )

        except socket.gaierror:
            print(
                f"[ERROR] Unable to resolve DNS hostname "
                f"'{args.ip}'."
            )

            print(
                "Please check your Cisco router DNS "
                "configuration ('ip dns server' / "
                "'ip host') or verify the hostname spelling."
            )

            sys.exit(1)

        client_socket.connect(
            (
                server_ip,
                args.port
            )
        )

        print(
            f"Connected to "
            f"{args.ip}:{args.port}"
        )

        player_name = get_player_name()

        connect_message = {
            "version": 1,
            "msg_type": "CONNECT",
            "request_id":
                f"REQ-{request_number:03d}",
            "game_id": None,
            "player_id": None,
            "state_version": 0,
            "payload": {
                "player_name": player_name
            }
        }

        request_number += 1

        send_message(
            client_socket,
            connect_message
        )

        while True:
            response = receive_message(
                client_socket
            )

            if response is None:
                print(
                    "Server disconnected."
                )
                break

            msg_type = response.get(
                "msg_type"
            )

            if msg_type == "LOBBY_WAIT":
                player_id = response.get(
                    "player_id"
                )

                game_id = response.get(
                    "game_id"
                )

                state_version = response.get(
                    "state_version",
                    state_version
                )

                payload = response.get(
                    "payload",
                    {}
                )

                print(
                    payload.get(
                        "message",
                        "Waiting for Player 2"
                    )
                )

            elif msg_type == "GAME_START":
                game_id = response.get(
                    "game_id"
                )

                state_version = response.get(
                    "state_version",
                    0
                )

                payload = response.get(
                    "payload",
                    {}
                )

                players = payload.get(
                    "players",
                    []
                )

                board = payload.get(
                    "board",
                    [
                        ["", "", ""],
                        ["", "", ""],
                        ["", "", ""]
                    ]
                )

                first_turn = payload.get(
                    "first_turn"
                )

                if player_id is None:
                    player_id = "P2"

                print(
                    "\nGame started!"
                )

                for player in players:
                    print(
                        f"{player['player_id']}: "
                        f"{player['player_name']} "
                        f"({player['symbol']})"
                    )

                print(
                    f"You are {player_id}"
                )

                display_board(board)

                if first_turn == player_id:
                    print(
                        "Your turn."
                    )

                    request_number = send_move(
                        client_socket,
                        request_number,
                        game_id,
                        player_id,
                        state_version
                    )

                else:
                    print(
                        "Waiting for the other "
                        "player's move..."
                    )

            elif msg_type == "STATE_UPDATE":
                game_id = response.get(
                    "game_id",
                    game_id
                )

                state_version = response.get(
                    "state_version",
                    state_version
                )

                payload = response.get(
                    "payload",
                    {}
                )

                board = payload.get(
                    "board",
                    []
                )

                current_turn = payload.get(
                    "current_turn"
                )

                print(
                    "\nGame state updated."
                )

                if board:
                    display_board(board)

                if current_turn == player_id:
                    print(
                        "Your turn."
                    )

                    request_number = send_move(
                        client_socket,
                        request_number,
                        game_id,
                        player_id,
                        state_version
                    )

                else:
                    print(
                        "Waiting for the other "
                        "player's move..."
                    )

            elif msg_type == "ERROR":
                payload = response.get(
                    "payload",
                    {}
                )

                error_message = payload.get(
                    "message",
                    "Unknown error"
                )

                print(
                    f"Server error: "
                    f"{error_message}"
                )

                if error_message in (
                    "Board position is already occupied",
                    "Row and column must be between 0 and 2"
                ):
                    print(
                        "Try another position."
                    )

                    request_number = send_move(
                        client_socket,
                        request_number,
                        game_id,
                        player_id,
                        state_version
                    )

            elif msg_type == "GAME_OVER":
                game_id = response.get(
                    "game_id",
                    game_id
                )

                state_version = response.get(
                    "state_version",
                    state_version
                )

                payload = response.get(
                    "payload",
                    {}
                )

                board = payload.get(
                    "board"
                )

                if board:
                    display_board(board)

                result = payload.get(
                    "result",
                    "UNKNOWN"
                )

                print(
                    f"Game over: {result}"
                )

                winner = payload.get(
                    "winner_player_id"
                )

                if winner is not None:
                    print(
                        f"Winner: {winner}"
                    )

                    if winner == player_id:
                        print(
                            "You won!"
                        )

                    else:
                        print(
                            "The other player won."
                        )

                scores = payload.get(
                    "scores"
                )

                if scores is not None:
                    print(
                        f"Scores: {scores}"
                    )

                break

            else:
                print(
                    f"Received message: "
                    f"{response}"
                )

    except ConnectionRefusedError:
        print(
            "Could not connect to the server."
        )

    except (
        ConnectionResetError,
        BrokenPipeError,
        OSError
    ) as error:
        print(
            f"Connection error: {error}"
        )

    finally:
        try:
            client_socket.close()

        except OSError:
            pass


if __name__ == "__main__":
    main()