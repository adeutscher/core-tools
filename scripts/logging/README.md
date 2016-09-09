
# Logging Scripts

Scripts for working with logging.

## Broadcast Server / Broadcast Client

This was a silly experiment in working with sockets and threading. The server will take any log message that it reads in from a Unix socket and broadcast it to any connected clients.

**Warning**: Obviously, this is hilariously insecure. Even rsyslog packets (which are also potentially transmitted over a network in plaintext) are at least going to a specific address instead of answering anyone who knocks.

Script Files:

* `broadcast-log-client.py`: Broadcast Server
*  broadcast-log-server.py : Broadcast Server
