
Notes on TCP tunneling through SSH.

## Allowing TCP Tunneling

The `AllowTcpForwarding` option in `/etc/ssh/sshd_config` controls whether or not TCP forwarding is allowed.
It is often set to "yes" by default. Set to "no" if you want to block these shenanigans on a particular server.

## TCP Tunnel

"Connecting to port 9999 on the client's localhost goes to port 22 of the server's localhost":

    ssh -L 9999:localhost:22 server

"Connecting to port 8888 on the client's anything goes to port 80 of the server's localhost":

    ssh -L 0.0.0.0:8888:localhost:80 server

"Connecting to port 7777 on the client's 10.0.0.1 address goes to port 443 of the 10.2.2.2 address, through the server":

      ssh -L 10.0.0.1:8888:10.2.2.2:80 server

## Reverse TCP Tunnel

"When people connect on port 2222 of the server's localhost (or 0.0.0.0 if GatewayPorts is set to "yes" instead of the default "no"), it will go through the tunnel to port 22 on the client's localhost."

    ssh -R 2222:localhost:22 server
    
 "When people connect on port 2222 of the server's 10.11.12.13 address (if GatewayPorts is set to "yes" instead of the default "no"), it will go through the tunnel to port 22 on the client's localhost."

      ssh -R 10.11.12.13:2222:localhost:22 server

### Other Notes

* To allow reverse tunneling to bind to any port and not just localhost, set "GatewayPorts" to "yes" on the server.
* If GatewayPorts is set to "no", then the server will ignore any attempt to bind to a different address without an error, and just go to localhost.
* If GatewayPorts is set to "no", then the server will bind to 0.0.0.0 by default if no other address is given.
