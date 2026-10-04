# Tic-Tac-Toe Game State Machine

## Server-Side State Design

I decided to keep the state machine based on what the server is actually doing
instead of making a separate state for every message.

The server uses these states:

- `INIT` - the server is ready but no game has started.
- `WAITING_FOR_PLAYERS` - the server waits until two players have connected.
- `GAME_START` - the server assigns P1/P2, X/O, and creates the empty board.
- `PLAYER_TURN` - the server waits for the current player to send a move.
- `EVALUATE_MOVE` - the server checks whether the requested move is allowed.
- `GAME_OVER` - the match has ended by win, draw, or forfeit.
- `CLEANUP` - sockets and game data are cleaned up before returning to the initial state.

I separated `PLAYER_TURN` and `EVALUATE_MOVE` because receiving a move and
deciding whether it is valid are two different jobs. An invalid move should
return an `ERROR` and go back to the same player's turn instead of changing
the board or crashing the game.

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> INIT

    INIT --> WAITING_FOR_PLAYERS: Server starts

    WAITING_FOR_PLAYERS --> WAITING_FOR_PLAYERS: First CONNECT / assign P1 as X / send LOBBY_WAIT
    WAITING_FOR_PLAYERS --> GAME_START: Second CONNECT / assign P2 as O
    WAITING_FOR_PLAYERS --> CLEANUP: Player disconnects / EOF / socket error

    GAME_START --> PLAYER_TURN: Send GAME_START / P1 takes first turn

    PLAYER_TURN --> EVALUATE_MOVE: Valid MOVE message received
    PLAYER_TURN --> PLAYER_TURN: Malformed or unknown message / send ERROR
    PLAYER_TURN --> PLAYER_TURN: Out-of-turn MOVE / send ERROR
    PLAYER_TURN --> GAME_OVER: Player disconnects / opponent wins by forfeit

    EVALUATE_MOVE --> PLAYER_TURN: Invalid position or occupied space / send ERROR
    EVALUATE_MOVE --> PLAYER_TURN: Valid move, game continues / send STATE_UPDATE / switch turn
    EVALUATE_MOVE --> GAME_OVER: Valid move causes win or draw
    EVALUATE_MOVE --> GAME_OVER: Player disconnects / opponent wins by forfeit

    GAME_OVER --> CLEANUP: Send GAME_OVER
    CLEANUP --> INIT: Close sockets and clear game data
```