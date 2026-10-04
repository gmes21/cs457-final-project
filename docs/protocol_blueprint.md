# Application Protocol Blueprint

## Project
Two-Player Tic-Tac-Toe over TCP

## Design Decision 1: Message Framing

I considered using newline-delimited JSON because it is simple and easy to read.
But I decided to use a 4-byte big-endian length prefix followed by a JSON payload.

I chose this because TCP is a continuous byte stream, so one recv() call may not
equal one complete message. With the length prefix, the receiver knows exactly
how many bytes belong to the next message.

## Design Decision 2: Server Controls the Game State

I decided that the server will be the only side allowed to change the official
Tic-Tac-Toe board.

The client can request a move, but it cannot decide by itself that the move was
accepted. The server will first check if the move is valid, if the correct player
made the move, and if the selected space is empty.

If the move is valid, the server updates the board and sends the new state to both
players. If the move is invalid, the server sends an ERROR message and the board
does not change.

I chose this design because both players should always receive the same official
game state from one trusted source.

## Design Decision 3: Allowed Message Types

I decided to keep the protocol limited to a fixed set of message types instead of
allowing free-form commands.

The allowed message types are:

- CONNECT
- LOBBY_WAIT
- GAME_START
- MOVE
- STATE_UPDATE
- ERROR
- DISCONNECT
- GAME_OVER

I chose these because each one represents a specific part of the game lifecycle.
The server will reject any message type that is not listed here.

I also decided that clients will never send STATE_UPDATE, GAME_START, or GAME_OVER.
Those messages can only come from the server because the server controls the official
game state.

## Message Direction and Purpose

| Message Type | Direction | Purpose |
|---|---|---|
| CONNECT | Client -> Server | Client asks to join the game using a player name. |
| LOBBY_WAIT | Server -> Client | Server tells the first player that it is waiting for a second player. |
| GAME_START | Server -> Clients | Server starts the match, assigns Player 1 / Player 2 roles, and sends the starting board. |
| MOVE | Client -> Server | Active player requests a move using a row and column. |
| STATE_UPDATE | Server -> Clients | Server sends the official board, active player, and current game state. |
| ERROR | Server -> Client | Server rejects an invalid, malformed, or out-of-turn request. |
| DISCONNECT | Client -> Server | Client tells the server that the player is intentionally leaving the game. |
| GAME_OVER | Server -> Clients | Server sends the final result such as win, draw, or forfeit. |

## Design Decision 4: Common JSON Message Structure

I decided that every message will use the same outer JSON structure. This gives
the client and server a predictable format before they look at the information
inside the message.

At first I considered using only `msg_type` and `payload`, but I decided to keep
a few additional fields because they have a specific purpose in the game. I did
not want to add fields just to make the protocol more complicated.

Every message contains these fields:

| Field | Type | Purpose |
|---|---|---|
| `version` | integer | Identifies the protocol version. For this project the value is `1`. |
| `msg_type` | string | Identifies which protocol message is being sent. It must be one of the allowed message types. |
| `request_id` | string or null | Identifies the client request connected to the message. It is `null` for server messages that are not a response to one specific client request. |
| `game_id` | string or null | Identifies which Tic-Tac-Toe game the message belongs to. It can be `null` before a game has started. |
| `player_id` | string or null | Identifies the player connected to the message. It can be `null` when the message is not about one specific player. |
| `state_version` | integer | Identifies the version of the official board state. It starts at `0` when the game begins. |
| `payload` | object | Contains the information that is specific to the message type. |

The general message structure is:

```json
{
  "version": 1,
  "msg_type": "MESSAGE_TYPE",
  "request_id": "REQ-001",
  "game_id": "GAME-001",
  "player_id": "P1",
  "state_version": 0,
  "payload": {}
}

## Message Schema 1: CONNECT

**Direction:** Client -> Server

**Purpose:**  
The client sends CONNECT when it first joins the server. The client provides a
player name, but the server is responsible for assigning the official player ID.

### Field Rules

| Field | Type | Rule |
|---|---|---|
| `version` | integer | Must be `1`. |
| `msg_type` | string | Must be `"CONNECT"`. |
| `request_id` | string | Created by the client to identify this connection request. |
| `game_id` | null | No game has been created yet. |
| `player_id` | null | The server has not assigned a player ID yet. |
| `state_version` | integer | Must be `0` because gameplay has not started. |
| `payload.player_name` | string | Name the player wants to use. It cannot be empty. |

### Example

```json
{
  "version": 1,
  "msg_type": "CONNECT",
  "request_id": "REQ-001",
  "game_id": null,
  "player_id": null,
  "state_version": 0,
  "payload": {
    "player_name": "Jason"
  }
}

## Message Schema 2: LOBBY_WAIT

**Direction:** Server -> Client

**Purpose:**  
The server sends LOBBY_WAIT after the first player connects but before a second
player has joined the game.

### Field Rules

| Field | Type | Rule |
|---|---|---|
| `version` | integer | Must be `1`. |
| `msg_type` | string | Must be `"LOBBY_WAIT"`. |
| `request_id` | string | Uses the request ID related to the player's connection. |
| `game_id` | string | Identifies the game lobby created by the server. |
| `player_id` | string | Player ID assigned by the server, such as `"P1"`. |
| `state_version` | integer | Must be `0` because the game has not started yet. |
| `payload.message` | string | Short message telling the player that the server is waiting for another player. |

### Example

```json
{
  "version": 1,
  "msg_type": "LOBBY_WAIT",
  "request_id": "REQ-001",
  "game_id": "GAME-001",
  "player_id": "P1",
  "state_version": 0,
  "payload": {
    "message": "Waiting for Player 2"
  }
}

## Message Schema 3: GAME_START

**Direction:** Server -> Clients

**Purpose:**  
The server sends GAME_START after two players have successfully joined. The server
assigns each player an ID and symbol, sends the empty board, and tells both players
who takes the first turn.

### Game Start Rules

I decided that the first player who connects becomes `P1` and uses `X`.

The second player becomes `P2` and uses `O`.

`P1` always takes the first turn. I chose this because it keeps the starting rule
simple and predictable instead of randomly choosing a player each game.

### Field Rules

| Field | Type | Rule |
|---|---|---|
| `version` | integer | Must be `1`. |
| `msg_type` | string | Must be `"GAME_START"`. |
| `request_id` | null | GAME_START is a server event sent to both players, not a response to one specific request. |
| `game_id` | string | Official game ID created by the server. |
| `player_id` | null | The message is sent to both players, so it is not tied to only one player. |
| `state_version` | integer | Must be `0` because no moves have been made yet. |
| `payload.players` | array | Contains information about both players. |
| `payload.players[].player_id` | string | Must be `"P1"` or `"P2"`. |
| `payload.players[].player_name` | string | Name provided when the player connected. |
| `payload.players[].symbol` | string | Must be `"X"` for P1 or `"O"` for P2. |
| `payload.first_turn` | string | Must be `"P1"` when the game starts. |
| `payload.board` | array | A 3 by 3 array representing the Tic-Tac-Toe board. Empty strings mean unused spaces. |

### Example

```json
{
  "version": 1,
  "msg_type": "GAME_START",
  "request_id": null,
  "game_id": "GAME-001",
  "player_id": null,
  "state_version": 0,
  "payload": {
    "players": [
      {
        "player_id": "P1",
        "player_name": "Jason",
        "symbol": "X"
      },
      {
        "player_id": "P2",
        "player_name": "Player2",
        "symbol": "O"
      }
    ],
    "first_turn": "P1",
    "board": [
      ["", "", ""],
      ["", "", ""],
      ["", "", ""]
    ]
  }
}

## Message Schema 4: MOVE

**Direction:** Client -> Server

**Purpose:**  
The active player sends MOVE to request placing their symbol in one location on
the board. The client is only requesting the move. The server decides if the move
is actually allowed.

### Move Rules

I decided to use row and column numbers from `0` to `2` because the board is a
3 by 3 array and this matches normal Python list indexes.

Before accepting a move, the server checks:

- The `game_id` belongs to an active game.
- The `player_id` belongs to that game.
- It is that player's turn.
- `row` is an integer from `0` to `2`.
- `col` is an integer from `0` to `2`.
- The selected board position is empty.
- The client's `state_version` matches the server's current state version.

If any of these checks fail, the server does not change the board.

### Field Rules

| Field | Type | Rule |
|---|---|---|
| `version` | integer | Must be `1`. |
| `msg_type` | string | Must be `"MOVE"`. |
| `request_id` | string | Created by the client to identify this move request. |
| `game_id` | string | Must identify the player's current game. |
| `player_id` | string | Must identify the player making the move. |
| `state_version` | integer | Must match the server's current board version. |
| `payload.row` | integer | Must be from `0` to `2`. |
| `payload.col` | integer | Must be from `0` to `2`. |

### Example

```json
{
  "version": 1,
  "msg_type": "MOVE",
  "request_id": "REQ-007",
  "game_id": "GAME-001",
  "player_id": "P1",
  "state_version": 2,
  "payload": {
    "row": 0,
    "col": 2
  }
}
...
I kept the MOVE payload small because the client only needs to tell the server
where it wants to move. The client does not send a new board or decide whether
the move was successful. That decision stays with the server.

## Message Schema 5: STATE_UPDATE

**Direction:** Server -> Clients

**Purpose:**  
The server sends STATE_UPDATE to both players after it accepts a valid move.
This message gives both clients the newest official board and tells them whose
turn comes next.

### State Update Rules

I decided that the server will send the complete board instead of only sending
the position that changed. Since a Tic-Tac-Toe board is very small, sending all
nine spaces keeps the client simple and makes sure both players have the same
board.

The `state_version` increases by one after every accepted move.

### Field Rules

| Field | Type | Rule |
|---|---|---|
| `version` | integer | Must be `1`. |
| `msg_type` | string | Must be `"STATE_UPDATE"`. |
| `request_id` | string | Matches the MOVE request that caused this update. |
| `game_id` | string | Identifies the active game. |
| `player_id` | string | Identifies the player whose move was accepted. |
| `state_version` | integer | New official state version after the accepted move. |
| `payload.board` | array | Current 3 by 3 board after the move. |
| `payload.next_turn` | string | Must be `"P1"` or `"P2"` and identifies who moves next. |

### Example

```json
{
  "version": 1,
  "msg_type": "STATE_UPDATE",
  "request_id": "REQ-007",
  "game_id": "GAME-001",
  "player_id": "P1",
  "state_version": 3,
  "payload": {
    "board": [
      ["", "", "X"],
      ["", "O", ""],
      ["", "", "X"]
    ],
    "next_turn": "P2"
  }
}
...
I used the same `request_id` as the accepted MOVE so it is clear which move
caused this board update. The server sends the same official board to both
players instead of letting each client update the game state on its own.

## Message Schema 6: ERROR

**Direction:** Server -> Client

**Purpose:**  
The server sends ERROR when it cannot accept or process a client's message.
The error is sent only to the client that caused the problem, and the official
game state does not change.

### Error Rules

I decided to include both an error code and a short message. The code gives the
client a consistent way to identify the problem, while the message makes the
error easier for the player to understand.

Some errors that can occur are:

- `MALFORMED_MESSAGE` - the message does not follow the required JSON format.
- `UNKNOWN_MESSAGE_TYPE` - the client sent a message type the protocol does not allow.
- `INVALID_MOVE` - the selected board position is not valid or is already used.
- `OUT_OF_TURN` - the player tried to move when it was not their turn.
- `STALE_STATE` - the client's state version does not match the server's current version.

An ERROR does not increase `state_version`.

### Field Rules

| Field | Type | Rule |
|---|---|---|
| `version` | integer | Must be `1`. |
| `msg_type` | string | Must be `"ERROR"`. |
| `request_id` | string or null | Uses the request ID of the message that caused the error when available. |
| `game_id` | string or null | Identifies the game if the client has already joined one. |
| `player_id` | string or null | Identifies the player if one has already been assigned. |
| `state_version` | integer | Contains the server's current state version. It does not increase because of an error. |
| `payload.code` | string | Short error code describing what went wrong. |
| `payload.message` | string | Human-readable explanation of the error. |

### Example

```json
{
  "version": 1,
  "msg_type": "ERROR",
  "request_id": "REQ-008",
  "game_id": "GAME-001",
  "player_id": "P2",
  "state_version": 3,
  "payload": {
    "code": "OUT_OF_TURN",
    "message": "It is not your turn."
  }
}
...
I kept the error response separate from STATE_UPDATE because an invalid request
should not look like a successful game change. The server returns the current
state version, but it leaves the board unchanged.