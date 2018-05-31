#!/usr/bin/python

# Experimental script for creating manual routes for different websites by domain.
# The intent is to exempt particular domains from VPN redirection.

# Notes
####
#
# This is a reactive script that scrapes DNS replies from tshark output.
# A possible enhancement to this script would be to have it use Python's
#   PCAP module and parse responses itself without tshark.
#
# This script will also match any subdomains by default (e.g '-d reddit.com' would also catch 'example.reddit.com'.
# To only restrict the exact domains, use the '-o' switch.
#
# The script now invokes tshark on its own, but to do this the "old" way by piping into stdin, use the '-s' switch:
#   tshark -i tun0 -f 'port 53' -l 2> /dev/null | ./script.py -s ...
#

import getopt, os, re, subprocess, sys

def enable_colours(force = False):
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_RED= '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_RED= ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_BLUE = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

TITLE_DEBUG = "debug"
TITLE_DOMAINS = "domains"
TITLE_GATEWAY="gw"
TITLE_INTERFACE = "if"
TITLE_ONLY_DOMAIN = "only"
TITLE_STDIN = "stdin"
TITLE_VPN_INTERFACE = "vpn-if"
args = { TITLE_DOMAINS : [] }

REGEX_INET4='^(([0-9]){1,3}\.){3}([0-9]{1,3})$'

# Magic numbers gained from counting tshark fields.

# A DNS packet will say DNS here
MAGIC_NUMBER_TSHARK_DNS = 5
# A DNS packet will start its description here
MAGIC_NUMBER_TSHARK_HEADER = 7
# DNS request will start here
MAGIC_NUMBER_TSHARK_RESPONSE_QUERY = 11
# First response will start here.
MAGIC_NUMBER_TSHARK_RESPONSE_CONTENTS = 13

# Load arguments and defaults
def handle_arguments():

    # Errors that have not been resolved.
    errors = []

    try:
        opts, operands = getopt.gnu_getopt(sys.argv[1:], "d:Dg:hi:osv:")
    except getopt.GetoptError as e:
        print >> sys.stderr, e
        hexit(1)

    for opt, optarg in opts:
        if optarg:
            optarg = optarg.strip()
        if opt == "-d":
            args[TITLE_DOMAINS].append(optarg)
        elif opt == "-D":
            args[TITLE_DEBUG] = True
        elif opt == "-h":
            hexit(0)
        elif opt == "-g":
            args[TITLE_GATEWAY] = optarg
        elif opt == "-i":
            args[TITLE_INTERFACE] = optarg
        elif opt == "-o":
            args[TITLE_ONLY_DOMAIN] = True
        elif opt == "-s":
            args[TITLE_STDIN] = True
        elif opt == "-v":
            args[TITLE_VPN_INTERFACE] = optarg

    # Domains Check
    if not args[TITLE_DOMAINS]:
        errors.append("No domains given (-d domain)")

    # Gateway Check
    if TITLE_GATEWAY not in args:
        # TODO: Make a best-effort guess at the default gateway IP. Can probably do this at the same time as the local interface TODO.
        errors.append("No gateway given (-g gateway-ip)")
    elif not re.match(REGEX_INET4, args[TITLE_GATEWAY]):
        errors.append("Invalid gateway IP: %s%s%s" % (COLOUR_GREEN, args[TITLE_GATEWAY], COLOUR_OFF))

    # Interface Check
    if TITLE_INTERFACE not in args:
        # TODO: Make a best-effort guess at the local interface. Can probably do this at the same time as the gateway IP TODO.
        errors.append("No interface given (-i interface)")
    elif not os.path.isdir("/sys/class/net/%s" % args[TITLE_INTERFACE]):
        errors.append("Interface does not exist: %s%s%s" % (COLOUR_BOLD, args[TITLE_INTERFACE], COLOUR_OFF))
    # VPN Interface Check
    if TITLE_VPN_INTERFACE not in args:
        errors.append("No VPN interface given (-v interface)")
    elif not os.path.isdir("/sys/class/net/%s" % args[TITLE_VPN_INTERFACE]):
        errors.append("VPN Interface does not exist: %s%s%s" % (COLOUR_BOLD, args[TITLE_VPN_INTERFACE], COLOUR_OFF))
    if errors:
        for e in errors:
            print "%s%s%s: %s" % (COLOUR_RED, "Error", COLOUR_OFF, e)
    return not errors

def hexit(exit_code=0):
    print "%s%s%s: ./%s -d domain -g gateway -i local-interface -v vpn-interface [-D] [-h]" % (COLOUR_BOLD, "Usage", COLOUR_OFF, os.path.basename(sys.argv[0]))
    print "  Uses DNS responses in tshark output to create exceptions to VPN redirection."
    print "  Multiple domains can be defined with multiple -d uses."
    print "  Interface should be natural interface, not VPN interface."
    print "  Above all: This is a REACTIVE script. It cannot outpace your first request, but will re-route to the gateway for later requests"
    exit(exit_code)

def main():
    if not handle_arguments():
        hexit(1)

    hosts = []
    debug = args.get(TITLE_DEBUG, False)
    only = args.get(TITLE_ONLY_DOMAIN, False)

    if args.get(TITLE_STDIN, False):
        print "Taking DNS replies from %s%s%s output via standard input" % (COLOUR_BLUE, "tshark", COLOUR_OFF),
    else:
        print "Taking DNS replies from %s%s%s output on %s%s%s" % (COLOUR_BLUE, "tshark", COLOUR_OFF, COLOUR_BOLD, args[TITLE_VPN_INTERFACE], COLOUR_OFF),
    print "and using them to create routes via %s%s%s on %s%s%s." % (COLOUR_GREEN, args[TITLE_GATEWAY], COLOUR_OFF, COLOUR_BOLD, args[TITLE_INTERFACE], COLOUR_OFF)
    if only:
        print "Domains:"
    else:
        print "Domains (and subdomains of):"
    for d in args[TITLE_DOMAINS]:
        print "  %s" % d

    mon = None
    if args.get(TITLE_STDIN, False):
        intake = sys.stdin
        if intake.isatty():
            print >> sys.stderr, "Invalid direct input source, must be piped in."
            exit(2)
    else:
        # TODO: I'm not sure about how to disable that packet count from tshark without also disabling stdout altogether.
        mon = subprocess.Popen(['tshark', '-n', '-l', '-f','udp and port 53', '-i', args[TITLE_VPN_INTERFACE]], stdout=subprocess.PIPE, stderr=open(os.devnull, 'w'))
        intake = mon.stdout

    try:
        while True:
            items = intake.readline().split()
            if not items:
                # EoF. Either:
                #  A: tshark process died. If this happened immediately, then the interface was never right to begin with...
                #  B: Standard Input from outside ended (-s)
                break
            elif len(items) <= MAGIC_NUMBER_TSHARK_RESPONSE_CONTENTS or items[MAGIC_NUMBER_TSHARK_DNS] != "DNS" or " ".join(items[MAGIC_NUMBER_TSHARK_HEADER:MAGIC_NUMBER_TSHARK_HEADER+3]) != "Standard query response" or items[MAGIC_NUMBER_TSHARK_RESPONSE_QUERY] != "A":
                # Not a DNS response (I think).
                # Either too short or expected contents do not match.
                # Skip line.
                continue

            domain = items[MAGIC_NUMBER_TSHARK_RESPONSE_QUERY+1]
            match = False
            if domain in args[TITLE_DOMAINS]:
                match = True
            elif not only:
                # Also check for subdomains of a tracked domain.
                for d in args[TITLE_DOMAINS]:
                    if domain.endswith(".%s" % domain):
                        match = True
                        break
            if not match:
                # Not a match for a watched domain.
                if debug:
                    # Print a message for debug output
                    print "Answer for %s%s%s A lookup (non-matching)" % (COLOUR_GREEN, domain, COLOUR_OFF)
                continue

            print "Answer for %s%s%s A lookup" % (COLOUR_GREEN, domain, COLOUR_OFF)
            response_mark = MAGIC_NUMBER_TSHARK_RESPONSE_CONTENTS
            while (response_mark + 1) < len(items) and items[response_mark] == "A":
                if items[response_mark+1] not in hosts:
                    print "  Add fallback route for %s%s%s via %s%s%s on %s%s%s" % (COLOUR_GREEN, items[response_mark+1], COLOUR_OFF, COLOUR_GREEN, args[TITLE_GATEWAY], COLOUR_OFF, COLOUR_BOLD, args[TITLE_INTERFACE], COLOUR_OFF)
                    if debug:
                        print "    Debug mode, not actually trying to add route."
                    else:
                        subprocess.Popen(['route', 'add', '-host', items[response_mark+1], 'gw', args[TITLE_GATEWAY], "dev", args[TITLE_INTERFACE]], stdout=sys.stdout, stderr=sys.stderr)
                    hosts.append(items[response_mark+1])
                response_mark += 2
    except KeyboardInterrupt as e:
        pass
    # End loop. Either ctrl-C or tshark died for some reason.
    if not debug:
        if hosts:
            print "Removing %d host route(s)" % len(hosts)
            for r in hosts:
                subprocess.Popen(['route', 'del', '-host', r], stdout=sys.stdout, stderr=sys.stderr)
        else:
            print "No host routes to remove."

if __name__ == "__main__":
    main()
