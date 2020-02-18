#!/usr/bin/env python

"""

This is a rewrite of a past project to report potential ARP poisoning.
The original product was written in C.

Well-behaved ARP behavior requires both a request and a reply.
    With a conversation as an analogy, this could be said as:
        * Host A: I'm looking for someone at this address B
        * Host B: Hey Host A, I'm Host B, and I'm over here.

ARP poisoning involves a malicious host constandly sending out
    crafted ARP messages to interfere with the ARP tables of the victim.
    With a conversation as an analogy, this could be said as:
        * Host C: Hey Host A, I'm host B, and I'm over here (honest!)
        * Host C: Hey Host A, I'm host B, and I'm over here (honest!)

This script makes judgements based on imbalances of ARP replies to ARP requests.
  * An imbalance of requests for a particular address suggests a client trying to reach something on an unused address.
    This is unfortunate for the person making the request, but not harmful.
* An imbalance of replies for a particular address suggests that ARP poisoning is taking place.
"""

from __future__ import print_function
import getopt, getpass, os, pwd, re, struct, subprocess, sys, time

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message, stderr=False):
    f=sys.stdout
    if stderr:
        f=sys.stderr
    print("%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message), file=f)

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
    print_error("Unexpected %s%s: %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e)))

def print_info(message):
    _print_message(COLOUR_GREEN, "Info", message)

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message)

###########################################

# Common Argument Handling Structure
# My own implementation of an argparse-like structure to add args and
#   build a help menu that I have a bit more control over.
#
# Note: These functions assume that my common message functions are also being used.
#       If this is not the case or if the functions are in a different module:
#          * Adjust print_foo functions.
#          * Adjust colour_text() calls.
#          * Adjust all mentions of COLOUR_* variables.

MASK_OPT_TYPE_LONG = 1
MASK_OPT_TYPE_ARG = 2

OPT_TYPE_FLAG = 0
OPT_TYPE_SHORT = MASK_OPT_TYPE_ARG
OPT_TYPE_LONG_FLAG = MASK_OPT_TYPE_LONG
OPT_TYPE_LONG = MASK_OPT_TYPE_LONG | MASK_OPT_TYPE_ARG

TITLE_HELP = "help"

class ArgHelper:

    args = {}
    defaults = {}
    raw_args = {}
    operands = []

    operand_text = None

    errors = []
    validators = []

    opts = {OPT_TYPE_FLAG: {}, OPT_TYPE_SHORT: {}, OPT_TYPE_LONG: {}, OPT_TYPE_LONG_FLAG: {}}
    opts_by_label = {}

    def __init__(self):
        self.add_opt(OPT_TYPE_FLAG, "h", TITLE_HELP, description="Display a help menu and then exit.")

    def __contains__(self, arg):
        return arg in self.args

    def __getitem__(self, arg, default = None):
        opt = self.opts_by_label.get(arg)

        if not opt:
            # There was no registered option.
            #   Giving give the args dictionary an attempt in case
            #   something like a validator went and added to it.
            return self.args.get(arg)
        if opt.multiple:
            default = []

        # Silly note: Doing a get() out of a dictionary when the stored
        #   value of the key is None will not fall back to default
        value = self.args.get(arg)
        if value is None:
            if opt.environment:
                value = os.environ.get(opt.environment, self.defaults.get(arg))
            else:
                value = self.defaults.get(arg)

        if value is None:
            return default
        return value

    def __setitem__(self, key, value):
        self.args[key] = value

    def add_opt(self, opt_type, flag, label, description = None, required = False, default = None, default_colour = None, default_announce = False, environment = None, converter=str, multiple = False, strict_single = False):

        if opt_type not in self.opts:
            raise Exception("Bad option type: %s" % opt_type)

        has_arg = opt_type & MASK_OPT_TYPE_ARG

        prefix = "-"
        match_pattern = "^[a-z0-9]$"
        if opt_type & MASK_OPT_TYPE_LONG:
            prefix = "--"
            match_pattern = "^[a-z0-9\-]+$" # ToDo: Improve on this regex?

        arg = prefix + flag

        # Check for errors. Developer errors get intrusive exceptions instead of the error list.
        if not label:
            raise Exception("No label defined for flag: %s" % arg)
        if not flag:
            raise Exception("No flag defined for label: %s" % label)
        if not opt_type & MASK_OPT_TYPE_LONG and len(flag) - 1:
            raise Exception("Short options must be 1-character long.") # A bit redundant, but more informative
        if not re.match(match_pattern, flag, re.IGNORECASE):
            raise Exception("Invalid flag value: %s" % flag) # General format check
        for g in self.opts:
            if opt_type & MASK_OPT_TYPE_LONG == g & MASK_OPT_TYPE_LONG and arg in self.opts[g]:
                raise Exception("Flag already defined: %s" % label)
        if label in self.opts_by_label:
            raise Exception("Duplicate label (new: %s): %s" % (arg, label))
        if multiple and strict_single:
            raise Exception("Cannot have an argument with both 'multiple' and 'strict_single' set to True.")
        # These do not cover harmless checks on arg modifiers with flag values.

        obj = OptArg(self)
        obj.opt_type = opt_type
        obj.label = label
        obj.required = required and opt_type & MASK_OPT_TYPE_ARG
        obj.default = default
        obj.default_colour = default_colour
        obj.default_announce = default_announce
        obj.environment = environment
        obj.multiple = multiple
        obj.description = description
        obj.converter = converter
        obj.has_arg = has_arg
        obj.strict_single = strict_single

        self.opts_by_label[label] = self.opts[opt_type][arg] = obj
        if not has_arg:
            default = False
        elif multiple:
            default = []
        self.defaults[label] = default

    def add_validator(self, fn):
        self.validators.append(fn)

    def _get_opts(self):
        s = "".join([k for k in sorted(self.opts[OPT_TYPE_FLAG])])
        s += "".join(["%s:" % k for k in sorted(self.opts[OPT_TYPE_SHORT])])
        return s.replace('-', '')

    def _get_opts_long(self):
        l = ["%s=" % key for key in sorted(self.opts[OPT_TYPE_LONG].keys())] + sorted(self.opts[OPT_TYPE_LONG_FLAG].keys())
        return [re.sub("^-+", "", i) for i in l]

    def convert_value(self, raw_value, opt):
        value = None

        try:
            value = opt.converter(raw_value)
        except:
            pass

        if value is None:
            self.errors.append("Unable to convert %s to %s: %s" % (colour_text(opt.label), opt.converter.__name__, colour_text(raw_value)))

        return value

    get = __getitem__

    def hexit(self, exit_code = 0):

        s = "./%s" % os.path.basename(sys.argv[0])
        lines = []
        for label, section in [("Flags", OPT_TYPE_FLAG), ("Options", OPT_TYPE_SHORT), ("Long Flags", OPT_TYPE_LONG_FLAG), ("Long Options", OPT_TYPE_LONG)]:
            if not self.opts[section]:
                continue

            lines.append("%s:" % label)
            for f in sorted(self.opts[section].keys()):
                obj = self.opts[section][f]
                s+= obj.get_printout_usage(f)
                lines.append(obj.get_printout_help(f))

        if self.operand_text:
            s += " %s" % self.operand_text

        _print_message(COLOUR_PURPLE, "Usage", s)
        for l in lines:
            print(l)

        if exit_code >= 0:
            exit(exit_code)

    def last_operand(self, default = None):
        if not len(self.operands):
            return default
        return self.operands[-1]

    def load_args(self, cli_args = []):
        if cli_args == sys.argv:
            cli_args = cli_args[1:]

        if not cli_args:
            return True

        try:
            output_options, self.operands = getopt.gnu_getopt(cli_args, self._get_opts(), self._get_opts_long())
        except Exception as e:
            self.errors.append("Error parsing arguments: %s" % str(e))
            return False

        for opt, optarg in output_options:
            found = False
            for has_arg, opt_type_tuple in [(True, (OPT_TYPE_SHORT, OPT_TYPE_LONG)), (False, (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG))]:
                if found:
                    break
                for opt_key in opt_type_tuple:
                    if opt in self.opts[opt_key]:
                        found = True
                        obj = self.opts[opt_key][opt]
                        if has_arg:
                            if obj.label not in self.raw_args:
                                self.raw_args[obj.label] = []
                            self.raw_args[obj.label].append(optarg)
                        else:
                            # Flag, single-argument
                            self.args[obj.label] = True
        return True

    def process(self, args = [], exit_on_error = True, print_errors = True):
        validate = True
        if not self.load_args(args):
            validate = False

        if self[TITLE_HELP]:
            self.hexit(0)

        if validate:
            self.validate()

        if self.errors:
            if print_errors:
                for e in self.errors:
                    print_error(e)

            if exit_on_error:
                exit(1)
        return not self.errors

    def set_operand_help_text(self, text):
        self.operand_text = text

    def validate(self):
        for key in self.raw_args:
            obj = self.opts_by_label[key]
            if not obj.has_arg:
                self.args[obj.label] = True
            if not obj.multiple:
                if obj.strict_single and len(self.raw_args[obj.label]) > 1:
                    self.errors.append("Cannot have multiple %s values." % colour_text(obj.label))
                else:
                    value = self.convert_value(self.raw_args[obj.label][-1], obj)
                    if value is not None:
                        self.args[obj.label] = value
            elif obj.multiple:
                self.args[obj.label] = []
                for i in self.raw_args[obj.label]:
                    value = self.convert_value(i, obj)
                    if value is not None:
                        self.args[obj.label].append(value)
            elif self.raw_args[obj.label]:
                value = self.convert_value(self.raw_args[obj.label][-1], obj)
                if value is not None:
                    self.args[obj.label] = value
        for m in [self.opts_by_label[o].label for o in self.opts_by_label if self.opts_by_label[o].required and o not in self.raw_args]:
            self.errors.append("Missing %s value." % colour_text(m))
        for v in self.validators:
            r = v(self)
            if r:
                if isinstance(r, list):
                    self.errors.extend(r) # Append all list items
                else:
                    self.errors.append(r) # Assume that this is a string.

class OptArg:

    def __init__(self, args):
        self.opt_type = 0
        self.args = args

    def is_flag(self):
        return self.opt_type in (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG)

    def get_printout_help(self, opt):

        desc = self.description or "No description defined"

        if self.is_flag():
            s = "  %s: %s" % (opt, desc)
        else:
            s = "  %s <%s>: %s" % (opt, self.label, desc)

        if self.environment:
            s += " (Environment Variable: %s)" % colour_text(self.environment)

        if self.default_announce:
            # Manually going to defaults table allows this core module
            # to have its help display reflect retroactive changes to defaults.
            s += " (Default: %s)" % colour_text(self.args.defaults.get(self.label), self.default_colour)
        return s

    def get_printout_usage(self, opt):

        if self.is_flag():
            s = opt
        else:
            s = "%s <%s>" % (opt, self.label)
        if self.required:
            return " %s" % s
        else:
            return " [%s]" % s

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

# Argument Validators

def validate_integers(self):
    errors = []
    for key in (TITLE_SCRIPT_COOLDOWN, TITLE_EXPIRY, TITLE_REPORT_THRESHOLD):
        if self[key] <= 0:
            errors.append("Value of %s must be a positive integer." % colour_text(key))

    if self[TITLE_REPORT_THRESHOLD] <= 2 and self[TITLE_REPORT_THRESHOLD] > 0:
        # Also tack on a warning
        print_warning("A low %s value of %s could generate a lot of false positives." % (colour_text(TITLE_REPORT_THRESHOLD), colour_text(self[TITLE_REPORT_THRESHOLD])))

    if self[TITLE_SCRIPT_COOLDOWN] > self[TITLE_EXPIRY]:
        print_warning("Value for %s (%s) is less than that of %s (%s). Script may run more often than expected." % (colour_text(TITLE_SCRIPT), colour_text(self[TITLE_SCRIPT_COOLDOWN]), colour_text(TITLE_EXPIRY), colour_text(self[TITLE_EXPIRY])))

    return errors

def validate_input(self):

    errors = []

    # Note: Intentionally checking for both PCAP and interface errors, even if we are about to complain about the user trying to do both.

    # Validate PCAP file
    if TITLE_PCAP_FILE in self and not os.path.isfile(self[TITLE_PCAP_FILE]):
        errors.append("PCAP file does not exist: %s" % colour_text(args[TITLE_INTERFACE], COLOUR_GREEN))
    # Validate interface.
    if TITLE_INTERFACE in self:
        if not os.path.isdir("/sys/class/net/%s" % self[TITLE_INTERFACE]):
            errors.append("Listening interface does not exist: %s" % colour_text(args[TITLE_INTERFACE], COLOUR_GREEN))
        if os.geteuid():
            errors.append("Must be %s to capture on a live interface." % colour_text("root", COLOUR_RED))

    if TITLE_PCAP_FILE in self and TITLE_INTERFACE in self:
        errors.append("Cannot specify both an input file and a capture interface.")
    elif not TITLE_INTERFACE in self and not TITLE_PCAP_FILE in self:
        errors.append("No interface or PCAP file defined.")

    return errors

def validate_module(self):
    try:
        import pcap
    except ImportError:
        return "Unable to import PCAP module, not installed. To install: dnf install -y libpcap-devel python-devel redhat-rpm-config && pip install pypcap"

def validate_script(self):

    errors = []
    if self[TITLE_SCRIPT]:
        if os.path.isdir(self[TITLE_SCRIPT]):
            print_error("Processing script path is a directory: %s" % colour_text(args[TITLE_SCRIPT], COLOUR_GREEN))
        elif not os.path.isfile(args[TITLE_SCRIPT]):
            errors.append("Processing script does not exist: %s" % colour_text(args[TITLE_SCRIPT], COLOUR_GREEN))
        elif not os.access(args[TITLE_SCRIPT], os.X_OK):
            errors.append("Processing script is not executable: %s" % colour_text(args[TITLE_SCRIPT], COLOUR_GREEN))

        try:
            global userinfo
            userinfo = pwd.getpwnam(self.get(TITLE_SCRIPT_USER, getpass.getuser()))
        except KeyError:
            print_error("Could not get information for %s: %s" % (colour_text(TITLE_SCRIPT_USER), colour_text(self[TITLE_SCRIPT_USER])))
    else:
        # Check for arguments that work off of the processing script.
        # I am divided on whether or not these should be warnings or errors...
        for check in [TITLE_SCRIPT_COOLDOWN, TITLE_SCRIPT_USER]:
            if check in self:
                print_warning("A value for %s was set, but no %s is defined." % (colour_text(TITLE_SCRIPT), colour_text(check)))

# Classes

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

        self.hw_size = struct.unpack('BBBBBB', bytes(pkt[offset]))[0] # Hardware Address Size
        offset += 1

        self.proto_size = struct.unpack('BBBB', bytes(pkt[offset]))[0] # Protocol Size
        offset += 1

        self.opcode = struct.unpack('!H', pkt[offset:offset+2])[0]
        offset += 2

        # ARP Header Source
        asrc = pkt[offset:offset+6]
        self.asrc = self._mac_bytes_to_str(asrc)
        offset += 6

        # Network Source IP
        self.nsrc = self._ipv4_bytes_to_str(pkt, offset)
        offset += 4

        # ARP Header Destination
        adst = pkt[offset:offset+6]
        self.adst = self._mac_bytes_to_str(adst)
        offset += 6

        # Network Destination IP
        self.ndst = self._ipv4_bytes_to_str(pkt, offset)
        offset += 4

        if self.opcode == 1: # Request
            # Request
            self.id = "%s%s" % (self.asrc, self.ndst)
        elif self.opcode == 2: # Reply
            self.id = "%s%s" % (self.adst, self.nsrc)
        else:
            self.id = "0000000000" # Placeholder, fallback. This will be discarded soon anyways.

        # Format the ID into a string for debug purposes.
        self.id_s = ''
        for b in self.id:
            self.id_s += '%02x' % ord(b)

    def _ipv4_bytes_to_str(self, pkt, offset):
        nsrc = bytes(pkt[offset:offset+4])
        return "%d.%d.%d.%d" % (nsrc[0], nsrc[1], nsrc[2], nsrc[3])

    def _mac_bytes_to_str(self, raw_bytes):
        unpacked = struct.unpack('BBBBBB', raw_bytes)
        result = ''
        for b in unpacked:
            result += '%02x:' % b
        return result[:-1]

def attempt_script(event, ts, arp, args):
    if event not in LAST_SCRIPT_RUN:
        LAST_SCRIPT_RUN[event] = {}

    if TITLE_SCRIPT not in args or not (ts - LAST_SCRIPT_RUN[event].get(arp.id, ts)) > args[TITLE_SCRIPT_COOLDOWN]:
        return # No script defined or cooldown not exceeded.

    # Mark timestamp by starting time.
    LAST_SCRIPT_RUN[event][arp.id] = ts

    # Run script
    try:
        subprocess.Popen([args[TITLE_SCRIPT], event, arp.nsrc, arp.asrc, arp.ndst, arp.adst, arp.esrc, arp.edst], preexec_fn=demote(userinfo.pw_uid, userinfo.pw_gid))
    except OSError:
        print_error("Problem executing script hook: %s" % colour_text(args[TITLE_SCRIPT], COLOUR_GREEN))

def demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)
    return result

def do_pcap_callback(ts, pkt, obj):
    # Reject too-short packets that could never be built into ARP messages
    if len(pkt) < 38:
        return

    arp = ARP(ts, pkt)

    if arp.opcode == 1: # ARP Request OpCode
        op = "REPLY"
        if obj.args[TITLE_VERBOSE]:
            print_notice("%s: Who has %s? Tell %s (%s)" % (colour_text(op), colour_text(arp.ndst, COLOUR_GREEN), colour_text(arp.nsrc, COLOUR_GREEN), colour_text(arp.asrc)))
    elif arp.opcode == 2: # ARP Reply OpCode
        op = "REPLY"
        if obj.args[TITLE_VERBOSE]:
            print_notice("%s: %s is at %s (To: %s at %s)" % (colour_text(op), colour_text(arp.nsrc, COLOUR_GREEN), colour_text(arp.asrc), colour_text(arp.ndst, COLOUR_GREEN), colour_text(arp.adst)))
    else:
        return # Not a request or reply.

    global TIME_RECENT
    global TIME_START
    TIME_RECENT = ts
    if not TIME_START:
        TIME_START = ts

    if arp.asrc != arp.esrc:
        obj.print_alert("%s for IP %s claiming to be from MAC %s, but is actually from MAC %s. Likely a forged healing packet!" % (colour_text(COLOUR_BOLD, op), colour_text(COLOUR_GREEN, arp.nsrc), colour_text(COLOUR_BOLD, arp.asrc), colour_text(COLOUR_BOLD, arp.esrc)))
        list_ipv4_addresses_by_mac(arp.esrc)
        attempt_script(ARP_SPOOF_EVENT_HEAL, ts, arp, obj.args)

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
            if (ts - ARP_INSTANCES[k][i].ts) > obj.args[TITLE_EXPIRY]:
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

    if score >= obj.args[TITLE_REPORT_THRESHOLD]:
         #
         # TODO: Existing reporting currently has a bit of a flaw:
         #          - Does not account for one IP "legitimately" being stepped on by two devices, creating an imbalance.
         #            This still impedes network performance, but it's more "ARP high cholesterol" than "ARP poisoning".
         #            Still bad for your network, but not necessarily malicious.

        obj.print_alert("%s (%s) is likely being ARP poisoned by %s (spoofing %s, ARP imbalance of %s over %s seconds)" % (colour_text(arp.ndst, COLOUR_GREEN), colour_text(arp.adst), colour_text(arp.esrc), colour_text(arp.nsrc, COLOUR_GREEN), colour_text(score), colour_text(obj.args[TITLE_REPORT_THRESHOLD])));

        list_ipv4_addresses_by_mac(arp.esrc, obj.args[TITLE_LIST])
        attempt_script(ARP_SPOOF_EVENT_SPOOF, ts, arp, obj.args)

def list_ipv4_addresses_by_mac(mac, do_list):

    if not do_list:
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
            addresses.append(colour_text(cols[0], COLOUR_GREEN))

    if addresses:
        print_info("IPv4 entries for %s in current ARP table: %s" % (colour_text(mac), ", ".join(addresses)))

class ToxScreen:
    def __init__(self):
        self.args = ArgHelper()

        self.args.add_opt(OPT_TYPE_SHORT, "c", TITLE_SCRIPT_COOLDOWN, "Cooldown between script invocations.", converter=int, default = DEFAULT_SCRIPT_COOLDOWN, default_announce = True)
        self.args.add_opt(OPT_TYPE_SHORT, "e", TITLE_EXPIRY, "Time in seconds that it takes for an ARP event to fall off this script's radar.", converter=int, default = DEFAULT_EXPIRY, default_announce = True)
        self.args.add_opt(OPT_TYPE_SHORT, "f", TITLE_PCAP_FILE, "PCAP file to load.")
        self.args.add_opt(OPT_TYPE_SHORT, "i", TITLE_INTERFACE, "Network interface to listen for ARP poisoning on.")
        self.args.add_opt(OPT_TYPE_FLAG, "l", TITLE_LIST, "Attempt to resolve offending MAC address to an IP address.")
        self.args.add_opt(OPT_TYPE_SHORT, "s", TITLE_SCRIPT, "Script to run when a suspicious event is detected.")
        self.args.add_opt(OPT_TYPE_SHORT, "t", TITLE_REPORT_THRESHOLD, "Cooldown between script invocations.", converter=int, default = DEFAULT_REPORT_THRESHOLD, default_announce = True)
        self.args.add_opt(OPT_TYPE_SHORT, "u", TITLE_SCRIPT_USER, "User to run script as. Only effective if script is run as root.")
        self.args.add_opt(OPT_TYPE_FLAG, "v", TITLE_VERBOSE, "Enable verbose output.")

        self.args.add_validator(validate_module)
        self.args.add_validator(validate_integers)
        self.args.add_validator(validate_input)
        self.args.add_validator(validate_script)

        self.alert_count = 0

    def do_pcap(self):

        target = self.args.get(TITLE_INTERFACE, self.args[TITLE_PCAP_FILE])
        import pcap
        pcap_obj = pcap.pcap(name=target, promisc=True, immediate=True, timeout_ms=50)
        try:
            pcap_obj.setfilter(PCAP_FILTER)
        except:
            print_error("Illegal PCAP filter: %s" % colour_text(PCAP_FILTER))
            exit(1)

        try:
            pcap_obj.loop(0, do_pcap_callback, self)
        except KeyboardInterrupt:
            print("\n")

        global TIME_RECENT
        global TIME_SPAN
        global TIME_START

        if TITLE_INTERFACE in self.args:
            TIME_RECENT = time.time()

        TIME_SPAN = int(TIME_RECENT - TIME_START)

    def print_alert(self, message):
        self.alert_count += 1
        _print_message(COLOUR_RED, "ALERT", message)

    def run(self, raw_args):
        self.args.process(raw_args)
        self.summarize_arguments()

        self.do_pcap()

        colour = COLOUR_RED
        if not self.alert_count:
            colour = COLOUR_GREEN

        if TITLE_PCAP_FILE in self.args:
            print_notice("Observed instances of ARP poisoning in PCAP file '%s' over %s seconds: %s" % (colour_text(os.path.basename(self.args[TITLE_PCAP_FILE]), COLOUR_GREEN), colour_text(TIME_SPAN), colour_text(self.alert_count, colour)))
        else:
            # Interface printing.
            print_notice("Observed instances of ARP poisoning on '%s' interface over %s seconds: %s" % (colour_text(COLOUR_GREEN, os.path.basename(self.args[TITLE_INTERFACE])), colour_text(TIME_SPAN), colour_text((self.alert_count, colour))))

    def summarize_arguments(self):
        if TITLE_INTERFACE in self.args:
            on = ("Listening", "on interface", colour_text(self.args[TITLE_INTERFACE]))
        else:
            on = ("Looking", "in file", colour_text(self.args[TITLE_PCAP_FILE], COLOUR_GREEN))
        print_notice("%s for ARP poisoning cases %s: %s" % on)
        print_notice("Poisoning threshold: %s imbalanced replies will imply poisoning." % colour_text(self.args[TITLE_REPORT_THRESHOLD]))
        print_notice("Poisoning expiry time: %s" % colour_text("%ds" % self.args[TITLE_EXPIRY]))
        if TITLE_SCRIPT in self.args:
            user_colour = COLOUR_BOLD
            if self.args[TITLE_SCRIPT_USER] == "root":
                user_colour = COLOUR_RED
            print_notice("Processing script: %s as %s (cooldown per instance: %s)" % (colour_text(self.args[TITLE_SCRIPT], COLOUR_GREEN), colour_text(self.args[TITLE_SCRIPT_USER], user_colour), colour_text("%ds" % self.args[TITLE_SCRIPT_COOLDOWN])))
        if self.args[TITLE_LIST]:
            print_notice("Suspicious MAC addresses will be checked against our current ARP table for matches.")

if __name__ == "__main__":

    screen = ToxScreen()
    screen.run(sys.argv)
