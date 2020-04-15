#!/usr/bin/env

from __future__ import print_function
import getopt, json, os, re, socket, struct, sys, time
if sys.version_info[0] == 2:
    from thread import start_new_thread
else:
    from _thread import start_new_thread

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message):
    print("%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message))

def colour_text(text, colour = None):
    colour = colour or COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def colour_path(text):
    # Lazy shorthand for next most common colouring after bold.
    return colour_text(text, COLOUR_GREEN)

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

local_files = [re.sub("\.pyc", ".py", __file__)]
def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ""
    if msg:
        sub_msg = "%s, " % msg

    exc_type, exc_obj, exc_tb = sys.exc_info()
    stack = []

    while exc_tb is not None:
        fname = exc_tb.tb_frame.f_code.co_filename
        lineno = exc_tb.tb_lineno
        stack.append((fname, lineno))
        exc_tb = exc_tb.tb_next

    # Get the deepest local file.
    fname, lineno = next((t for t in reversed(stack) if os.path.realpath(t[0]) in local_files), (stack[-1]))

    fname = os.path.split(fname)[1]
    print_error("Unexpected %s (%s%s, Line %s): %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, colour_text(fname, COLOUR_GREEN), lineno, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message)

ATTR_REPLY = "reply"
ATTR_JSON = "json"
ATTR_CLOSING = "closing"

DEFAULT_ATTR_CLOSING = True
DEFAULT_ATTR_JSON = False
DEFAULT_ATTR_REPLY = True

DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = DEFAULT_PORT_LIBRARY = 1234
DEFAULT_TIMEOUT = 5

REGEX_INET4='^(([0-9]){1,3}\.){3}([0-9]{1,3})$'

ENCODING = 'utf-8'

TITLE_BIND = "bind"
TITLE_FORCE_COLOURS = "colours"
TITLE_MODE = "mode"
TITLE_PORT = "port"
TITLE_TIMEOUT = "timeout"
TITLE_VERBOSE="verbose"
# NetAccess titles.
TITLE_ALLOW = "allow address/range"
TITLE_ALLOW_FILE = "allow address/range file"
TITLE_DENY = "deny address/range"
TITLE_DENY_FILE = "deny address/range file"

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
        good = True
        candidate = candidate.strip()
        if re.match(self.REGEX_INET4_CIDR, candidate):
            g, n = self.ip_validate_cidr(candidate)
            good = g
            if g:
                # No error
                net_list.append((n, candidate))
        else:
            g, a, astr = self.ip_validate_address(candidate)
            error = g
            if g:
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

    def ip_make_mask(self, n):
        # Return a mask of n bits as an integer
        return (2<<n-1)-1

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
            return (True, self.ip_strton(ip), ip)
        except socket.gaierror:
            self.errors.append("Unable to resolve: %s" % colour_text(candidate, COLOUR_GREEN))
            return (False, None, None)

    def ip_validate_cidr(self, candidate):
        a = candidate.split("/")[0]
        m = candidate.split("/")[1]
        try:
            if socket.gethostbyname(a) and int(m) <= 32:
                return (True, self.ip_network_mask(a, m))
        except socket.gaierror:
            pass
        self.errors.append("Invalid CIDR address: %s" % colour_text(candidate, COLOUR_GREEN))
        return (False, None)

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
            self.errors.append("Path to %s file does not exist: %s" % (header, colour_text(path, COLOUR_GREEN)))
            return False
        with open(path) as f:
            for l in f.readlines():
                fn(l)

    def load_blacklist_file(self, path):
        return self.load_access_file(self.add_blacklist, path, "blacklist")

    def load_whitelist_file(self, path):
        return self.load_access_file(self.add_whitelist, path, "whitelist")

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

        # Special logic for SimpleMessages
        global CURRENT_MODE
        if CURRENT_MODE in (MODE_TCP_DEFAULT, MODE_TCP_ONLY):
            self.udp = False
            if CURRENT_MODE == MODE_TCP_DEFAULT:
                self.add_opt(OPT_TYPE_FLAG, "u", TITLE_MODE, "UDP Mode (default: TCP).")
                self.add_validator(check_toggle_to_udp)
        elif CURRENT_MODE in (MODE_UDP_DEFAULT, MODE_UDP_ONLY):
            self.udp = True
            if CURRENT_MODE == MODE_UDP_DEFAULT:
                self.add_opt(OPT_TYPE_FLAG, "t", TITLE_MODE, "TCP Mode (default: UDP).")
                self.add_validator(check_toggle_to_tcp)
        if CURRENT_MODE in (MODE_UDP_DEFAULT, MODE_TCP_DEFAULT, MODE_TCP_ONLY):
            # If TCP is an option, then add the option to set a socket timeout value.
            self.add_opt(OPT_TYPE_SHORT, "T", TITLE_TIMEOUT, "Read socket timeout for TCP connections.", converter = int, default = DEFAULT_TIMEOUT, default_announce = True)
        # End special logic

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

# Initialize arguments
args = ArgHelper()
# Short opts
args.add_opt(OPT_TYPE_FLAG, "v", TITLE_VERBOSE, "Verbose output.")
args.add_opt(OPT_TYPE_FLAG, "C", TITLE_FORCE_COLOURS, "Force colours to be enabled.")
# Short flags
args.add_opt(OPT_TYPE_SHORT, "a", TITLE_ALLOW, "Add network address or CIDR range to whitelist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "A", TITLE_ALLOW_FILE, "Add addresses or CIDR ranges in file to whitelist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "b", TITLE_BIND, "Address to bind to.", default = DEFAULT_BIND, default_announce = True, default_colour = COLOUR_GREEN)
args.add_opt(OPT_TYPE_SHORT, "d", TITLE_DENY, "Add network address or CIDR range to blacklist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "D", TITLE_DENY_FILE, "Add addresses or CIDR ranges in file to blacklist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "p", TITLE_PORT, "Specify server bind port.", converter = int, default = DEFAULT_PORT, default_announce = True)

# Values for TCP/UDP settings, along with some truly lazy shorthand functions.
MODE_TCP_DEFAULT = "tcp"
MODE_TCP_ONLY = "tcp-only"
MODE_UDP_DEFAULT = "udp"
MODE_UDP_ONLY = "udp-only"

CURRENT_MODE = MODE_TCP_DEFAULT
def set_mode_tcp_default():
    global CURRENT_MODE
    CURRENT_MODE = MODE_TCP_DEFAULT

def set_mode_tcp_only():
    global CURRENT_MODE
    CURRENT_MODE = MODE_TCP_ONLY

def set_mode_udp_default():
    global CURRENT_MODE
    CURRENT_MODE = MODE_UDP_DEFAULT

def set_mode_udp_only():
    global CURRENT_MODE
    CURRENT_MODE = MODE_UDP_ONLY

# Validator functions
def process_colour_args(self):
    if self[TITLE_FORCE_COLOURS]:
        enable_colours(true)

def validate_common_arguments(self):
    errors = []

    port = self[TITLE_PORT]
    if port < 0 or port > 65535:
        errors.append("Port must be 0-65535. Given: %s" % colour_text(port))

    if TITLE_TIMEOUT in self:
        errors.append("Timeout must be a positive value. Given: %s" % colour_text(COLOUR_BOLD, self[TITLE_TIMEOUT]))
    return errors

args.add_validator(validate_common_arguments)

# Apply blacklist and whitelist values
def validate_blacklists(self):
    for i in self[TITLE_ALLOW]:
        access.add_whitelist(i)
    for i in self[TITLE_ALLOW_FILE]:
        access.load_whitelist_file(i)
    for i in self[TITLE_DENY]:
        access.add_blacklist(i)
    for i in self[TITLE_DENY_FILE]:
        access.load_whitelist_file(i)
    return access.errors
args.add_validator(validate_blacklists)

# Special handler for SimpleMessages
def check_toggle_to_tcp(self):
    if self[TITLE_MODE]:
        self.udp = False

# Special handler for SimpleMessages
def check_toggle_to_udp(self):
    if self[TITLE_MODE]:
        self.udp = True

# Script-running classes and functions.
class SimpleMessageSession:
    def __init__(self, sock, udp, addr, handler_class):
        self.udp = udp
        self.sock = sock
        self.addr = addr
        self.handler = handler_class(self)
        self.closing = True

    def handle(self, data):
        log_header = "%s[%s]" % (colour_text(self.addr[0], COLOUR_GREEN), colour_text(time.strftime("%Y-%m-%d %k:%M:%S")))
        msg = None
        try:
            if isinstance(data, bytes) and sys.version_info[0] >= 3:
                data = str(data, ENCODING)

            if getattr(self.handler, ATTR_JSON, DEFAULT_ATTR_JSON):
                have_json = False
                try:
                    j_data = json.loads(data) # Convert to an object
                    have_json = True
                except Exception as e:
                    if args[TITLE_VERBOSE]:
                        print_exception(e, "JSON decoding")
                    msg = json.dumps({"error": "Malformed JSON"})
                if have_json:
                    msg = self.handler.handle(log_header, j_data)
            else:
                # Run message directly
                msg = self.handler.handle(log_header, data)
        except Exception as e:
            print_exception(e, "Processing handler")
        if getattr(self.handler, ATTR_REPLY, DEFAULT_ATTR_REPLY) and msg is not None:
            self.send(msg)

    def send(self, data):

        if not isinstance(data, bytes) and sys.version_info[0] >= 3:
            data = bytes(data, ENCODING)

        if self.udp:
            self.sock.sendto(data, self.addr) # UDP
        else:
            self.sock.sendall(data) # TCP

def announce_common_arguments(verb = "Doing stuff"):

    bind_address, bind_port = get_bind_information()

    if verb:
        if args.udp:
            noun = "datagrams"
        else:
            noun = "connections"

        print_notice("%s with %s sent to %s\n" % (verb, noun, colour_text("%s:%d" % (bind_address, bind_port), COLOUR_GREEN)))

    if args[TITLE_VERBOSE]:
        print_notice("Extra information shall also be printed.")

    if TITLE_TIMEOUT in args:
        timeout_bold = colour_text(args[TITLE_TIMEOUT])
        print_notice("Read socket timeout: %s" % timeout_bold)
        if args.udp:
            print_warning("Socket timeout value of %ss will be ignored for UDP connections." % timeout_bold)

    access.announce_filter_actions()

def get_bind_information():
    return (args[TITLE_BIND], args[TITLE_PORT])

def serve(handler_class):
    # Convenient short-hand
    udp = args.udp
    port = args[TITLE_PORT]
    bind = args[TITLE_BIND]

    if udp:
        sockobj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    else:
        sockobj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind socket to local host and port
    try:
        sockobj.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockobj.bind((bind, port))
        if not udp:
            sockobj.listen(10)
    except socket.error as msg:
        print_error('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
        exit(1)

    if udp:
        sessions = {}

    # Keep accepting new messages
    try:
        while True:
            if udp:
                data, addr = sockobj.recvfrom(65535)
            else:
                conn, addr = sockobj.accept()

            if not access.is_allowed(addr[0]):
                # Not allowed
                if args[TITLE_VERBOSE]:
                    print_denied("%s (%s)" % (log_header, colour_text("Ignored", COLOUR_RED)))
                continue

            if udp:
                # UDP
                if addr not in sessions:
                    sessions[addr] = SimpleMessageSession(sockobj, True, addr, handler_class)
                sessions[addr].handle(data)

                if getattr(sessions[addr], ATTR_CLOSING, DEFAULT_ATTR_CLOSING):
                    del sessions[addr]
            else:
                # TCP
                start_new_thread(tcpclientthread, (conn, addr,  handler_class))
    except KeyboardInterrupt:
        pass

def set_default_port(port):
    # Used for services to conveniently adjust their default port.
    args.defaults[TITLE_PORT] = DEFAULT_PORT = port

def tcpclientthread(sockobj, addr, handler_class):
    sockobj.settimeout(args[TITLE_TIMEOUT])
    keep_alive = True
    session = SimpleMessageSession(sockobj, False, addr, handler_class)
    try:
        while keep_alive:
            data = sockobj.recv(65535)
            if not data:
                sockobj.close()
                return
            session.handle(data)
            keep_alive = not getattr(session, ATTR_CLOSING, DEFAULT_ATTR_CLOSING)
    except socket.timeout as e:
        print_exception(e, "Client %s Timeout" % colour_text(addr[0], COLOUR_GREEN))
    except Exception as e:
        print_exception(e, "Client %s" % colour_text(addr[0], COLOUR_GREEN))

    sockobj.close()

access = NetAccess()
