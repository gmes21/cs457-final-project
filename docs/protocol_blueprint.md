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