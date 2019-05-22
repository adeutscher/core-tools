
# Network Benchmarking

This page describes various items that may be useful for assessing network performance.

## iperf3

`iperf3` is a network benchmarking tool used to test throughput. It can be installed from the following sources:

* In Fedora, it is installed via the `iperf3` package.
* The source code can be downloaded from the developer's website: https://iperf.fr/iperf-download.php

The command requires `iperf3` to be running both on a server and client machine.

### Server Usage

The server is fairly straightforwards.

Basic example:

    iperf3 -s

#### Useful Switches

##### Specifying Port

To set a different port:

    iperf3 -s -p 5201

##### Bind to Address

To bind to a particular address:

    iperf3 -s -B 10.20.30.40

##### UDP Mode

To listen on a UDP socket instead:

    iperf3 -s -u

### Client Usage

Basic example against a server at `10.20.30.40` (by default, an `iperf3` test will run for 10 seconds, reporting in every 1 second):

    iperf -c 10.20.30.40

#### Useful Switches

###### Specifying Port

To get to a server on a different port (default port is 5201):

    iperf -c 10.20.30.40 -p 5201

###### UDP Mode

To reach the server over UDP instead of the default TCP:

    iperf -c 10.20.30.40 -u

###### Test Length and Interval

To set a different test length (`-t <time>`) and/or the reporting interval (`-i <interval seconds>`) that runs for 30 seconds while reporting every 2s.

    iperf -c 10.20.30.40 -i 2 -t 30

###### Limit Test by Byte Count

To limit your test based on bytes transmitted instead of time, use the `-b n[KMG]` switch (note: The `man` pages only advertise `K` and `M` prefixes):

    iperf -c 10.20.30.40 -n 2G

Confirming that limiting by bytes is mutually exclusive with limiting by time.

###### Rate Limiting

To rate-limit your test rate, use the `-b n[KM]` switch:

    iperf -c 10.20.30.40 -b 300k

#### Public Servers

The `iperf` team offers a couple of public servers (https://iperf.fr/iperf-servers.php). These could be useful for troubleshooting issues with an internet connection:

North American Servers (Fremont, California):

* iperf.he.net (TCP/5201 and UDP/5201)
* iperf.scottlinux.com (TCP/5201 and UDP/5201)
