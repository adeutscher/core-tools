#!/usr/bin/python

# A likely over-engineered script to relay UDP datagrams from one host to multiple targets.
# I mostly made this to work with my desktop-notify-relay.py script and its audio-playing cousin.

import os, re, socket, sys
import SimpleMessages as sm
sm.local_files.append(os.path.realpath(__file__))
# Commonly-used items from SimpleMessages
from SimpleMessages import args, colour_path, colour_text, print_notice

DEFAULT_PORT_LISTEN = 2222
DEFAULT_PORT_TARGET = 1234
DEFAULT_SHORT_MESSAGE_THRESHOLD = 127

TITLE_PORT_TARGET = "target port"

sm.set_default_port(DEFAULT_PORT_LISTEN)

args.add_opt(sm.OPT_TYPE_SHORT, "t", TITLE_PORT_TARGET, "Specify server bind port.", converter = int, default = DEFAULT_PORT_TARGET, default_announce = True)

targets = []
display_addresses = []

# A count of default items.
# If the item is greater than zero, then the summary will not print the target port.
default_count = 0

def print_skipped(message):
    sm._print_message(sm.COLOUR_RED, "Skipped", message)

def validate_targets(self):
    if not self.operands:
        return "No targets defined."

    global default_count

    local_addresses = socket.gethostbyname_ex(socket.gethostname())[2]

    bad_target_port = False
    errors = []
    evaluated_pairs = []

    for target in self.operands:
        items = target.split(":")

        if not items:
            continue
        elif not items[0]:
            addr = "127.0.0.1" # Assume localhost with a blank field.
        elif re.match(r"^\d+$", items[0]):
            errors.append("Invalid target address: %s" % colour_path(items[0]))
            continue # Error in resolving IP address.
        else:
            addr = items[0]

        # Handle IP address
        res = sm.access.ip_validate_address(addr) # Borrowing off of accesss
        if not res[0]:
            errors.append("Could not validate target address: %s" % colour_path(addr))
            continue # Error in resolving IP address.

        # Handle Ports
        if len(items) > 1:
            try:
                port = int(items[1])
            except ValueError:
                errors.append("Invalid port for address %s: %s" % (colour_path(addr), colour_text(items[1])))
                continue
        else:
            port = self[TITLE_PORT_TARGET]

        display = colour_path(res[2])
        if bad_target_port or port != self[TITLE_PORT_TARGET]:
            display += ":%s" % colour_path(port)
        if res[2] != addr:
             display = "%s (%s)" % (colour_path(addr), display)

        pair = (res[2], port)

        if pair in evaluated_pairs:
            sm.print_warning("An target was specified twice: %s" % display)
            continue
        evaluated_pairs.append(pair)

        if not bad_target_port and is_loop((res[2], port), (args[sm.TITLE_BIND], args[sm.TITLE_PORT])):

            # Check for loops against target port.
            # If there is a problem with the target port from up above in the arguments,
            # then we will not bother with this check because loop checking might give false positives.

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

            errors.append("Bad target (avoiding a loop): %s" % display)
            continue

        targets.append(pair)

        if addr == res[2]:
            # Provided an IP address
            if port == args[TITLE_PORT_TARGET]:
                default_count += 1
                display_addresses.append(colour_path(addr))
            else:
                display_addresses.append(colour_path("%s:%s" % (addr, port)))
        else:
            # Provided some variety of domain name.
            display_addresses.append(display)
    return errors
args.add_validator(validate_targets)

def summarize_arguments():
    if len(display_addresses) > 1:
        wording = "addresses"
    else:
        wording = "address"

    print_notice("Relaying one-way datagrams to the following %s: %s" % (wording, ", ".join(display_addresses)))
    print_notice("Bind address: %s" % colour_path(args[sm.TITLE_BIND]))
    print_notice("Listen port: %s" % colour_text("UDP/%d" % args[sm.TITLE_PORT]))

    global default_count
    if default_count:
        print_notice("Default target port: %s" % colour_text("UDP/%d" % args[TITLE_PORT_TARGET]))

    sm.announce_common_arguments(None)

def is_loop(target_addr, server_addr):
    if target_addr[1] != server_addr[1]:
        return False

    # Shortcut for loopback stuff.
    if target_addr[0].startswith("127."):
        return True

    local_addresses = socket.gethostbyname_ex(socket.gethostname())[2]
    # Target is a local address and we are bound to a local address.
    if target_addr[0] in local_addresses and server_addr[0] in ["0.0.0.0", target_addr[0]]:
        return True

    # Run through all options, not a loop.
    return False

class UdpMultiplierHandler:
    def __init__(self, session):
        # Save however slightly on constant lookups in args
        self.bind = args[sm.TITLE_BIND]
        self.port = args[sm.TITLE_PORT]
        self.sockobj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        session.reply = False
        self.session = session

    def handle(self, header,  data):

        # Intentionally getting our addresses each time.
        relayed = 0
        for addr in targets:
            if is_loop(addr, (self.bind, self.port)):
                # Double-check for a short loop in case addresses have changed since the script was invoked.
                # See within process_arguments() for comments describing check reasoning.
                print_skipped("%s (%s)" % (header, colour_text("Potential short loop: %s" % colour_path(addr[0]), sm.COLOUR_RED)))
                continue
            try:
                self.sockobj.sendto(data, addr)
            except socket.error as e:
                print_error("Error sending to target (%s:%s): %s" % (colour_path(addr[0]), colour_path(addr[1]), e))
            relayed += 1

        footer = ""
        if relayed != len(targets):
            # Only report on partial if we weren't able to send to every target.
            footer = " (Sent to %s/%s targets)" % (colour_text(relayed), colour_text(len(targets)))

        if len(data) <= DEFAULT_SHORT_MESSAGE_THRESHOLD and re.match('^[ -~]{1,}$', data):
            # Data does not to contain multiple lines or unprintables.
            print_notice("%s[%s]%s: %s" % (header, self.readable_bytes(len(data)),footer, data.strip()))
        else:
            # Data seems be long or contains multiple lines or unprintables.
            print_notice("%s[%s] %s" % (header, self.readable_bytes(len(data)), footer))

    def readable_bytes(self, nbytes):
        units = ["B", "KB"]
        if nbytes > 1024:
            return "%.02f%s" % (float(nbytes)/1024, units[1])
        return "%d%s" % (nbytes, units[0])

if __name__ == '__main__':
    sm.set_mode_udp_only()
    args.process(sys.argv)
    summarize_arguments()
    sm.serve(UdpMultiplierHandler)
