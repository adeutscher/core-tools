
# Networking Scripts

Scripts for networking management.

## access-point.py

Host or manually join a wireless access point.

Usage:

    ./access-point.py [-j] [-b bridge] [-B] [-c channel] [-i interface] [-I] [-p password] [-P] [-s SSID] [-S] [-w]

Arguments:

* `-j`: Join an access point instead of the default of hosting one.
* `-b bridge`: specify the bridge that a hosted access point is to be attached to.
* `-B`: collect bridge information when it is prompted for.
* `-c channel`: Sets the channel that the access point shall be hosted on.
* `-i interface`: Wireless interface to use when hosting or joining a WiFi network.
* `-I`: Collect wireless interface to use when prompted.
* `-p password`: Password to secure wireless interface with or to join network with.
* `-P`: Collect password when prompted.
* `-s ssid`: SSID network to host/join.
* `-S`: Collect SSID when prompted.
* `-w`: WEP mode. Should only really be used for a demonstration of why WEP should not be used.

## arp-toxscreen.py

Use `libpcap` to sniff for an imbredacted-namece of unsolicited ARP replies that might suggest ARP poisoning.

Usage:

    ./arp-toxscreen.py (-i interface||-f pcap-file) [-c script-cooldown] [-e expiry-time] [-h] [-s script] [-t report-threshold] [-v]

Arguments:

* `-f pcap-file`: PCAP file to listen to.
* `-i interface`: Network interface to listen on.
* `-e expiry-time`: Time after which to forget about ARP events.
* `-t threshold`: Threshold of imbredacted-nameces to at which point to consider a chain of unsolicited ARP replies to be a poisoning attempt.
* `-v`: Print additional information when any ARP request/reply is detected.
* `-s script`: processing script to run when a suspicious instance is detected.
* `-c cooldown`: Seconds between script runs per suspect.

## connections.sh

List incoming connections scraped from `netstat` or `conntrack -L` output.

Usage:

    ./connections.sh [-acChlLmoqrRsv] [matches]

By default, displays incoming connections. Use -o to display outgoing connections instead.

Specify matches to restrict output. For example, './connections.sh 192.168.0.0/24' would only show incoming connections from '192.168.0.0/24'. Switching to outgoing mode (-o) changes this to only display connections to matching subnets.

Valid matches:

* Interface: Addresses used by an interface will be used (use -r to take the interfaces' routes).
             If a bridge member is added by accident, then the bridge can be detected.
* IPv4 address (e.g. 192.168.0.1)
* IPv4 CIDR range (e.g. 192.168.0.0/24)
* Destination port number (e.g. 22).

Arguments:

* `-a`: All-mode. When using conntrack, do not restrict to just our device's addresses. Address checks will look at both ends of connection for a match.
* `-c`: Conntrack-mode. Use conntrack instead of netstat to detect connections. Must be root to use.
* `-C`: Force colours, even if output is not a terminal.
* `-h`: Help. Print a help menu and exit.
* `-l`: Show loopback connections, which are ignored by default. Will only work with netstat.
* `-L`: LAN-only mode. Only show incoming connections from LAN addresses (or to LAN addresses for outgoing mode).
* `-m`: Monitor mode. Constantly re-poll and print out connection information.
* `-o`: Outgoing mode. Display outgoing connections instead of incoming connections. Address checks will look at destination for a match.
* `-q`: "Quiet"-ish mode: Print information in barebones format (probably for future parsing).
* `-r`: Range mode. When specifying interfaces as a filter, use local CIDR ranges instead of just IPv4 addresses.
* `-R`: Remote-only mode: Only show incoming connections from non-LAN addresses (or to non-LAN addresses for outgoing mode).
* `-s`: Separate mode. Do not summarize connections, displaying individual ports.
* `-S`: Standard input. Collect input from stdin, assumed to be valid netstat or conntrack output
* `-v`: Verbose mode. Reach out to my `getlabel` script to attempt to resolve MAC addresses.
   * `-vv` will call `getlabel` with -v for additional information.

## dhclient-force.sh

Run `dhclient` while killing old instances. Made because `dhclient` has an annoying habit of staying around.

Usage:

    `./dhclient-force.sh interface`

## fix-dns.sh

A silly script to force-restart a self-hosted BIND9 server.

Usage:

    ./fix-dns.sh

## getlabel.sh

Use MAC addresses stored in a CSV file in order to identify a host. As a fallback, identify a vendor.

Usage:

    ./getlabel.sh [-chlv] subject [more-subjects]

A subject can be one of the following:

  * A MAC Address
  * An IPv4 address
  * An IPv4 CIDR range.

  IPv4 addresses and ranges must be at least partly within your local routes.

Arguments:

* `-c`: Force terminal colours. Useful if output is being stored temporarily before a confirmed terminal.
* `-h`: Show a help menu.
* `-l`: "Lazy" mode. Silence many errors and do not attempt to resolve MAC addresses that are not immediately in our ARP table.

This script reads off of a CSV file for its main data. The file is specified in the `INDEX_NETWORK_DATA` environment variable, and should be of the following format:

    category,type,mac-address,title,location,sublocation,description,notes
    My Devices,Desktop,aa:bb:cc:dd:ee:ff,My Desktop Machine,Home,A Desk,This is a Computer,

As a fallback to a label (or in verbose mode), the script draws off vendor information out of a pipe-delimited file. The file is specified in the `INDEX_VENDOR_DATA` environment variable, and should be of the following format:

    prefix  |vendor
    00:00:00|XEROX CORPORATION

I use the following to generate my vendor index using the IEEE website:

    curl -L "http://standards-oui.ieee.org/oui.txt" > oui.txt
    cat oui.txt | grep \(hex\) | awk -F"\t" '{print 0"|" }' | sed 's/   (hex)//g' | sed -r 's/^([A-Z1-90]{2})-([A-Z1-90]{2})-([A-Z1-90]{2})/\L\1:\2:\3/' | sed 's/\r//g' | sort > vendor-mac.txt

Other Notes:

* MAC addresses can be specified by prefix.

## http-quick-share-threaded.py

An expansion on the Python's SimpleHTTPServer module to have tidier output and a bit more general control.

Usage:

    ./http-quick-share-threaded.py [-a allow-address/range] [-A allow-list-file] [-b bind-address] [-d deny-address/range] [-D deny-list-file] [-h] [-l] [-n] [-p port] [-P] [-r] [-t]

Arguments:

* `-a address/range`: Network address or range to whitelist.
* `-A allow-list-file`: File containing addresses or ranges to whitelist.
* `-b bind`: Address to bind to.
* `-d address/range`: Network address or range to blacklist. Blacklists override conflicting whitelists.
* `-D allow-list-file`: File containing addresses or ranges to blacklist. Blacklists override conflicting whitelists.
* `-b bind`: Network address to bind to (default: `0.0.0.0`).
* `-h`: Print a help menu and exit.
* `-l` / `--local-links`: Only follow symbolic links that lead to within the shared directory.
* `-n` / `--no-links`: Do not follow any symbolic links.
* `-p port`: Port to listen on (default: `8080`).
* `-r`: Display items in reverse order.
* `-t`: Sort items by modification time instead of alphabetically.
* `--user user`: Required username.
* `--password password`: Required password.
* `--prompt`: Password prompt text.

## kill-incoming-ssh-sessions.sh

Kill all SSH sessions for a particular user.

Usage:

    ./kill-incoming-ssh-sessions.sh [other-user]

Other notes:

* By default, this will kill SSH sessions for the current user.

## ping-reliably.sh and ping-unreliably.sh

These two closely-related scripts are made to ping a destination until it eithre can (for `ping-reliably.sh`) or cannot (for `ping-unreliably.sh`) ping a server. I generally use this to confirm that a host or network link is/is-not down.

Usage:

    ping-reliably host [count]

Notes:

* The default count of required pings is `60`.

## rdp.py

A wrapper around `xfreerdp` command to more convenientlly deal with arguments (especially with the inconsistent arguments used by earlier versions of `xfreerdp`).

Usage:

    ./rdp.py server [-d domain] [-D] [-g HxW] [-h height] [-p password] [-P] [-u user] [-U] [-w width]

Arguments:

* `-d domain`: Domain of user to attempt to authenticate with.
* `-D`: Prompt for a domain.
* `-p domain`: Password of user to attempt to authenticate with.
* `-P`: Prompt for a password. Recommended if you are on a system where someone could snoop on your password.
* `-u domain`: Name of user to attempt to authenticate with.
* `-U`: Prompt for a username.
* `-h`: Display height.
* `-w`: Display width.
* `-g geometry`: Display both height and width in one argument. Format: `HxW`

The script reads defaults off of the following environment variables:

* `RDP_HEIGHT`: Set display height.
* `RDP_WIDTH`: Set display height.
* `RDP_DOMAIN`: Set user domain.
* `RDP_USER`: Set username.
* `RDP_PASSWORD`: Set user password (obviously, only use this on a system that you ABSOLUTELY trust).

Other notes:

* If necessary credentials are missing or incorrect then the RDP server will probably prompt the user to correct themselves.

## relay-tcp.sh and relay-udp.sh

These two related scripts are a wrapper around NMap's `ncat`, made to forward TCP connections or UDP datagrams respectively.

Usage:

    ./relay-tcp.sh local-port destination-address dest-port

## shuffle-if.sh

A wrapper around `macchanger` to shuffle a network interface's MAC address.

## ssh-compile-config.sh

Compile SSH information from different modules and place them into a SSH configuration file.

Usage:

    ./ssh-compile-config.sh [config-file]

Provide an file path as an argument to compile to a file other then `~/.ssh/config`.

For more information on this, see the [ssh/](/ssh/) directory `README.md` file.

## ssh-fix-permissions-core.sh and ssh-fix-permissions.sh

Lazy scripts to make sure that SSH configuration directories across different tool modules are private.

## ssl-expiry-check.sh

Read domains off of a CSV file and attempt confirm if they will be expiring soon.

Usage:

    ./ssl-expiry-check -f data-file [-s notification-hook]

CSV format: `domain,port,days-threshold,contacts`

Contacts are optional, and must be handled by a separate script.

Script arguments:

    ./script contact domain state expiry-time time-remaining

Assignments to uncomment and place into a script:

    CONTACT="${1}"     # Contact path
    DOMAIN="${2}"      # Domain examined
    STATE="${3}"       # Mode. Possible states: "expiring", "expiring SOON", or "expired"
    EXPIRY_TIME="${4}" # Expiry date
    REMAINING="${5}"   # Remaining time (human-readable)

## udp-multiplier-relay.py

Listen on a UDP port and forward datagrams received to other hosts.

Usage:

    ./udp-multiplier-relay.py [-a allow-address/range] [-A allow-list-file] [-b bind-address] [-d deny-address/range] [-D deny-list-file] [-h] [-p listen-port] [-t target-port] target-address [target-address-b ...]

Arguments:

* `-a address/range`: Network address or range to whitelist.
* `-A allow-list-file`: File containing addresses or ranges to whitelist.
* `-b bind`: Address to bind to.
* `-c`: Force colours, even if stdout is not a terminal.
* `-d address/range`: Network address or range to blacklist. Blacklists override conflicting whitelists.
* `-D allow-list-file`: File containing addresses or ranges to blacklist. Blacklists override conflicting whitelists.
* `-h`: Print a help menu and exit.
* `-p`: Port to listen on.
* `-t`: Target UDP port.

## update-repo.sh

Wrapper to update a `git` clone or `svn` checkout.

Usage:

    ./update-repo.sh ~/dev/repo.sh

## vnc-quick-share.sh

Wrapper around x11vnc for convenient sharing of an area:

Usage:

    ./vnc-quick-share [-c] [-d dimensions] [-h] [-l] [-m monitor] [-p passwd|-P] [-w]

Arguments:

* `-c`: Continue mode. Attempt to re-connect if `x11vnc` dies.
* `-d dimensions`: Specify a particular range. Format example: `279x213+2580+637`
* `-h`: Print help menu and exit.
* `-l`: List connected monitors and exit.
* `-m monitor`: Share a particular monitor.
* `-p password`: Password to "secure" VNC sharing with.
* `-P`: Prompt for a password to "secure" VNC sharing with.
* `-w`: Enable writing.
   * If writing is enabled, then a password will be required.

## vpn-domain-route-catcher.py

Experimental script for creating manual routes for different websites by domain. The intent is use DNS responses in tshark output to create exceptions to VPN redirection.

Usage:

    ./vpn-domain-route-catcher.py -d domain -g gateway -i local-interface -v vpn-interface [-D] [-h] [-o] [-s] [-t]

Arguments:

* `-d domain`: Domain to watch. Can be specified multiple times.
* `-D`: Debug mode. Do not actually add any detected routes. Also print slightly more output.
* `-g gateway`: Gateway IP to bypass routes through.
* `-h`: Print this help menu and exit.
* `-i local-interface`: Interface that local routes will be added on, bypassing VPN
* `-o`: Strict domain mode. Only add routes for domains that exactly match requested domains. Default behavior is to match requested domains and all their sub-domains.
* `-s`: Collect input from standard input (presumed to be tshark output). Example: tshark -i tun0 -f 'port 53' -l 2> /dev/null | ./script.py -s ...
* `-t`: Collect input directly tshark output invoked as a subprocess.
* `-v`: VPN interface. This is the interface that is expected to be able to see unencrypted DNS responses to drive route addition. Not required for standard input mode.

Above all: Remember that this is a REACTIVE script. It (probably) cannot outpace your first request, but will re-route to the gateway for later requests.

## wifi-list-raw.sh

Scrape wireless network information from `iw` command output.

Usage:

    ./wifi-list-raw.sh interface

## wifi-qr-maker.sh

Create QR codes for a WiFi network.

Usage:

    ./wifi-qr-maker.sh [-h] [-p PASSWORD] [-s SSID]

Arguments:

* `-h`: Print this help screen and exit.
* `-p`: Get the password as a command line argument (not recommended, but possible).
* `-s`: Set SSID via command line.

Note: If the SSID/password are not given as arguments, then you will be prompted to enter them.

## wol-manual.py

Standalone version of `wakeonlan`/`wol` commands.

Usage:

    ./wol-manual.py [-a target_address] [-h] ... MAC-ADDRESS ...

Arguments:

* `-a target_address`: Send to specific broadcast address .This is necessary when waking up a device on a different collision domain than your default gateway interface.
   * Example value: `192.168.100.0`
* `-h`: Display this help menu and exit.
* `-p port`: Select UDP port.


