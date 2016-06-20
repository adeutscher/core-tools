#!/usr/bin/python

import socket,sys,os

address=('127.0.0.1',4321)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock.sendto("Hello",address)

try:
    while True:
        message,server = sock.recvfrom(4096)
        if message[0] == 'd':
            # Data message, print it out
            print message[1:]
            sys.stdout.flush()
            temp = 0
        elif message[0] == 'k':
            # Internal message, knock request. Return the received data.
            sock.sendto("r%s"%message[1:],remote_server)
        elif message[0] == 'r':
            # Hello Reply
            print "Successfully registered."
            remote_server = server
        else:
            print "Unknown data: " % message

finally:
    sock.close()
