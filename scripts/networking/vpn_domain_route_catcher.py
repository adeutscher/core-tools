#!/usr/bin/env python

# Experimental script for creating manual routes for different websites by domain.
# The intent is to exempt particular domains from VPN redirection.

# Notes
####
#
# This is a reactive script that scrapes DNS replies from pypcap or tshark output.
#
# This script will also match any subdomains by default (e.g '-d reddit.com' would also catch 'example.reddit.com'.
# To only restrict the exact domains, use the '-o' switch.
#
# For a list of options, use the -h switch.
#

from __future__ import print_function
import getopt, os, re, subprocess, struct, sys

#
# Common Colours and Message Functions
###


def _print_message(header_colour, header_text, message, stderr=False):
    f = sys.stdout
    if stderr:
        f = sys.stderr
    print(
        "%s[%s]: %s"
        % (
            colour_text(header_text, header_colour),
            colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN),
            message,
        ),
        file=f,
    )


def colour_text(text, colour=None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)


def enable_colours(force=False):
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

error_count = 0


def print_error(message):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, "Error", message)


def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ""
    if msg:
        sub_msg = " (%s)" % msg
    print_error(
        "Unexpected %s%s: %s"
        % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e))
    )


def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)


def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message)


TITLE_DEBUG = "debug"
TITLE_DOMAINS = "domains"
TITLE_GATEWAY = "gw"
TITLE_INTERFACE = "if"
TITLE_MODE = "mode"
TITLE_ONLY_DOMAIN = "only"
TITLE_VPN_INTERFACE = "vpn-if"

MODE_STDIN = 1
MODE_TSHARK = 2
MODE_PCAP = 3

args = {TITLE_DOMAINS: [], TITLE_MODE: MODE_PCAP}

REGEX_INET4 = '^(([0-9]){1,3}\.){3}([0-9]{1,3})$'

# Magic numbers gained from counting tshark fields.

# A DNS packet will say DNS title here
MAGIC_NUMBER_TSHARK_DNS = 5
# A DNS packet will start its description here
MAGIC_NUMBER_TSHARK_HEADER = 7
# DNS request will start here
MAGIC_NUMBER_TSHARK_RESPONSE_QUERY = 11
# First response will start here.
MAGIC_NUMBER_TSHARK_RESPONSE_CONTENTS = 13

PCAP_FILTER = 'udp and src port 53'


class DNSItem:
    points = []

    def _get_domain_string(self, data, point, points=None, debug=False):
        s = ""

        if points and point in points:
            return (s, point)

        points.append(point)

        while point < len(data):
            expected_length = ord(data[point])
            if not expected_length:
                break
            if expected_length == 0xC0:
                # Pointer to another record.
                point += 1
                subname, subpoint = self._get_domain_string(
                    data, ord(data[point]), points, debug
                )
                s += "%s." % subname
                break  # A pointer is considered to be the end of a record.
            point += 1
            s += "%s." % data[point : point + expected_length]
            point += expected_length
        return (s[:-1], point + 1)


class DNSAnswer(DNSItem):
    def __init__(self, data, point):
        self.point_start = point
        points = []
        self.domain, point = self._get_domain_string(data, point, points)
        self.answer_type = struct.unpack('!H', data[point : point + 2])[0]
        point += 2
        self.answer_class = struct.unpack('!H', data[point : point + 2])[0]
        point += 2
        self.ttl = struct.unpack('!L', data[point : point + 4])[0]
        point += 4
        self.data_length = struct.unpack('!H', data[point : point + 2])[0]
        point += 2
        self.data = data[point : point + self.data_length]
        point += self.data_length
        self.point_end = point


class DNSHeader:
    def __init__(self, data):
        self.build_data(data)

        point = 12
        self.domains = {}
        self.queries = []
        self.answers = []

        # Handle Questions
        for i in range(self.question_records):
            self.queries.append(DNSQuery(data, point))
            point = self.queries[len(self.queries) - 1].point_end

        # Handle Answers
        for i in range(self.answer_rrs):
            self.answers.append(DNSAnswer(data, point))
            point = self.answers[len(self.answers) - 1].point_end

        # NYI: Handling of authority RRs and additional RRs
        # Not needed for this script.

    def build_data(self, data):
        self.id = struct.unpack('!H', data[0:2])[0]
        self.flags = struct.unpack('H', data[2:4])[0]
        self.qr = self.flags & 0x1
        self.opcode = (struct.unpack('B', data[2:3])[0] >> 3) & 0xF
        self.aa = (self.flags >> 10) & 0x1
        self.tc = (self.flags >> 9) & 0x1
        self.rd = (self.flags >> 8) & 0x1
        self.ra = (self.flags >> 7) & 0x1
        self.opcode = (struct.unpack('B', data[3:4])[0] >> 4) & 0x7
        self.response_code = struct.unpack('B', data[3:4])[0] & 0xF
        self.question_records = struct.unpack('!H', data[4:6])[0]
        self.answer_rrs = struct.unpack('!H', data[6:8])[0]
        self.authoritative_rrs = struct.unpack('!H', data[8:10])[0]
        self.additional_rrs = struct.unpack('!H', data[10:12])[0]


class DNSQuery(DNSItem):
    def __init__(self, data, point):
        points = []
        self.point_start = point
        self.domain, point = self._get_domain_string(data, point, points)
        self.query_type = struct.unpack('!H', data[point : point + 2])[0]
        point += 2
        self.query_class = struct.unpack('!H', data[point : point + 2])[0]
        self.point_end = point + 2


class EthernetPacket:
    def __init__(self, data):
        self.destination = self._mac_bytes_to_str(data[0:6])
        self.source = self._mac_bytes_to_str(data[6:12])
        self.type = data[12:14]
        self.data = data[14:]

    def _mac_bytes_to_str(self, bytes):
        unpacked = struct.unpack('BBBBBB', bytes)
        result = ''
        for b in unpacked:
            result += '%02x:' % b
        return result[:-1]


class IPPacket:
    def __init__(self, data, ethernet):
        self.ethernet = ethernet
        self.version = (ord(data[0:1]) & 0xF0) >> 4
        self.header_len = (ord(data[0:1]) & 0x0F) * 32 / 8
        self.tos = ord(data[1:2])
        self.total_length = struct.unpack('!H', data[2:4])[0]
        self.identification = data[4:6]
        self.flags = ord(data[6:7]) & 0xE0
        self.reserved = self.flags & 0x20 == 0x20
        self.dont_fragment = self.flags & 0x40 == 0x40
        self.more_fragments = self.flags & 0x80 == 0x80
        self.fragment_offset = struct.unpack('!H', data[6:8])[0] & 0xFF1F
        self.ttl = ord(data[8:9])
        self.protocol = ord(data[9:10])
        self.checksum = data[10:12]
        self.source = ip_bytes_to_str(data[12:16])
        self.source_raw = struct.unpack('!I', data[12:16])[0]
        self.destination = ip_bytes_to_str(data[16:20])
        self.destination_raw = struct.unpack('!I', data[16:20])[0]
        self.data = data[20:]


class UDPPacket:
    def __init__(self, data, ip):
        self.ip = ip
        self.src = struct.unpack('!H', data[0:2])[0]
        self.dst = struct.unpack('!H', data[2:4])[0]
        self.length = struct.unpack('!H', data[4:6])[0]
        self.checksum = data[6:8]
        self.data = data[8 : self.length]


def add_routes_for_domain(domain, addresses):
    count = 0
    for address in addresses:
        if address not in hosts:
            count += 1
            print_notice(
                "  Add fallback route for %s via %s on %s"
                % (
                    colour_text(address, COLOUR_GREEN),
                    colour_text(args.get(TITLE_GATEWAY, "Undefined"), COLOUR_GREEN),
                    colour_text(args.get(TITLE_INTERFACE, "Undefined")),
                )
            )
            if debug:
                print_notice("    Debug mode, not actually trying to add a route.")
            else:
                run_command(
                    [
                        'route',
                        'add',
                        '-host',
                        address,
                        'gw',
                        args[TITLE_GATEWAY],
                        "dev",
                        args[TITLE_INTERFACE],
                    ]
                )
            hosts.append(address)
    if count:
        print(
            "Answer for %s A lookup (%s%s%s)"
            % (
                colour_text(domain, COLOUR_GREEN),
                COLOUR_GREEN,
                ("%s, %s" % (COLOUR_OFF, COLOUR_GREEN)).join(addresses),
                COLOUR_OFF,
            )
        )
    elif debug:
        print(
            "Answer for %s A lookup (already added)" % colour_text(domain, COLOUR_GREEN)
        )


def confirm_root_or_rerun():
    if not os.geteuid():
        # Already root, no need to continue.
        return

    cmd = list(sys.argv)
    cmd.insert(0, "sudo")

    print_notice(
        "We are not %s, so %s will be re-run through %s."
        % (
            colour_text("root", COLOUR_RED),
            colour_text(cmd[1], COLOUR_GREEN),
            colour_text(cmd[0], COLOUR_BLUE),
        )
    )

    # Run command. Do not set sudo_required because of the alternate message was printed above.
    exit(run_command(cmd))


def do_input_pipe(intake=sys.stdin):
    while True:
        items = intake.readline().split()
        if not items:
            # EoF. Either:
            #  A: tshark process died. If this happened immediately, then the interface was never right to begin with...
            #  B: Standard Input from outside ended (-s)
            break
        elif (
            len(items) <= MAGIC_NUMBER_TSHARK_RESPONSE_CONTENTS
            or items[MAGIC_NUMBER_TSHARK_DNS] != "DNS"
            or " ".join(
                items[MAGIC_NUMBER_TSHARK_HEADER : MAGIC_NUMBER_TSHARK_HEADER + 3]
            )
            != "Standard query response"
            or items[MAGIC_NUMBER_TSHARK_RESPONSE_QUERY] != "A"
        ):
            # Not a DNS response (I think).
            # Either too short or expected contents do not match.
            # Skip line.
            continue

        domain = items[MAGIC_NUMBER_TSHARK_RESPONSE_QUERY + 1]

        response_mark = MAGIC_NUMBER_TSHARK_RESPONSE_CONTENTS
        addresses = []
        while (response_mark + 1) < len(items) and items[response_mark] == "A":
            addresses.append(items[response_mark + 1])
            response_mark += 2

        examine_domain(domain, addresses)


def do_input_pcap():
    pcap_obj = pcap.pcap(
        name=args[TITLE_VPN_INTERFACE], promisc=True, immediate=True, timeout_ms=50
    )
    try:
        pcap_obj.setfilter(PCAP_FILTER)
    except:
        print_error("Illegal PCAP filter: %s" % colour_text(PCAP_FILTER))
        exit(1)
    pcap_obj.loop(0, do_input_pcap_callback)


def do_input_pcap_callback(ts, pkt, arg=None):
    e = EthernetPacket(pkt)
    ip = IPPacket(e.data, e)

    if ip.protocol != 0x11:
        return  # Non-UDP packet, sanity-checking filter

    udp = UDPPacket(ip.data, ip)

    if udp.src != 53:
        return  # Non-DNS port, sanity-checking filter

    try:
        dns = DNSHeader(udp.data)
    except Exception as e:
        print_error("Malformed DNS response?")
        raise

    if not (dns.qr and dns.answer_rrs):
        return  # Not a response with answers

    # Format answers into a dictionary of IPv4 responses keyed by IP address
    items = {}
    for i in dns.answers:
        if not (i.answer_type == 1 and i.answer_type == 1):
            continue  # Not A IN

        if i.domain not in items:
            items[i.domain] = []
        items[i.domain].append(ip_bytes_to_str(i.data))

    if not items:
        return  # No Answer entries in response

    for item in items.keys():
        examine_domain(item, items[item])


def examine_domain(domain, addresses):
    if is_match(domain):
        add_routes_for_domain(domain, addresses)
    elif debug:
        # Print a message for debug output. Not considered a necessity in regular mode.
        print(
            "Answer for %s A lookup (non-matching)" % colour_text(domain, COLOUR_GREEN)
        )


# Load arguments and defaults
def handle_arguments():

    # Errors that have not been resolved.
    errors = []
    try:
        opts, operands = getopt.gnu_getopt(sys.argv[1:], "d:Dg:hi:ostv:")
    except getopt.GetoptError as e:
        print_exception(e)
        hexit(1)

    for opt, optarg in opts:
        if optarg:
            optarg = optarg.strip()
        if opt == "-d":
            args[TITLE_DOMAINS].append(optarg.lower())
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
            args[TITLE_MODE] = MODE_STDIN
        elif opt == "-t":
            args[TITLE_MODE] = MODE_TSHARK
        elif opt == "-v":
            args[TITLE_VPN_INTERFACE] = optarg

    # Domains Check
    if not args[TITLE_DOMAINS]:
        print_error("No domains given (-d domain)")

    # Gateway Check
    if TITLE_GATEWAY not in args:
        # TODO: Make a best-effort guess at the default gateway IP. Can probably do this at the same time as the local interface TODO.
        print_error("No gateway given (-g gateway-ip)")
    elif not re.match(REGEX_INET4, args[TITLE_GATEWAY]):
        print_error(
            "Invalid gateway IP: %s" % colour_text((args[TITLE_GATEWAY], COLOUR_GREEN))
        )

    # Interface Check
    if TITLE_INTERFACE not in args:
        # TODO: Make a best-effort guess at the local interface. Can probably do this at the same time as the gateway IP TODO.
        print_error("No interface given (-i interface)")
    elif not os.path.isdir("/sys/class/net/%s" % args[TITLE_INTERFACE]):
        print_error("Interface does not exist: %s" % colour_text(args[TITLE_INTERFACE]))

    # VPN Interface Check
    if TITLE_VPN_INTERFACE not in args:
        if args.get(TITLE_MODE, 0) != MODE_STDIN:
            # Listening with libpcap or tshark requires an interface to listen on.
            print_error("No VPN interface given (-v interface)")
    elif not os.path.isdir("/sys/class/net/%s" % args[TITLE_VPN_INTERFACE]):
        print_error(
            "VPN Interface does not exist: %s" % colour_text(args[TITLE_VPN_INTERFACE])
        )

    if not args.get(TITLE_DEBUG, False):
        print_error(
            "Must be %s to actually add routes via %s command."
            % (colour_text("root", COLOUR_RED), colour_text("route", COLOUR_BLUE))
        )

    if errors:
        for e in errors:
            print_error(e)


def hexit(exit_code=0):
    print(
        "%s: %s -d domain -g gateway -i local-interface -v vpn-interface [-D] [-h] [-o] [-s] [-t]"
        % (
            colour_text("Usage", COLOUR_PURPLE),
            colour_text("./%s" % os.path.basename(sys.argv[0]), COLOUR_GREEN),
        )
    )
    print(
        "  Uses DNS responses in tshark output to create exceptions to VPN redirection."
    )
    print("  Switches:")
    print("    -d domain: Domain to watch. Can be specified multiple times.")
    print(
        "    -D: Debug mode. Do not actually add any detected routes. Also print slightly more output."
    )
    print("    -g gateway: Gateway IP to bypass routes through.")
    print("    -h: Print this help menu and exit.")
    print(
        "    -i local-interface: Interface that local routes will be added on, bypassing VPN"
    )
    print(
        "    -o: Strict domain mode. Only add routes for domains that exactly match requested domains. Default behavior is to match requested domains and all their sub-domains."
    )
    print(
        "    -s: Collect input from standard input (presumed to be tshark output). Example: tshark -i tun0 -f 'port 53' -l 2> /dev/null | ./script.py -s ..."
    )
    print("    -t: Collect input directly tshark output invoked as a subprocess.")
    print(
        "    -v: VPN interface. This is the interface that is expected to be able to see unencrypted DNS responses to drive route addition. Not required for standard input mode."
    )
    print(
        "  Above all: This is a REACTIVE script. It (probably) cannot outpace your first request, but will re-route to the gateway for later requests"
    )
    exit(exit_code)


def ip_bytes_to_str(bytes):
    unpacked = struct.unpack('BBBB', bytes)
    return '%d.%d.%d.%d' % unpacked


def is_match(domain):
    match = False
    if domain in args[TITLE_DOMAINS]:
        match = True
    elif not only:
        # Also check for subdomains of a tracked domain.
        for d in args[TITLE_DOMAINS]:
            if domain.endswith(".%s" % domain):
                match = True
                break
    return match


def main():

    global hosts
    hosts = []
    global debug
    debug = args.get(TITLE_DEBUG, False)
    global only
    only = args.get(TITLE_ONLY_DOMAIN, False)

    if args.get(TITLE_MODE, 0) == MODE_STDIN:
        m = "Taking DNS replies from %s output via standard input" % colour_text(
            "tshark", COLOUR_BLUE
        )
    elif args.get(TITLE_MODE, 0) == MODE_TSHARK:
        m = "Taking DNS replies from %s output on %s" % (
            colour_text("tshark", COLOUR_BLUE),
            colour_text(args[TITLE_VPN_INTERFACE]),
        )
    elif args.get(TITLE_MODE, 0) == MODE_PCAP:
        m = "Taking DNS replies collected via %s data on %s" % (
            colour_text("pypcap"),
            colour_text(args[TITLE_VPN_INTERFACE]),
        )
    m += " and using them to create routes via %s on %s." % (
        colour_text(args[TITLE_GATEWAY], COLOUR_GREEN),
        colour_text(args[TITLE_INTERFACE]),
    )

    print_notice(m)

    if only:
        print_notice("Domains:")
    else:
        print_notice("Domains (and subdomains of):")
    for d in args[TITLE_DOMAINS]:
        print_notice(colour_text(d, COLOUR_GREEN))

    mon = None

    try:
        if args.get(TITLE_MODE, 0) == MODE_STDIN:
            do_input_pipe()
        elif args.get(TITLE_MODE, 0) == MODE_TSHARK:
            # TODO: I'm not sure about how to disable the packet count from tshark without also disabling stdout altogether.
            mon = subprocess.Popen(
                [
                    'tshark',
                    '-n',
                    '-l',
                    '-f',
                    PCAP_FILTER,
                    '-i',
                    args[TITLE_VPN_INTERFACE],
                ],
                stdout=subprocess.PIPE,
                stderr=open(os.devnull, 'w'),
            )
            do_input_pipe(mon.stdout)
        elif args.get(TITLE_MODE, 0) == MODE_PCAP:
            do_input_pcap()
    except KeyboardInterrupt as e:
        pass

    # End loop. Either ctrl-C or tshark died for some reason.
    if not debug:
        if hosts:
            print_notice("Removing %d host route(s)" % len(hosts))
            for r in hosts:
                run_command(['route', 'del', '-host', r])
        else:
            print_notice("No host routes to remove.")


def run_command(cmd, stdout=sys.stdout, stderr=sys.stderr):
    ret = 0
    try:
        p = subprocess.Popen(cmd, stdout=err, stderr=err)
        p.communicate()
        ret = p.returncode
        if ret < 0:
            ret = 1
    except KeyboardInterrupt:
        ret = 130
    except Exception as e:
        print_exception(e)
        ret = 1
    return ret


if __name__ == "__main__":
    handle_arguments()

    if args[TITLE_MODE] == MODE_PCAP:
        # Only bother attempting to load libpcap if it will be used.
        try:
            import pcap
        except ImportError:
            print_error("Python module %s is not installed." % colour_text("pypcap"))
            print_notice(
                "To install: dnf install -y libpcap-devel python-devel redhat-rpm-config && pip install pypcap"
            )

    if error_count:
        hexit(1)

    if args[TITLE_MODE] == MODE_PCAP:
        # Note: Only doing root checks for libpcap input, since I usually make tshark runnable as non-root users on my machines.
        # This check aside, anyone running this without the proper permissions on tshark would get a kick in the pants nearly immediately.
        confirm_root_or_rerun()

    main()
