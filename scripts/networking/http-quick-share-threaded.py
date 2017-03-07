#!/usr/bin/python   

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ThreadingMixIn
import os, sys

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

if __name__ == '__main__':
    bind_address = "0.0.0.0"
    bind_port = 8080
    server = ThreadedHTTPServer((bind_address, bind_port), SimpleHTTPRequestHandler)
    if sys.stdout.isatty():
        print "Sharing \033[1;92m%s\033[0m on %s:%d" % (os.path.realpath(os.getcwd()), bind_address, bind_port)
    else:
        print "Sharing %s on %s:%d" % (os.path.realpath(os.getcwd()), bind_address, bind_port)
    print "Starting server, use <Ctrl-C> to stop"
    server.serve_forever()
