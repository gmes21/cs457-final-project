# AI Prompting and Constraint Strategy

## My Approach

I am using AI as an implementation assistant, but I do not want it deciding
the protocol for me. I designed the message types, JSON fields, framing rule,
server authority, and state transitions first.

When I use AI for code later, I will give it specific rules from my protocol
instead of asking it to create a generic client-server application.

The generated code must follow these decisions:

- Use TCP sockets.
- Encode application messages as UTF-8 JSON.
- Use a 4-byte unsigned big-endian length prefix before every JSON payload.
- Use only the message types defined in `protocol_blueprint.md`.
- Do not add or rename JSON fields.
- The server is the only side allowed to change the official game state.
- A client sends a `MOVE` request but never sends its own updated board.
- Invalid or out-of-turn moves return `ERROR` without changing the board.
- TCP EOF and socket failures must use the disconnect behavior defined in the protocol.
- State transitions must match `fsm_specification.md`.

I chose this approach because a general request such as "make a socket
Tic-Tac-Toe game" leaves too many design choices to the AI. By defining the
protocol first, I can constrain generated code to decisions I already made.

## Prompt 1: TCP Framing Functions

**Goal:** Generate only the send/receive framing functions for the protocol I
already designed.

**Prompt:**

```text
Write Python helper functions for sending and receiving messages over a TCP
socket. Follow these requirements exactly:

1. Messages are JSON encoded as UTF-8.
2. Every JSON payload is preceded by exactly 4 bytes.
3. The 4-byte header is an unsigned integer in big-endian network byte order.
4. The integer contains only the number of JSON payload bytes. The 4-byte
   header itself is not included in the length.
5. Use struct.pack("!I", length) when sending.
6. Use struct.unpack("!I", header)[0] when receiving.
7. Do not assume one recv() call returns all requested bytes.
8. Create a recv_exact(sock, n) helper that keeps reading until exactly n
   bytes have been collected.
9. If recv() returns b"", treat it as a closed TCP connection and return None.
10. Use sendall() when sending.
11. Do not use newline-delimited JSON.
12. Do not add timestamps, delimiters, extra headers, classes, threads,
    authentication, encryption, or any protocol fields that I did not request.

Generate only:
- recv_exact(sock, n)
- send_message(sock, message)
- receive_message(sock)

Do not create the client, server, or game logic.
```

### Why I constrained it this way

I already chose length-prefixed framing, so I do not want the AI choosing a
different message boundary method. I also limited the requested output to three
small functions because asking for the whole networking program at once could
cause the AI to make protocol decisions that are not in my design.

## Prompt 2: Validate Protocol Messages

**Goal:** Generate validation logic that accepts only the message structure I
already defined.

**Prompt:**

```text
Write a Python function named validate_message(message) for my Tic-Tac-Toe TCP
protocol.

Do not redesign the protocol. Follow these rules exactly.

Every message must contain these outer fields:

- version
- msg_type
- request_id
- game_id
- player_id
- state_version
- payload

Rules:

1. version must be integer 1.
2. msg_type must be one of:
   CONNECT, LOBBY_WAIT, GAME_START, MOVE, STATE_UPDATE, ERROR, DISCONNECT,
   GAME_OVER.
3. Do not accept any other message type.
4. Do not rename fields.
5. Do not add new fields.
6. request_id may be a string or null depending on the message type.
7. game_id may be null before a game exists.
8. player_id may be null for server messages that are not about one player.
9. state_version must be an integer.
10. payload must be a JSON object.

For MOVE specifically:

- msg_type must equal "MOVE".
- request_id must be a string.
- game_id must be a string.
- player_id must be a string.
- payload must contain exactly row and col.
- row must be an integer from 0 through 2.
- col must be an integer from 0 through 2.
- Do not validate whether the square is occupied here. That belongs to game
  state logic, not message schema validation.

Return a simple validation result that tells the caller whether the message is
valid and, if invalid, why.

Do not create socket code, game logic, classes, authentication, timestamps,
logging frameworks, or database code.
```

### Why I constrained it this way

I separated message-format validation from game-rule validation on purpose.
Checking whether `row` and `col` have the correct type and range belongs to the
protocol parser. Checking whether that board position is already occupied
belongs to the server's game state. This keeps the generated parser focused on
the schema I designed instead of letting it decide game behavior.