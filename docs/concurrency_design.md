# Server Concurrency Architecture

## Concurrency Model

I chose a multi-threaded server design for this project. The server will use a separate worker thread for each connected client, so one client does not block the other client while waiting for data.

The main server thread will listen for new connections and accept them. After a client connects, the server will create a worker thread for that client socket. Since both client threads can access the same game state, shared game data will need to be protected when it is being changed.

## Server Connection Lifecycle

The main server thread listens for incoming TCP connections. When a client connects, the server accepts the connection and creates a new worker thread for that client.

The worker thread handles messages from that client until the connection ends. If the client disconnects normally, reaches TCP EOF, or has a socket error, the server cleans up that connection.

The main server thread continues listening for other clients while the worker threads handle the connected players.

## Shared Game State

Both player threads need access to the same Tic-Tac-Toe game. Because of this, some information is shared between the threads.

The shared data includes the board, current player's turn, player information, game status, score information, and the connected client socket list.

The client threads should not keep separate copies of the official game state. The server keeps the official state so both players always use the same game information.

## Thread Safety

Since two worker threads can access the same game, they could try to change shared data at the same time. I will use a `threading.Lock` to protect changes to the shared game state.

A worker thread must acquire the lock before checking and changing shared game data. After the operation is finished, the thread releases the lock so another worker thread can use it.

The lock will protect operations such as validating a move, updating the board, changing the current turn, ending the game, and updating scores.

The connected client list is also shared server data. When a client is added or removed, that change should happen while the lock is held so another worker thread does not read the list while it is being changed.

## Move Critical Section

Processing a move needs to happen as one protected operation. The worker thread will acquire the lock before checking the player's turn, checking the board position, and updating the game state.

If the move is valid, the server updates the board, changes the turn, and updates the state version before releasing the lock. If the move is invalid, the board is not changed.

This prevents both player threads from making a move against the same game state at the same time.

## Score Synchronization

The server is responsible for keeping the official score information. A client does not calculate or change the score on its own.

When a game ends, the server determines the result and updates the score while the shared game state is protected. This prevents two threads from changing the score at the same time.

After the score is updated, the server can send the newest game result and score information to the connected clients.

## Client Synchronization

Both clients need to see the same official game state. After the server accepts a valid move, it sends the updated state to both players.

The server's `state_version` increases when an accepted move changes the game state. This helps the server and clients know which board state is the newest.

Invalid moves do not change the board or increase the state version. The server sends an `ERROR` back to the client that made the invalid request.

## Race Conditions

Without synchronization, both client threads could read the same board state before either one updates it. This could allow two moves to be processed using old information.

The lock prevents this by allowing only one worker thread at a time to check and modify the shared game state.

For example, if both players send a move at almost the same time, one thread finishes its move first. The second thread then checks the updated board and current turn before making any changes.

## Thread Responsibilities

The main server thread is responsible for accepting new TCP connections.

Each worker thread is responsible for receiving and handling messages from one connected client.

The worker threads share the official game state, but changes to that state must go through the protected section. This keeps networking work separate from shared game updates.
