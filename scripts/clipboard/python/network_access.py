#!/usr/bin/env python

import os, re, socket, struct, sys

# This is a pristine copy of the access functions that have made their
#  way into quite a few of my Python network scripts.

# Colours

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
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

# Network Access Class
# Required modules: re, socket, struct, sys
###

class NetAccess:
    # Basic IPv4 CIDR syntax check
    REGEX_INET4_CIDR='^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

    def __init__(self):
        self.errors = []
        self.allowed_addresses = []
        self.allowed_networks = []
        self.denied_addresses = []
        self.denied_networks = []

    def add_access(self, addr_list, net_list, candidate):
        candidate = candidate.strip()
        if re.match(self.REGEX_INET4_CIDR, candidate):
            good, net, bits = self.ip_validate_cidr(candidate)
            if good:
                # No error
                net_list.append((candidate, net, bits))
        else:
            good, a, astr = self.ip_validate_address(candidate)
            if good:
                # No error
                addr_list.append((a, candidate, astr))
        return good

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
                    print_notice("%s %s: %s" % (action, title, colour_text(address, COLOUR_GREEN)))
                else:
                    print_notice("%s %s: %s (%s)" % (action, title, colour_text(address, COLOUR_GREEN), colour_text(ip, COLOUR_GREEN)))

    # Credit for initial IP functions: http://code.activestate.com/recipes/66517/

    def ip_strton(self, ip):
        # Convert decimal dotted quad string integer
        a,b,c,d = struct.unpack('BBBB', socket.inet_aton(ip))
        return (a << 24) + (b << 16) + (c << 8) + d

    def ip_validate_address(self, candidate):
        try:
            ip = socket.gethostbyname(candidate)
            return (True, self.ip_strton(ip), ip)
        except socket.gaierror:
            self.errors.append("Unable to resolve: %s" % colour_text(candidate, COLOUR_GREEN))
            return (False, None, None)

    def ip_validate_cidr(self, candidate):
        a = candidate.split("/")[0]
        m = int(candidate.split("/")[1])

        try:
            # Will either succeed or throw an exception
            ip = self.ip_strton(socket.gethostbyname(a))
            if m <= 32:
                return (True, ip, 32 - m)
        except socket.gaierror:
            pass
        self.errors.append("Invalid CIDR address: %s" % colour_text(candidate, COLOUR_GREEN))
        return (False, None, None)

    def is_allowed(self, address):
        # Blacklist/Whitelist filtering
        allowed = True

        if len(self.allowed_addresses) or len(self.allowed_networks):
            # Whitelist processing, address is not allowed until it is cleared.
            allowed = False
            # Compare string-form against allowed addresses
            if address in [a[2] for a in self.allowed_addresses]:
                allowed = True
            else:
                # Try checking allowed networks
                ip = self.ip_strton(address)
                for net, bits in [(n[1], n[2]) for n in self.allowed_networks]:
                    if (net >> bits) == (ip >> bits):
                        allowed = True
                        break

        if allowed and len(self.denied_addresses) or len(self.denied_networks):
            # Blacklist processing. A blacklist argument one-ups a whitelist argument in the event of a conflict
            # Do not bother to check the blacklist if the address is already denied.

            if address in [a[2] for a in self.denied_addresses]:
                allowed = False
            else:
                # Try checking denied networks
                ip = self.ip_strton(address)
                for net, bits in [(n[1], n[2]) for n in self.denied_networks]:
                    if (net >> bits) == (ip >> bits):
                        allowed = False
                        break
        return allowed

    def load_access_file(self, fn, path, header):
        if not os.path.isfile(path):
            self.errors.append("Path to %s file does not exist: %s" % (header, colour_text(path, COLOUR_GREEN)))
            return False
        with open(path) as f:
            for l in f.readlines():
                fn(l)

    def load_blacklist_file(self, path):
        return self.load_access_file(self.add_blacklist, path, "blacklist")

    def load_whitelist_file(self, path):
        return self.load_access_file(self.add_whitelist, path, "whitelist")

# Demonstration of access-list
if __name__ == "__main__": # pragma: no cover
    acc = NetAccess()

    acc.add_whitelist("127.0.0.1")
    acc.add_whitelist("10.11.12.13")
    acc.add_blacklist("10.11.12.13/24")
    acc.announce_filter_actions()
    for i in ["127.0.0.1", "10.11.12.13", "1.2.3.4"]:
        if acc.is_allowed(i):
            word = "Allowed"
        else:
            word = "Denied"
        print("Test: %s address %s%s%s" % (word, COLOUR_GREEN, i, COLOUR_OFF))
