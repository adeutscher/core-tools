#!/usr/bin/python

# A likely over-engineered script to relay UDP datagrams from one host to multiple targets.
# I mostly made this to work with my desktop-notify-relay.py script and its audio-playing cousin.
# Combined with this script I can send notifications to multiple machines at once in case I'm jumping between screens.
# Uses the same whitelist/blacklist system as my other Python network scripts to filter input before it gets multiplied.

import getopt, os, re, socket, struct, sys, time

def __print_message(colour, header, message):
    print "%s[%s]: %s" % (colour_text(colour, header), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

def colour_text(colour, text):
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def enable_colours(force = False):
    global COLOUR_PURPLE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_PURPLE = '\033[1;35m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_PURPLE = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_BLUE = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

#
# Common Message Functions
###

def print_denied(message):
    __print_message(COLOUR_RED, "Denied", message)

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    __print_message(COLOUR_RED, "Error", message)

def print_notice(message):
    __print_message(COLOUR_BLUE, "Notice", message)

def print_skipped(message):
    __print_message(COLOUR_RED, "Skipped", message)

def print_usage(message):
    __print_message(COLOUR_PURPLE, "Usage", message)

# Network Access Class
# Required modules: re, socket, struct, sys
###

class NetAccess:
    # Basic IPv4 CIDR syntax check
    REGEX_INET4_CIDR='^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

    def __init__(self):
        self.allowed_addresses = []
        self.allowed_networks = []
        self.denied_addresses = []
        self.denied_networks = []

    def add_access(self, addr_list, net_list, candidate):
        error = False
        if re.match(self.REGEX_INET4_CIDR, candidate):
            e, n = self.ip_validate_cidr(candidate)
            error = e
            if not e:
                # No error
                net_list.append((n, candidate))
        else:
            e, a, astr = self.ip_validate_address(candidate)
            error = e
            if not e:
                # No error
                addr_list.append((a, candidate, astr))
        return error

    def add_blacklist(self, candidate):
        return self.add_access(self.denied_addresses, self.denied_networks, candidate)

    def add_whitelist(self, candidate):
        return self.add_access(self.allowed_addresses, self.allowed_networks, candidate)

    def announce_filter_actions(self):
        for action, address_list, network_list in [("Allowing", self.allowed_addresses, self.allowed_networks), ("Denying", self.denied_addresses, self.denied_networks)]:
            l = []
            l.extend([("address", s, i) for n, s, i in address_list])
            l.extend([("network", s, s) for n, s in network_list])

            for title, ip, address in l:
                if ip == address:
                    print "%s %s: %s%s%s" % (action, title, COLOUR_GREEN, address, COLOUR_OFF)
                else:
                    print "%s %s: %s%s%s (%s%s%s)" % (action, title, COLOUR_GREEN, address, COLOUR_OFF, COLOUR_GREEN, ip, COLOUR_OFF)

    # Credit for initial IP functions: http://code.activestate.com/recipes/66517/

    def ip_make_mask(self, n):
        # Return a mask of n bits as a long integer
        return (2L<<n-1)-1

    def ip_strton(self, ip):
        # Convert decimal dotted quad string to long integer
        return struct.unpack('<L',socket.inet_aton(ip))[0]

    def ip_network_mask(self, ip, bits):
        # Convert a network address to a long integer
        return self.ip_strton(ip) & self.ip_make_mask(int(bits))

    def ip_addrn_in_network(self, ip, net):
        # Is a numeric address in a network?
        return ip & net == net

    def ip_validate_address(self, candidate):
        try:
            ip = socket.gethostbyname(candidate)
            return (False, self.ip_strton(ip), ip)
        except socket.gaierror:
            print_error("Unable to resolve: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF))
            return (True, None, None)

    def ip_validate_cidr(self, candidate):
        a = candidate.split("/")[0]
        m = candidate.split("/")[1]
        try:
            if socket.gethostbyname(a) and int(m) <= 32:
                return (False, self.ip_network_mask(a, m))
        except socket.gaierror:
            pass
        print_error("Invalid CIDR address: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF))
        return (True, None)

    def is_allowed(self, address):
        # Blacklist/Whitelist filtering
        allowed = True

        if len(self.allowed_addresses) or len(self.allowed_networks):
            # Whitelist processing, address is not allowed until it is cleared.
            allowed = False

            if address in [a[2] for a in self.allowed_addresses]:
                allowed = True
            else:
                # Try checking allowed networks
                cn = self.ip_strton(address)
                for n in [n[0] for n in self.allowed_networks]:
                    if self.ip_addrn_in_network(cn, n):
                        allowed = True
                        break

        if allowed and len(self.denied_addresses) or len(self.denied_networks):
            # Blacklist processing. A blacklist argument one-ups a whitelist argument in the event of a conflict
            # Do not bother to check the blacklist if the address is already denied.

            if address in [a[2] for a in self.denied_addresses]:
                allowed = False
            else:
                # Try checking denied networks
                cn = self.ip_strton(address)
                for n in [n[0] for n in self.denied_networks]:
                    if self.ip_addrn_in_network(cn, n):
                        allowed = False
                        break
        return allowed

    def load_access_file(self, fn, path, header):
        if not os.path.isfile(path):
            print_error("Path to %s file does not exist: %s%s%s" % (header, COLOUR_GREEN, path, COLOUR_OFF))
            return False
        with open(path) as f:
            for l in f.readlines():
                fn(l)

    def load_blacklist_file(self, path):
        return self.load_access_file(self.add_blacklist, path, "blacklist")

    def load_whitelist_file(self, path):
        return self.load_access_file(self.add_whitelist, path, "whitelist")

#
# Script Functions
###

DEFAULT_LISTEN_PORT = 2222
DEFAULT_TARGET_PORT = 1234
DEFAULT_BIND = "0.0.0.0"
DEFAULT_SHORT_MESSAGE_THRESHOLD = 127

TITLE_BIND = "bind address"
TITLE_LISTEN_PORT = "listen port"
TITLE_TARGET_PORT = "target port"

def do_relay():

    # Save constant lookups
    port = args.get(TITLE_LISTEN_PORT, DEFAULT_LISTEN_PORT)
    bind = args.get(TITLE_BIND, DEFAULT_BIND)

    sockobj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Bind socket to local host and port
    try:
        sockobj.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockobj.bind((bind, port))
    except socket.error as msg:
        print_error('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
        exit(1)

    # Keep accepting new messages
    while True:
        data, addr = sockobj.recvfrom(65535)

        # Blacklist/Whitelist filtering
        allowed = access.is_allowed(addr[0])
        header = "%s[%s][%s]" % (colour_text(COLOUR_GREEN, addr[0]), colour_text(COLOUR_BOLD, time.strftime("%Y-%m-%d %k:%M:%S")), colour_text(COLOUR_BOLD, readable_bytes(len(data))))

        if not allowed:
            # Not allowed
            print_denied("%s (%s)" % (header, colour_text(COLOUR_RED, "Ignored")))
            continue


        local_addresses = socket.gethostbyname_ex(socket.gethostname())[2]

        relayed = 0
        for addr in targets:
            if port == addr[1] and (addr[0].startswith("127.") or (addr in local_addresses and bind in ["0.0.0.0", addr[0]])):

                # Double-check for a short loop in case addresses have changed since the script was invoked.
                # See within process_arguments() for comments describing check reasoning.

                print_skipped("%s (%s)" % (header, colour_text(COLOUR_RED, "Potential short loop: %s" % colour_text(COLOUR_GREEN, addr[0]))))
                continue

            sockobj.sendto(data, addr)
            relayed += 1

        if relayed != len(targets):
            footer = " (Sent to %s/%s targets)" % (colour_text(COLOUR_BOLD, relayed), colour_text(COLOUR_BOLD, len(targets)))
        else:
            footer = ""

        if len(data) <= DEFAULT_SHORT_MESSAGE_THRESHOLD and re.match('^[ -~]{1,}$', data):
            # Data does not to contain multiple lines or unprintables.
            print_notice("%s%s: %s" % (header, footer, data.strip()))
        else:
            # Data seems be long or contains multiple lines or unprintables.
            print_notice("%s%s" % (header, footer))

def hexit(code = 0):
    print_usage("./%s [-a allow-address/range] [-A allow-list-file] [-b bind-address] [-d deny-address/range] [-D deny-list-file] [-h] [-p listen-port] [-t target-port] target-address [target-address-b ...]" % os.path.basename(sys.argv[0]))
    exit(code)

def process_arguments():
    global args
    args = {}
    global access
    access = NetAccess()
    raw_ints = {}

    try:
        opts, operands = getopt.gnu_getopt(sys.argv[1:],"a:A:b:d:D:hp:t:")
    except getopt.GetoptError as e:
        print "GetoptError: %s" % e
        hexit(1)

    for opt, arg in opts:
        if opt in ("-a"):
            access.add_whitelist(arg)
        elif opt in ("-A"):
            access.load_whitelist_file(arg)
        elif opt in ("-b"):
            args[TITLE_BIND] = arg
        elif opt in ("-d"):
            access.add_blacklist(arg)
        elif opt in ("-D"):
            access.load_blacklist_file(arg)
        elif opt in ("-h"):
            hexit(0)
        elif opt in ("-p"):
            raw_ints[TITLE_LISTEN_PORT] = arg
        elif opt in ("-t"):
            raw_ints[TITLE_TARGET_PORT] = arg

    for key in [TITLE_LISTEN_PORT, TITLE_TARGET_PORT]:
        if key not in raw_ints:
            continue
        try:
            args[key] = int(raw_ints[key])
        except ValueError:
            print_error("Invalid %s value: %s" % (colour_text(COLOUR_BOLD, key), colour_text(COLOUR_BOLD, raw_ints[key])))

    if not operands:
        print_error("No target addresses defined.")
    else:
        local_addresses = socket.gethostbyname_ex(socket.gethostname())[2]

        for addr in operands:
            res = access.ip_validate_address(addr)
            if res[0]:
                continue # Error in resolving IP address.

            display = "%s (%s)" % (colour_text(COLOUR_GREEN, res[2]), colour_text(COLOUR_GREEN, addr))

            if args.get(TITLE_LISTEN_PORT, DEFAULT_LISTEN_PORT) == args.get(TITLE_TARGET_PORT, DEFAULT_TARGET_PORT) and (res[2].startswith("127.") or (res[2] in local_addresses and args.get(TITLE_BIND, DEFAULT_BIND) in ["0.0.0.0", addr[0]])):

                # If our source port is our target port, then check for an immediate loop.
                # With a basic relay, not much we can do to avoid some joker setting up
                # a more sophisticated loop with multiple relay instances, though...
                # The "solution" to this would be to add some sort of wrapper protocol,
                #  but that would have two problems:
                #    * Potentially clipping off larger payloads
                #    * Would require an "exit" server, which sort of
                #        misses the point of a quick-and-dirty relay.

                # The proper, sophisticated way to do the check
                # for whether or not we are targetting a loopback address
                # would be to co-opt the methods of NetAccess class
                # to check the address numerically. However, since we
                # are dealing with the static 127.0.0.0/8 range, a
                # startswith check for the 4 bytes of "127." will be faster
                # than doing a bunch of conversions.

                print_error("Target port is equal to destination port and address is a local address (avoiding a loop): %s" % display)
                continue

            targets.append((res[2], args.get(TITLE_TARGET_PORT, DEFAULT_TARGET_PORT)))

            if addr == res[2]:
                # Provided an IP address
                display_addresses.append(colour_text(COLOUR_GREEN, addr))
            else:
                # Provided some variety of domain name.
                display_addresses.append(display)

def readable_bytes(nbytes):
    units = ["B", "KB"]

    if nbytes > 1024:
        return "%.02f%s" % (float(nbytes)/1024, units[1])
    return "%d%s" % (nbytes, units[0])

def summarize_arguments():
    print_notice("Bind address: %s" % colour_text(COLOUR_GREEN, args.get(TITLE_BIND, DEFAULT_BIND)))
    print_notice("Listen port: %s" % colour_text(COLOUR_BOLD, "UDP/%d" % args.get(TITLE_LISTEN_PORT, DEFAULT_LISTEN_PORT)))
    print_notice("Target port: %s" % colour_text(COLOUR_BOLD, "UDP/%d" % args.get(TITLE_TARGET_PORT, DEFAULT_TARGET_PORT)))

    if len(display_addresses) > 1:
        wording = "addresses"
    else:
        wording = "address"

    print_notice("Relaying one-way datagrams to the following %s: %s" % (wording, ", ".join(display_addresses)))

if __name__ == "__main__":

    display_addresses = []
    targets = []
    process_arguments()

    if error_count:
        hexit(1)

    # Confirm the information to stdout.
    summarize_arguments()

    try:
        do_relay() # Set up the relay.
    except KeyboardInterrupt:
        print "",
        exit(130)
