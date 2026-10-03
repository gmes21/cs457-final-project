# Application Protocol Blueprint

## Project
Two-Player Tic-Tac-Toe over TCP

## Design Decision 1: Message Framing

I considered using newline-delimited JSON because it is simple and easy to read.
But I decided to use a 4-byte big-endian length prefix followed by a JSON payload.

I chose this because TCP is a continuous byte stream, so one recv() call may not
equal one complete message. With the length prefix, the receiver knows exactly
how many bytes belong to the next message.