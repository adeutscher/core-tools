#!/usr/bin/python
 
import os,socket,sys, threading
import time

def main():
    
    socket_thread = SocketThread()
    network_thread = NetworkThread()
    try:
    
        socket_thread.start()
        network_thread.start()
    
        while socket_thread.isAlive() and network_thread.isAlive():
            time.sleep(0.1)
            
    finally:
        socket_thread.stop()
        network_thread.stop()
        exit(0)
      
class NetworkSocket():
    def __init__(self):
        self.address = ('0.0.0.0',4321)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,0)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.address)
        
class SocketThread(threading.Thread):
    
    def __init__(self):
        threading.Thread.__init__(self)

    def stop(self):
        self._Thread__stop()
        
    def run(self):
    
        local_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        # Optionally: Set umask to restrict the users that
        #     can access the socket that we are about to create.
        #os.umask(077)
        sock_path = '/tmp/log-sock'
        
        network_sock = network_container.socket

        try:
            if sys.stdout.isatty():
                print "Creating UNIX socket at \033[1;92m%s\033[0m." % sock_path
                print "\033[1;93mReminder\033[0m: Make sure that rsyslog is set to fire log messages at \033[1;92m%s\033[0m!" % sock_path
            else:
                print "Creating UNIX socket at %s" % sock_path
                print "Reminder: Make sure that rsyslog is set to fire log messages at %s!" % sock_path
            
            local_sock.bind(sock_path)
            # After a certain number of messages, we will send knock requests to each connected client.
            message_tally = 1
            
            while True:
                # Send the 
                message = local_sock.recv(4096)
                # I needed to manually flush output while
                #     I was piping the output of this script
                #     into other commands.
                #print "   %s" % message
                #sys.stdout.flush()
                
                if message_tally % 50 == 0:
                    # Generate data for checking against clients
                    # TODO: Replace with random data
                    knock_data = "reply-data"
                
                for address in clients.keys():
                    network_sock.sendto("d%s" % message,address)
                    
                    if message_tally % 50 == 0:
                        
                        if clients[address]['strikes'] > 3:
                            if sys.stdout.isatty():
                                print "De-registered client from: \033[1;92m%s\033[0m on \033[1;92mUDP/%s\033[0m" % address
                            else:
                                print "De-registered client from: %s on UDP/%s " % address
                                
                            del clients[address]
                            
                            continue
                        else:
                            network_sock.sendto("k%s" % knock_data,address)
                            clients[address]['knock-data'] = knock_data
                            clients[address]['strikes'] = clients[address]['strikes'] + 1
                
                if message_tally % 50 == 0:
                    message_tally = 0
                
                message_tally = message_tally + 1
        except Exception as e:
            print e
        finally:
            local_sock.shutdown(socket.SHUT_RDWR)
            local_sock.close()
            
            network_sock.close()
            os.remove(sock_path)
                    
class NetworkThread(threading.Thread):
    
    def __init__(self):
        threading.Thread.__init__(self)

    def stop(self):
        self._Thread__stop()
        
    def run(self):
        
        if sys.stdout.isatty():
            print "Hosting server on \033[1;92m%s\033[0m (port \033[1mUDP/%s\033[0m)" % network_container.address
        else:
            print "Hosting server on %s (port UDP/%s)" % network_container.address
        
        # Network socket
        sock = network_container.socket
        
        while True:
            data,address = sock.recvfrom(4096)
            
            #print 'received %s bytes from %s' % (len(data), address)
            #print "Data: %s" % data
            
            if address in clients:
                # Existing connection
                if data[0] == 'r':
                    # Reply to a knock request
                    # Validate
                    if data == "r%s" % clients[address]['knock-data']:
                        clients[address]['strikes'] = 0
                        clients[address]['knock-data'] = ''
                        #print "Received a reply from %s/%d" % address
                else:
                    print "Unknown data: " % data
            else:
                # New connection
                
                if sys.stdout.isatty():
                    print "Registered client: \033[1;92m%s\033[0m on \033[1mUDP/%s\033[0m " % address
                else:
                    print "Registered client: %s on UDP/%s " % address
                    
                            
                # Register new client
                clients[address] = { 'strikes': 0, 'knock-data': '' }
                sock.sendto("r",address)
            
if __name__ == "__main__":
    clients = {}
    
    # Store network socket in a global container in order to
    #     easily access it from both threads.
    network_container = NetworkSocket()
    
    main()
            
