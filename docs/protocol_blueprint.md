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
| `request_id` | string | Gives a request or event its own identifier so a response or error can be traced back to it. |
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