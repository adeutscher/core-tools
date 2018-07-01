#!/usr/bin/python

"""

This is a rewrite of a past project to report potential ARP poisoning.
The original product was written in

Well-behaved ARP behavior requires both a request and a reply.
    With a conversation as an analogy, this could be said as:
        * Host A: I'm looking for someone at this address B
        * Host B: Hey Host A, I'm Host B, and I'm over here.

ARP poisoning involves a malicious host constandly sending out
    crafted ARP messages to interfere with the ARP tables of the victim.
    With a conversation as an analogy, this could be said as:
        * Host C: Hey Host A, I'm host B, and I'm over here (honest!)
        * Host C: Hey Host A, I'm host B, and I'm over here (honest!)

This script makes judgements based on imbredacted-nameces of ARP replies to ARP requests.
  * An imbredacted-namece of requests for a particular address suggests a client trying to reach something on an unused address.
    This is unfortunate for the person making the request, but not harmful.
* An imbredacted-namece of replies for a particular address suggests that ARP poisoning is taking place.
"""

import getopt, getpass, os, pwd, re, struct, subprocess, sys, time

# Colours

def colour_text(colour, text):
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

alert_count = 0
def print_alert(message):
    global alert_count
    alert_count += 1
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_RED, "ALERT", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_RED, "Error", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_info(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_GREEN, "Info", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_notice(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_BLUE, "Notice", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_usage(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_PURPLE, "Usage", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_warning(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_YELLOW, "Warning", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

#
# Script Functions
###

ARP_INSTANCES = {}
LAST_SCRIPT_RUN = {}
TIME_START = 0
TIME_SPAN = 0
TIME_RECENT = 0

ARP_SPOOF_EVENT_HEAL = "SPOOF"
ARP_SPOOF_EVENT_SPOOF = "SPOOF"

DEFAULT_EXPIRY = 300
DEFAULT_LIST = False
DEFAULT_REPORT_THRESHOLD = 5
DEFAULT_SCRIPT_COOLDOWN = 300
DEFAULT_SCRIPT_USER = getpass.getuser()
DEFAULT_VERBOSE = False

PCAP_FILTER = "arp"

TITLE_SCRIPT_COOLDOWN = "script cooldown"
TITLE_EXPIRY = "expiry period"
TITLE_INTERFACE = "interface"
TITLE_LIST = "list ips"
TITLE_PCAP_FILE = "PCAP file"
TITLE_REPORT_THRESHOLD = "report threshold"
TITLE_SCRIPT = "processing script"
TITLE_SCRIPT_USER = "processing script user"
TITLE_VERBOSE = "verbose"

class ARP():
    def __init__(self, ts, pkt):

        self.ts = ts

        initial_offset = 0
        offset = initial_offset

        if not offset:
            # Ethernet Header (should technically be separate if this were a larger-scale application...)

            edst = pkt[offset:offset+6] # Ethernet Header Destination
            self.edst = self._mac_bytes_to_str(edst)
            offset += 6

            esrc = pkt[offset:offset+6] # Ethernet Header Source
            self.esrc = self._mac_bytes_to_str(esrc)
            offset += 6

            self.type = struct.unpack('!H', pkt[offset:offset+2])[0] # Ethernet Header Protocol Type
            offset += 2
        else:
            self.type = -1
            self.edst = None
            self.esrc = None

        self.hw_type = struct.unpack('!H', pkt[offset:offset+2])[0] # Hardware Type
        offset += 2

        self.proto_type = struct.unpack('!H', pkt[offset:offset+2])[0] # Protocol Type
        offset += 2

        self.hw_size = struct.unpack('B', pkt[offset])[0] # Hardware Address Size
        offset += 1

        self.proto_size = struct.unpack('B', pkt[offset])[0] # Protocol Size
        offset += 1

        self.opcode = struct.unpack('!H', pkt[offset:offset+2])[0]
        offset += 2

        # ARP Header Source
        asrc = pkt[offset:offset+6]
        self.asrc = self._mac_bytes_to_str(asrc)
        offset += 6

        # Network Source IP
        nsrc = pkt[offset:offset+4]
        self.nsrc = "%d.%d.%d.%d" % (ord(nsrc[0]), ord(nsrc[1]), ord(nsrc[2]), ord(nsrc[3]))
        offset += 4

        # ARP Header Destination
        adst = pkt[offset:offset+6]
        self.adst = self._mac_bytes_to_str(adst)
        offset += 6

        # Network Destination IP
        ndst = pkt[offset:offset+4]
        self.ndst = "%d.%d.%d.%d" % (ord(ndst[0]), ord(ndst[1]), ord(ndst[2]), ord(ndst[3]))
        offset += 4

        if self.opcode == 1: # Request
            # Request
            self.id = "%s%s" % (asrc, ndst)
        elif self.opcode == 2: # Reply
            self.id = "%s%s" % (adst, nsrc)
        else:
            self.id = "0000000000" # Placeholder, fallback. This will be discarded soon anyways.

        # Format the ID into a string for debug purposes.
        self.id_s = ''
        for b in self.id:
            self.id_s += '%02x' % ord(b)

    def _mac_bytes_to_str(self, bytes):
        unpacked = struct.unpack('BBBBBB', bytes)
        result = ''
        for b in unpacked:
            result += '%02x:' % b
        return result[:-1]

def attempt_script(event, ts, arp):
    if event not in LAST_SCRIPT_RUN:
        LAST_SCRIPT_RUN[event] = {}

    if TITLE_SCRIPT not in args or not ((ts - LAST_SCRIPT_RUN[event].get(arp.id, ts)) > args.get(TITLE_SCRIPT_COOLDOWN, DEFAULT_SCRIPT_COOLDOWN)):
        return # No script defined or cooldown not exceeded.

    # Mark timestamp by starting time.
    LAST_SCRIPT_RUN[event][arp.id] = ts

    # Run script
    try:
        subprocess.Popen([args[TITLE_SCRIPT], event, arp.nsrc, arp.asrc, arp.ndst, arp.adst, arp.esrc, arp.edst], preexec_fn=demote(userinfo.pw_uid, userinfo.pw_gid))
    except OSError:
        print_error("Problem executing script hook: %s" % colour_text(COLOUR_GREEN, args.get(TITLE_SCRIPT)))

def demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)
    return result

def do_pcap():
    target = args.get(TITLE_INTERFACE, args.get(TITLE_PCAP_FILE))
    pcap_obj = pcap.pcap(name=target, promisc=True, immediate=True, timeout_ms=50)
    try:
        pcap_obj.setfilter(PCAP_FILTER)
    except:
        print_error("Illegal PCAP filter: %s" % colour_text(COLOUR_BOLD, PCAP_FILTER))
        exit(1)

    try:
        pcap_obj.loop(0, do_pcap_callback)
    except KeyboardInterrupt:
        print "\n"

    global TIME_RECENT
    global TIME_SPAN
    global TIME_START

    if TITLE_INTERFACE in args:
        TIME_RECENT = time.time()

    TIME_SPAN = int(TIME_RECENT - TIME_START)

def do_pcap_callback(ts, pkt, arg=None):
    # Reject too-short packets that could never be built into ARP messages
    if len(pkt) < 38:
        return

    arp = ARP(ts, pkt)

    if arp.opcode == 1: # ARP Request OpCode
        op = "REPLY"
        if args.get(TITLE_VERBOSE, DEFAULT_VERBOSE):
            print_notice("%s: Who has %s? Tell %s (%s)" % (colour_text(COLOUR_BOLD, op), colour_text(COLOUR_GREEN, arp.ndst), colour_text(COLOUR_GREEN, arp.nsrc), colour_text(COLOUR_BOLD, arp.asrc)))
    elif arp.opcode == 2: # ARP Reply OpCode
        op = "REPLY"
        if args.get(TITLE_VERBOSE, DEFAULT_VERBOSE):
            print_notice("%s: %s is at %s (To: %s at %s)" % (colour_text(COLOUR_BOLD, op), colour_text(COLOUR_GREEN, arp.nsrc), colour_text(COLOUR_BOLD, arp.asrc), colour_text(COLOUR_GREEN, arp.ndst), colour_text(COLOUR_BOLD, arp.adst)))
    else:
        return # Not a request or reply.

    global TIME_RECENT
    global TIME_START
    TIME_RECENT = ts
    if not TIME_START:
        TIME_START = ts

    if arp.asrc != arp.esrc:
        print_alert("%s for IP %s claiming to be from MAC %s, but is actually from MAC %s. Likely a forged healing packet!" % (colour_text(COLOUR_BOLD, op), colour_text(COLOUR_GREEN, arp.nsrc), colour_text(COLOUR_BOLD, arp.asrc), colour_text(COLOUR_BOLD, arp.esrc)))
        list_ipv4_addresses_by_mac(arp.esrc)
        attempt_script(ARP_SPOOF_EVENT_HEAL, ts, arp)

        # Immediately return.
        # The point in tracking events is that we normally cannot track poisoning by a single packet.
        # However, healing packets from ettercap/arpspoof/etc trying to cover its tracks
        # are blatant enough that they can be identified right away.
        # Do not track event to avoid false positives.
        return

    # Is an interaction of this ID currently stored in the dictionary?
    if arp.id not in ARP_INSTANCES:
        ARP_INSTANCES[arp.id] = [arp] # Create list and add ARP packet
    else:
        ARP_INSTANCES[arp.id].append(arp) # Append ARP packet to existing chain.

    # Need to clear out old instances.
    # If we are reading from a PCAP file, then we can only really
    #   compare against the current timestamp.
    # If we are reading from a live capture, then we can use the current
    #   time as a reference (which should be pretty much be
    #   the provided timestamp anyways).
    for k in ARP_INSTANCES.keys():
        # May as well clear through all instances.
        i = 0
        while i < len(ARP_INSTANCES[k]):
            if (ts - ARP_INSTANCES[k][i].ts) > args.get(TITLE_EXPIRY, DEFAULT_EXPIRY):
                del ARP_INSTANCES[k][i]
                # Do not increment, since i will now be the old i+1.
            else:
                i += 1
        if not ARP_INSTANCES[k]:
            # Delete empty lists, mostly for tidiness.
            del ARP_INSTANCES[k]
            for key in LAST_SCRIPT_RUN:
                for subkey in LAST_SCRIPT_RUN[key]:
                    if arp.id in LAST_SCRIPT_RUN[key][subkey]:
                        del LAST_SCRIPT_RUN[key][subkey][arp.id]

    # Sweep through non-expired instances of this ID to look for potential poisoning.
    score = 0
    i = 0
    while i < len(ARP_INSTANCES[arp.id]):
        if ARP_INSTANCES[arp.id][i].opcode == 1: # Request
            # Machine sent out a request, behooving real machine to reply and countering poison attack.
            # Still under consideration, have a request simply decrement the score instead?
            score = 0
        else: # Reply
            score += 1
        i += 1

    if score >= args.get(TITLE_REPORT_THRESHOLD, DEFAULT_REPORT_THRESHOLD):
         #
         # TODO: Existing reporting currently has a bit of a flaw:
         #          - Does not account for one IP "legitimately" being stepped on by two devices, creating an imbredacted-namece.
         #            This still impedes network performance, but it's more "ARP high cholesterol" than "ARP poisoning".
         #            Still bad for your network, but not necessarily malicious.

        print_alert("%s (%s) is likely being ARP poisoned by %s (spoofing %s, ARP imbredacted-namece of %s over %s seconds)" % (colour_text(COLOUR_GREEN, arp.ndst), colour_text(COLOUR_BOLD, arp.adst), colour_text(COLOUR_BOLD, arp.esrc), colour_text(COLOUR_GREEN, arp.nsrc), colour_text(COLOUR_BOLD, score), colour_text(COLOUR_BOLD, args.get(TITLE_REPORT_THRESHOLD, DEFAULT_REPORT_THRESHOLD))));
        list_ipv4_addresses_by_mac(arp.esrc)
        attempt_script(ARP_SPOOF_EVENT_SPOOF, ts, arp)

def hexit(code = 0):
    print_usage("./%s (-i interface||-f pcap-file) [-c script-cooldown] [-e expiry-time] [-h] [-s script] [-t report-threshold] [-v]" % os.path.basename(sys.argv[0]))
    exit(code)


def list_ipv4_addresses_by_mac(mac):

    if not args.get(TITLE_LIST, DEFAULT_LIST):
        return # Listing is not enabled.

    try:
        with open("/proc/net/arp", "r") as f:
            content = f.readlines()
            f.close()
    except OSError as e:
        # File error.
        print_error(e)
        return

    addresses = []

    for line in content:
        cols = re.sub('\s+', ' ', line).split(" ")
        if cols[3] == mac:
            addresses.append(colour_text(COLOUR_GREEN, cols[0]))

    if addresses:
        print_info("IPv4 entries for %s in current ARP table: %s" % (colour_text(COLOUR_BOLD, mac), ", ".join(addresses)))

def process_arguments():

    raw_ints = {}

    try:
        opts, operands = getopt.gnu_getopt(sys.argv, "c:e:f:hi:ls:t:u:v")
    except getopt.GetoptError as e:
        print_error(e)
        exit(1)

    for opt, optarg in opts:
        if opt in ("-c"):
            raw_ints[TITLE_SCRIPT_COOLDOWN] = optarg
        elif opt in ("-e"):
            raw_ints[TITLE_EXPIRY] = optarg
        elif opt in ("-f"):
            args[TITLE_PCAP_FILE] = optarg
        elif opt in ("-h"):
            hexit(0)
        elif opt in ("-i"):
            args[TITLE_INTERFACE] = optarg
        elif opt in ("-l"):
            args[TITLE_LIST] = True
        elif opt in ("-s"):
            args[TITLE_SCRIPT] = optarg
        elif opt in ("-t"):
            raw_ints[TITLE_REPORT_THRESHOLD] = optarg
        elif opt in ("-u"):
            raw_ints[TITLE_SCRIPT_USER] = optarg
        elif opt in ("-v"):
            args[TITLE_VERBOSE] = True

    for key in raw_ints:
        try:
            args[key] = int(raw_ints[key])
        except ValueError:
            print_error("Invalid %s%s%s: %s%s%s" % (COLOUR_BOLD, key, COLOUR_OFF, COLOUR_BOLD, raw_ints[key], COLOUR_OFF))

    # Validate integer values.
    for key in (TITLE_SCRIPT_COOLDOWN, TITLE_EXPIRY, TITLE_REPORT_THRESHOLD):
        if key in args and args[key] <= 0:
            print_error("Value of %s%s%s must be a positive integer." % (COLOUR_BOLD, key, COLOUR_OFF))
            del args[key] # Delete to not interfere with other validations.

    if TITLE_REPORT_THRESHOLD in args and args[TITLE_REPORT_THRESHOLD] < 2:
        print_warning("A low %s%s%s value of %s%d%s could generate a lot of false positives." % (COLOUR_BOLD, TITLE_REPORT_THRESHOLD, COLOUR_OFF, COLOUR_BOLD, args[TITLE_REPORT_THRESHOLD], COLOUR_OFF))

    # Validate PCAP file
    if TITLE_PCAP_FILE in args and not os.path.isfile(args[TITLE_PCAP_FILE]):
        print_error("PCAP file does not exist: %s%s%s" % (COLOUR_GREEN, args[TITLE_INTERFACE], COLOUR_OFF))
    # Validate interface.
    if TITLE_INTERFACE in args:
        if not os.path.isdir("/sys/class/net/%s" % args[TITLE_INTERFACE]):
            print_error("Listening interface does not exist: %s%s%s" % (COLOUR_GREEN, args[TITLE_INTERFACE], COLOUR_OFF))
        if os.geteuid():
            print_error("Must be %s%s%s to listen on a live interface." % (COLOUR_RED, "root", COLOUR_OFF))
    # Note: Intentionally checking for both PCAP and interface errors, even if we are about to complain about the user trying to do both.

    if TITLE_INTERFACE in args and TITLE_PCAP_FILE in args:
        print_error("Cannot use both a PCAP file and a live interface capture.")
    elif not TITLE_INTERFACE in args and not TITLE_PCAP_FILE in args:
        print_error("No interface or PCAP file defined.")

    if TITLE_SCRIPT in args:
        if os.path.isdir(args[TITLE_SCRIPT]):
            print_error("Processing script path is a directory: %s%s%s" % (COLOUR_GREEN, args[TITLE_SCRIPT], COLOUR_OFF))
        elif not os.path.isfile(args[TITLE_SCRIPT]):
            print_error("Processing script does not exist: %s%s%s" % (COLOUR_GREEN, args[TITLE_SCRIPT], COLOUR_OFF))
        elif not os.access(args[TITLE_SCRIPT], os.X_OK):
            print_error("Processing script is not executable: %s%s%s" % (COLOUR_GREEN, args[TITLE_SCRIPT], COLOUR_OFF))

        try:
            global userinfo
            userinfo = pwd.getpwnam(args.get(TITLE_SCRIPT_USER, getpass.getuser()))
        except KeyError:
            print_error("Could not get information for %s: %s" % (colour_text(COLOUR_BOLD, TITLE_SCRIPT_USER), colour_text(COLOUR_BOLD, args[TITLE_SCRIPT_USER])))
    else:
        # Check for arguments that work off of the processing script.
        # I am divided on whether or not these should be warnings or errors...
        for check in [TITLE_SCRIPT_COOLDOWN, TITLE_SCRIPT_USER]:
            if check in args:
                print_error("A value for %s was set, but no %s%s%s is defined." % (colour_text(COLOUR_BOLD, TITLE_SCRIPT), colour_text(COLOUR_BOLD, check)))

    if args.get(TITLE_SCRIPT_COOLDOWN, DEFAULT_SCRIPT_COOLDOWN) > args.get(TITLE_EXPIRY, DEFAULT_EXPIRY):
        print_warning("Value for %s (%s) is less than that of %s (%s). Script may run more often than expected." % (colour_text(COLOUR_BOLD, TITLE_SCRIPT), colour_text(COLOUR_BOLD, args.get(TITLE_SCRIPT_COOLDOWN, DEFAULT_SCRIPT_COOLDOWN)), colour_text(COLOUR_BOLD, TITLE_EXPIRY), colour_text(COLOUR_BOLD, args.get(TITLE_EXPIRY, DEFAULT_EXPIRY))))

def summarize_arguments():
    if TITLE_INTERFACE in args:
        on = ("Listening", "on interface", colour_text(COLOUR_BOLD, args[TITLE_INTERFACE]))
    else:
        on = ("Looking", "in file", colour_text(COLOUR_GREEN, args[TITLE_PCAP_FILE]))
    print_notice("%s for ARP poisoning cases %s: %s" % on)
    print_notice("Poisoning threshold: %s%d%s imbredacted-nameced replies will imply poisoning." % (COLOUR_BOLD, args.get(TITLE_REPORT_THRESHOLD, DEFAULT_REPORT_THRESHOLD), COLOUR_OFF))
    print_notice("Poisoning expiry time: %s%ds%s" % (COLOUR_BOLD, args.get(TITLE_EXPIRY, DEFAULT_EXPIRY), COLOUR_OFF))
    if TITLE_SCRIPT in args:
        user_colour = COLOUR_BOLD
        if args.get(TITLE_SCRIPT_USER, DEFAULT_SCRIPT_USER) == "root":
            user_colour = COLOUR_RED
        print_notice("Processing script: %s%s%s as %s%s%s (cooldown per instance: %s%ss%s)" % (COLOUR_GREEN, args[TITLE_SCRIPT], COLOUR_OFF, user_colour, args.get(TITLE_SCRIPT_USER, DEFAULT_SCRIPT_USER), COLOUR_OFF, COLOUR_BOLD, args.get(TITLE_SCRIPT_COOLDOWN, DEFAULT_SCRIPT_COOLDOWN), COLOUR_OFF))
    if args.get(TITLE_LIST, DEFAULT_LIST):
        print_notice("Suspicious MAC addresses will be checked against our current ARP table for matches.")

try:
    import pcap
except ImportError:
    print_error("Unable to import PCAP module, not installed.")
    print_notice("To install: dnf install -y python-devel redhat-rpm-config && pip install pypcap")

args = {}

if __name__ == "__main__":
    process_arguments()

    if error_count:
        hexit(1)

    summarize_arguments()
    do_pcap()

    colour = COLOUR_RED
    if not alert_count:
        colour = COLOUR_GREEN

    if TITLE_PCAP_FILE in args:
        print_notice("Observed instances of ARP poisoning in PCAP file '%s' over %s seconds: %s" % (colour_text(COLOUR_GREEN, os.path.basename(args[TITLE_PCAP_FILE])), colour_text(COLOUR_BOLD, TIME_SPAN), colour_text(colour, alert_count)))
    else:
        # Interface printing.
        print_notice("Observed instances of ARP poisoning on '%s' interface over %s seconds: %s" % (colour_text(COLOUR_GREEN, os.path.basename(args[TITLE_INTERFACE])), colour_text(COLOUR_BOLD, TIME_SPAN), colour_text(colour, alert_count)))
