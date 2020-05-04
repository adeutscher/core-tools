#!/usr/bin/env python3

from __future__ import print_function
# General
import getopt, os, random, re, sys
# Networking
import errno, fcntl, select, socket, ssl, struct, time
from ssl import SSLError, SSLWantReadError, SSLWantWriteError
from select import EPOLLIN, EPOLLET, EPOLLERR, EPOLLHUP, EPOLLONESHOT, EPOLLOUT, EPOLLPRI

# This script uses a number of features of the 'select' module that were present in
#   Fedora 31's installation of Python3 but not in Python2 on the same system.
# For the momment, my approach to this is to allow a Python2 invocation to proceed as
#   as far as argument validation, where an error message about an incorrect version
#   will be presented along with every other error.
if sys.version_info.major >= 3:
    from select import EPOLLRDHUP
else:
    # May as well set the proper EPOLLRDHUP value
    EPOLLRDHUP = 0x2000

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message, log_message = False, stderr=False):
    f=sys.stdout
    if stderr:
        f=sys.stderr

    header_template = "%s[%%s]:" % colour_text(header_text, header_colour)
    if log_message:
        header = header_template % colour_text(time.strftime("%Y-%m-%d %k:%M:%S"))
    else:
        header = header_template % colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN)

    print(header, message, file=f)

def colour_addr(ip, port, host=None):
    if host and host != ip: return '[%s:%s (%s)]' % (colour_blue(ip), colour_text(port), colour_blue(host))
    return '%s:%s' % (colour_blue(ip), colour_text(port))

def colour_blue(text): return colour_text(text, COLOUR_BLUE)

def colour_green(text): return colour_text(text, COLOUR_GREEN)

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

def log_error(msg): print_error(msg, log_message = True)

def log_notice(msg): print_notice(msg, log_message = True)

error_count = 0
def print_error(message, log_message = False):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, "Error", message, log_message = log_message)

def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ""
    if msg: sub_msg = " (%s)" % msg
    print_error("Unexpected %s%s: %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e)))

def print_notice(message, log_message = False): _print_message(COLOUR_BLUE, "Notice", message, log_message = log_message)

def print_warning(message): _print_message(COLOUR_YELLOW, "Warning", message)

###########################################

# Common Argument Handling Structure
# My own implementation of an argparse-like structure to add args and
#   build a help menu that I have a bit more control over.
#

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

    def __contains__(self, arg): return arg in self.args

    def __getitem__(self, arg, default = None):
        opt = self.opts_by_label.get(arg)

        if not opt:
            # There was no registered option.
            #   Giving give the args dictionary an attempt in case
            #   something like a validator went and added to it.
            return self.args.get(arg)
        if opt.multiple: default = []

        # Silly note: Doing a get() out of a dictionary when the stored
        #   value of the key is None will not fall back to default
        value = self.args.get(arg)
        if value is None:
            if opt.environment: value = os.environ.get(opt.environment, self.defaults.get(arg))
            else: value = self.defaults.get(arg)

        if value is None: return default
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
        if not has_arg: default = False
        elif multiple: default = []
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

        try: value = opt.converter(raw_value)
        except: pass

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

        if self.operand_text: s += " %s" % self.operand_text

        _print_message(COLOUR_PURPLE, "Usage", s)
        for l in lines: print(l)

        if exit_code >= 0: exit(exit_code)

    def last_operand(self, default = None):
        if not len(self.operands): return default
        return self.operands[-1]

    def load_args(self, cli_args = []):
        if cli_args == sys.argv: cli_args = cli_args[1:]

        if not cli_args: return True

        try:
            output_options, self.operands = getopt.gnu_getopt(cli_args, self._get_opts(), self._get_opts_long())
        except Exception as e:
            self.errors.append("Error parsing arguments: %s" % str(e))
            return False

        for opt, optarg in output_options:
            found = False
            for has_arg, opt_type_tuple in [(True, (OPT_TYPE_SHORT, OPT_TYPE_LONG)), (False, (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG))]:
                if found: break
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

        # If basic argument loading failed, then don't bother to validate
        validate = self.load_args(args)

        if self[TITLE_HELP]: self.hexit(0)

        if validate: self.validate()

        if self.errors:
            if print_errors:
                for e in self.errors: print_error(e)

            if exit_on_error: exit(1)
        return not self.errors

    def set_operand_help_text(s, text): s.operand_text = text

    def validate(self):
        for key in self.raw_args:
            obj = self.opts_by_label[key]
            if not obj.has_arg: self.args[obj.label] = True
            if not obj.multiple:
                if obj.strict_single and len(self.raw_args[obj.label]) > 1:
                    self.errors.append("Cannot have multiple %s values." % colour_text(obj.label))
                else:
                    value = self.convert_value(self.raw_args[obj.label][-1], obj)
                    if value is not None: self.args[obj.label] = value
            elif obj.multiple:
                self.args[obj.label] = []
                for i in self.raw_args[obj.label]:
                    value = self.convert_value(i, obj)
                    if value is not None: self.args[obj.label].append(value)
            elif self.raw_args[obj.label]:
                value = self.convert_value(self.raw_args[obj.label][-1], obj)
                if value is not None: self.args[obj.label] = value
        for m in [self.opts_by_label[o].label for o in self.opts_by_label if self.opts_by_label[o].required and o not in self.raw_args]:
            self.errors.append("Missing %s value." % colour_text(m))
        for v in self.validators:
            r = v(self)
            if r:
                if isinstance(r, list): self.errors.extend(r) # Append all list items
                else: self.errors.append(r) # Assume that this is a string.

class OptArg:
    def __init__(s, a):
        s.opt_type = 0
        s.args = a

    def is_flag(s): return s.opt_type in (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG)

    def get_printout_help(self, opt):

        desc = self.description or "No description defined"

        if self.is_flag(): s = "  %s: %s" % (opt, desc)
        else: s = "  %s <%s>: %s" % (opt, self.label, desc)

        if self.environment: s += " (Environment Variable: %s)" % colour_text(self.environment)

        if self.default_announce:
            # Manually going to defaults table allows this core module
            # to have its help display reflect retroactive changes to defaults.
            s += " (Default: %s)" % colour_text(self.args.defaults.get(self.label), self.default_colour)
        return s

    def get_printout_usage(self, opt):

        if self.is_flag(): s = opt
        else: s = "%s <%s>" % (opt, self.label)

        if self.required: return " %s" % s
        return " [%s]" % s

# Network Access Class
###

class NetAccess:
    # Basic IPv4 CIDR syntax check
    REGEX_INET4_CIDR='^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

    def __init__(s):
        s.errors = []
        s.allowed_addresses = []
        s.allowed_networks = []
        s.denied_addresses = []
        s.denied_networks = []

    def add_access(s, addr_list, net_list, candidate):
        good = True
        candidate = candidate.strip()
        if re.match(s.REGEX_INET4_CIDR, candidate):
            g, n = s.ip_validate_cidr(candidate)
            if g: net_list.append((n, candidate))
        else:
            g, a, astr = s.ip_validate_address(candidate)
            if g: addr_list.append((a, candidate, astr))
        return g

    add_blacklist = lambda s, c: s.add_access(s.denied_addresses, s.denied_networks, c)

    add_whitelist = lambda s, c: s.add_access(s.allowed_addresses, s.allowed_networks, c)

    def announce_filter_actions(self):
        for action, address_list, network_list in [("Allowing", self.allowed_addresses, self.allowed_networks), ("Denying", self.denied_addresses, self.denied_networks)]:
            l = []
            l.extend([("address", s, i) for n, s, i in address_list])
            l.extend([("network", s, s) for n, s in network_list])

            for title, ip, address in l:
                if ip == address: print_notice("%s %s: %s" % (action, title, colour_text(address, COLOUR_GREEN)))
                else: print_notice("%s %s: %s (%s)" % (action, title, colour_text(address, COLOUR_GREEN), colour_text(ip, COLOUR_GREEN)))

    # Credit for initial IP functions: http://code.activestate.com/recipes/66517/

    # Return a mask of n bits as a long integer
    ip_make_mask = lambda s, n: (2<<n-1)-1

    # Convert decimal dotted quad string to long integer
    def ip_strton(s, ip): return struct.unpack('<L',socket.inet_aton(ip))[0]

    def ip_network_mask(s, ip, bits):
        # Convert a network address to a long integer
        return s.ip_strton(ip) & s.ip_make_mask(int(bits))

    def ip_addrn_in_network(s, ip, net):
        # Is a numeric address in a network?
        return ip & net == net

    def ip_validate_address(s, candidate):
        try:
            ip = socket.gethostbyname(candidate)
            return (True, s.ip_strton(ip), ip)
        except socket.gaierror:
            s.errors.append("Unable to resolve: %s" % colour_text(candidate, COLOUR_GREEN))
            return (False, None, None)

    def ip_validate_cidr(s, candidate):
        a = candidate.split("/")[0]
        m = candidate.split("/")[1]
        try:
            if socket.gethostbyname(a) and int(m) <= 32: return (True, self.ip_network_mask(a, m))
        except socket.gaierror: pass

        s.errors.append("Invalid CIDR address: %s" % colour_text(candidate, COLOUR_GREEN))
        return (False, None)

    def is_allowed(self, address):
        # Blacklist/Whitelist filtering
        allowed = True

        if len(self.allowed_addresses) or len(self.allowed_networks):
            # Whitelist processing, address is not allowed until it is cleared.
            allowed = False

            if address in [a[2] for a in self.allowed_addresses]: allowed = True
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

            if address in [a[2] for a in self.denied_addresses]: allowed = False
            else:
                # Try checking denied networks
                cn = self.ip_strton(address)
                for n in [n[0] for n in self.denied_networks]:
                    if self.ip_addrn_in_network(cn, n):
                        allowed = False
                        break
        return allowed

    def load_access_file(s, fn, path, header):
        if not os.path.isfile(path):
            s.errors.append("Path to %s file does not exist: %s" % (header, colour_text(path, COLOUR_GREEN)))
            return False
        with open(path) as f:
            for l in f.readlines(): fn(l)

    def load_blacklist_file(s, path): return s.load_access_file(s.add_blacklist, path, "blacklist")

    def load_whitelist_file(s, path): return s.load_access_file(s.add_whitelist, path, "whitelist")

# Script Classes

TITLE_BIND = "bind"
TITLE_PORT = "port"
TITLE_VERBOSE="verbose"

TITLE_BALANCE_RANDOM = "random-target"
TITLE_BALANCE_ROUND_ROBIN = "round-robin-target"

TITLE_TARGET_PORT = "target-port"
TITLE_TARGET_SSL = "target-ssl"
TITLE_TARGET_SSL_INSECURE = "target-ssl-insecure"

TITLE_SSL_CERT = "SSL certfile"
TITLE_SSL_KEY = "SSL keyfile"

TITLE_ALLOW = "allow address/range"
TITLE_ALLOW_FILE = "allow address/range file"
TITLE_DENY = "deny address/range"
TITLE_DENY_FILE = "deny address/range file"

class TcpRelayServer:

    DEFAULT_BIND = "0.0.0.0"
    DEFAULT_PORT = 4444
    DEFAULT_TARGET_PORT = 4444

    def __init__(self):

        self.access = NetAccess()

        ## Arguments
        args = ArgHelper()
        args.add_validator(self.validate_version)
        args.set_operand_help_text('target[:port] [target-2[:port]] ...')

        # Short flags
        args.add_opt(OPT_TYPE_FLAG, "v", TITLE_VERBOSE, "Verbose output.")

        # Short opts

        args.add_opt(OPT_TYPE_SHORT, "b", TITLE_BIND, "Address to bind to.", default = self.DEFAULT_BIND, default_announce = True, default_colour = COLOUR_GREEN)
        args.add_opt(OPT_TYPE_SHORT, "p", TITLE_PORT, "Specify server bind port.", converter = int, default = self.DEFAULT_PORT, default_announce = True)
        args.add_opt(OPT_TYPE_LONG, TITLE_TARGET_PORT, TITLE_TARGET_PORT, 'Specify default target port.', default = self.DEFAULT_TARGET_PORT, default_announce = True)
        args.add_opt(OPT_TYPE_LONG_FLAG, TITLE_TARGET_SSL, TITLE_TARGET_SSL, 'Indicate that the target is SSL-secured.')
        args.add_opt(OPT_TYPE_LONG_FLAG, TITLE_TARGET_SSL_INSECURE, TITLE_TARGET_SSL_INSECURE, 'Indicate that the target is SSL-secured, and that the relay should ignore certificate verification errors.')

        args.add_opt(OPT_TYPE_LONG_FLAG, TITLE_BALANCE_RANDOM, TITLE_BALANCE_RANDOM, 'Select between multiple targets at random.')
        args.add_opt(OPT_TYPE_LONG_FLAG, TITLE_BALANCE_ROUND_ROBIN, TITLE_BALANCE_ROUND_ROBIN, 'Rotate between targets (default).')

        args.add_opt(OPT_TYPE_SHORT, "a", TITLE_ALLOW, "Add network address or CIDR range to whitelist.", multiple = True)
        args.add_opt(OPT_TYPE_SHORT, "A", TITLE_ALLOW_FILE, "Add addresses or CIDR ranges in file to whitelist.", multiple = True)
        args.add_opt(OPT_TYPE_SHORT, "d", TITLE_DENY, "Add network address or CIDR range to blacklist.", multiple = True)
        args.add_opt(OPT_TYPE_SHORT, "D", TITLE_DENY_FILE, "Add addresses or CIDR ranges in file to blacklist.", multiple = True)

        args.add_opt(OPT_TYPE_SHORT, "c", TITLE_SSL_CERT, "SSL certificate file path (PEM format). Can also contain the SSL key.")
        args.add_opt(OPT_TYPE_SHORT, "k", TITLE_SSL_KEY, "SSL key file path (PEM format).")

        args.add_validator(self.validate_common_arguments)
        args.add_validator(self.validate_access)
        args.add_validator(self.validate_ssl)

        self.args = args

        self.active_fds = set()
        self.sessions = {}
        self.targets = []

    def get_target_round_robin(s):
        s._round_robin_index = (getattr(s, '_round_robin_index', -1) + 1) % len(s.targets)
        return s.targets[s._round_robin_index]

    def init_server(self):
        self.server_socket = self.new_socket()
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.args[TITLE_SSL_CERT]:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(self.args[TITLE_SSL_CERT], keyfile=self.args[TITLE_SSL_KEY])
            self.init_socket(self.server_socket)
            self.server_socket = ctx.wrap_socket(self.server_socket, server_side=True, do_handshake_on_connect=False)

        self.client_ctx = None
        if self.args[TITLE_TARGET_SSL] or self.args[TITLE_TARGET_SSL_INSECURE]:
            self.client_ctx = ssl.create_default_context()
            if self.args[TITLE_TARGET_SSL_INSECURE]:
                self.client_ctx.check_hostname = False
                self.client_ctx.verify_mode = ssl.CERT_NONE

        self.server_socket.bind((self.args[TITLE_BIND], self.port))
        self.server_socket.listen(50)

        self.epoll_socket = select.epoll()
        self.register_socket(self.server_socket, EPOLLIN | EPOLLET)

        return True

    def init_socket(s, so):
        os.set_blocking(so.fileno(), False)
        so.setblocking(False)
        fcntl.fcntl(so, fcntl.F_SETFL, os.O_NONBLOCK) # Redundant, but to be absolutely sure...

    def is_loop(s, target_addr, server_addr):
        if target_addr[1] != server_addr[1]:
            # Non-matching port. Barring forwarding shenanigans, not a loop.
            return False

        # Shortcut for loopback stuff.
        # The proper, sophisticated way to do the check
        # for whether or not we are targetting a loopback address
        # would be to co-opt the methods of NetAccess class
        # to check the address numerically. However, since we
        # are dealing with the static 127.0.0.0/8 range, a
        # startswith check for the 4 bytes of "127." will be faster
        # than doing a bunch of conversions.
        if target_addr[0].startswith("127."):
            return True

        local_addresses = socket.gethostbyname_ex(socket.gethostname())[2]
        # Target is a local address and we are bound to a local address.
        if target_addr[0] in local_addresses and server_addr[0] in ["0.0.0.0", target_addr[0]]:
            return True

        # Run through all options, not a loop.
        return False

    def new_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.init_socket(s)
        return s

    def print_summary(s):
        # Summarize arguments
        if s.verbose: print_notice('Additional information shall be printed.')

        if len(s.targets) == 1:
            s.get_target = lambda: s.targets[0]

            t = s.get_target()
            print_notice('Relaying TCP connections on %s to %s' % (colour_addr(s.args[TITLE_BIND], s.port), t))

        else:
            print_notice('Relaying TCP connections on %s to the following hosts:' % colour_addr(s.args[TITLE_BIND], s.port))
            for t in s.targets: print_notice('  * %s' % t)

            if s.args[TITLE_BALANCE_RANDOM]: s.get_target = lambda: s.targets[random.randint(0, len(s.targets)-1)]
            else: s.get_target = s.get_target_round_robin

        if s.args[TITLE_SSL_CERT]:
            print_notice('SSL-encrypting incoming data with certificate: %s' % colour_green(s.args[TITLE_SSL_CERT]))
            if s.args[TITLE_SSL_KEY]: print_notice('SSL key file: %s' % colour_green(s.args[TITLE_SSL_KEY]))

        if s.args[TITLE_TARGET_SSL] or s.args[TITLE_TARGET_SSL_INSECURE]:
            print_notice('Target(s) are assumed to be SSL-secured')
            if s.args[TITLE_TARGET_SSL_INSECURE]: print_notice('SSL certificate verification is disabled.')

    def register_session(s, session):
        if session.src not in s.sessions: s.sessions[session.src.fileno()] = session
        if session.dst not in s.sessions: s.sessions[session.dst.fileno()] = session

    def register_socket(s, sock, flags):
        fd = sock.fileno()
        try:
            s.epoll_socket.register(fd, flags)
        except FileExistsError:
            # Observed to happen when sending an OpenVPN-TCP connection over the relay.
            s.epoll_socket.modify(fd, flags)
        s.active_fds.add(fd)

    def resolve_port(s, value, label):
        try:
            port = int(value)
            if port < 0 or port > 65535: return None, "%s must be 0-65535. Given: %s" % (label, colour_text(port))
            return port, None
        except ValueError: return None, '%s is invalid. Given: ' % (label, colour_text(port))

    def resolve_target_address(s, value):
        try: ip = socket.gethostbyname(value)
        except socket.gaierror: return None, value, "Unable to resolve: %s" % colour_text(value, COLOUR_BLUE)
        return ip, value, None

    def run(self):
        self.args.process(sys.argv)
        self.print_summary()
        if not self.init_server(): return 1

        try:
            while True:
                events = self.epoll_socket.poll(1)
                for fd, event in events:

                    if fd == self.server_socket.fileno():
                        try:
                            while True:
                                sock, addr = self.server_socket.accept()
                                self.init_socket(sock)

                                if not self.access.is_allowed(addr[0]):
                                    sock.shutdown(socket.SHUT_RDWR)
                                    sock.close()
                                    continue

                                session = TcpRelaySession(self, sock, addr)
                                session.handle_connection()

                        except (BlockingIOError, socket.error) as e: pass
                        continue

                    session = self.sessions.get(fd)
                    if session: session.handle_data(fd, event)

        finally: self.shutdown()
        return 0

    def shutdown(s):
        for i in list(s.active_fds): s.unregister_descriptor(i)
        s.epoll_socket.close()
        s.server_socket.close()

    def unregister_descriptor(s, fd):
        s.epoll_socket.unregister(fd)
        s.active_fds.remove(fd)

    def unregister_socket(s, sock):
        s.unregister_descriptor(sock.fileno())

    def validate_access(self, args):
        a = self.access
        for i in args[TITLE_ALLOW]: a.add_whitelist(i)
        for i in args[TITLE_ALLOW_FILE]: a.load_whitelist_file(i)
        for i in args[TITLE_DENY]: a.add_blacklist(i)
        for i in args[TITLE_DENY_FILE]: a.load_whitelist_file(i)
        return a.errors

    def validate_common_arguments(self, args):
        errors = []
        self.verbose = args[TITLE_VERBOSE]

        self.port, port_error = self.resolve_port(args[TITLE_PORT], 'Bind port')
        if port_error: errors.append(port_error)

        for target_items in [t.split(':') for t in self.args.operands]:

            target_ip, target_addr, target_err = self.resolve_target_address(target_items[0])
            if target_err: errors.append(target_err)

            port_label = 'Target port for %s' % colour_blue(target_addr)
            if len(target_items) > 1:
                target_port, port_err = self.resolve_port(target_items[1], port_label)
            else:
                target_port, port_err = self.resolve_port(args[TITLE_TARGET_PORT], port_label)
            if port_err: errors.append(target_err)

            # Check for obvious loops
            # If there is a problem with the IP/port information from up above,
            # then we will not bother with this check because loop checking might give false positives.
            if not target_err and not port_err and self.is_loop((target_ip, target_port), (args[TITLE_BIND], args[TITLE_PORT])):
                errors.append("Bad target (avoiding a potential loop): %s" % colour_addr(target_ip, target_port, target_addr))

            # Always append target, even if it's generated a number of errors.
            # On account of the errors, this instance of the script won't survive past argument handling.
            self.targets.append(TcpRelayTarget(target_ip, target_port, target_addr))

        if not self.targets: errors.append('No relay target specified.')
        else:
            num_rotation_options = len([i for i in [TITLE_BALANCE_RANDOM, TITLE_BALANCE_ROUND_ROBIN] if args[i]])
            if num_rotation_options > 1:
                if len(self.targets) > 1: errors.append('Must only select one rotation type when using multiple targets.')
                # If there was only one target, let the user off with a warning.
                else: print_warning('%s rotation options selected, but only one target was specified.' % colour_text(num_rotation_options))

            # Sanity-check for the user to remind them that every target will be treated as SSL.
            if len(self.targets) > 1 and (args[TITLE_TARGET_SSL] or args[TITLE_TARGET_SSL_INSECURE]):
                print_warning('SSL endpoints enabled for multiple targets. %s target will be considered to be SSL-enabled.' % colour_text(len(self.targets)))

        return errors

    def validate_ssl(self, args):
        errors = []

        for label in [TITLE_SSL_CERT, TITLE_SSL_KEY]:
            if args[label] and not os.path.isfile(args[label]): errors.append("%s not found: %s" % (label, colour_green(args[label])))

        if TITLE_SSL_KEY in self.args and not TITLE_SSL_CERT in args:
            errors.append('%s path provided, but no %s path was provided.' % (TITLE_SSL_KEY, TITLE_SSL_CERT))

        if not errors and args[TITLE_SSL_CERT]:
            # No SSL errors so far. Attempt to SSL-wrap a TCP socket and see if we get any errors.
            try:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(args[TITLE_SSL_CERT], keyfile=args[TITLE_SSL_KEY])
            except SSLError as e:
                m = "Unexpected %s: " % colour_text(type(e).__name__, COLOUR_RED)
                if re.match("^\[SSL\] PEM lib", str(e)):
                    # '[SSL] PEM lib (_ssl.c:2798)' is super-unhelpful, so we will provide our own error message.
                    # Unconfirmed: Is a missing key the only that can cause this?
                    m+= "Must specify a key file or a cert file that also contains a key."
                else:
                    # Append regular error message
                    m += str(e)
                errors.append(m)

        return errors

    def validate_version(self, args):
        if sys.version_info.major == 2: return 'This script currently only supports Python 3.'

STATE_UNCONNECTED = 1
STATE_UNINITIALIZED = 2
STATE_CONNECTED = 3

class TcpRelaySession:

    CLIENT_FLAGS = EPOLLET | EPOLLIN | EPOLLONESHOT | EPOLLPRI | EPOLLRDHUP

    def __init__(s, srv, src_sock, addr):
        s.server = srv
        s.verbose = srv.verbose
        s.target = srv.get_target()

        s.running = True
        s.src = src_sock
        s.addr = addr

        if s.server.args[TITLE_SSL_CERT]:
            s.state_client = STATE_UNINITIALIZED
        else: s.state_client = STATE_CONNECTED
        s.state_server = STATE_UNCONNECTED

        s.dst = srv.new_socket()
        srv.register_session(s)

    get_arrow_string = lambda s: '%s->%s' % (colour_addr(s.addr[0], s.addr[1]), s.target)

    def handle_connection(self):

        if self.state_client != STATE_CONNECTED:

            try:
                self.src.do_handshake()
                self.state_client = STATE_CONNECTED

                if self.verbose: print_notice('Client SSL initialized for %s' % self.get_arrow_string())
            except (SSLWantReadError, SSLWantWriteError, BlockingIOError) as e:
                self.re_arm(self.src, EPOLLIN | EPOLLET | EPOLLRDHUP | EPOLLONESHOT)
            except (SSLError, OSError) as e:
                self.shutdown()

        rearm_server = False
        if self.running and self.state_server == STATE_UNCONNECTED:

            target_addr = (self.target.ip, self.target.port)
            if self.verbose: log_notice('Attempting: %s' % self.get_arrow_string())

            try:
                try: self.dst.connect(target_addr)
                except socket.error as e:
                    # errno.EISCON has been observed to happen when running the relay on WSL.
                    # Uncertain how widespread the problem is.
                    # Any other socket error should be considered to be at the very least a failure of
                    #   this immediate connection attempt.
                    if e.errno != errno.EISCONN: raise
                rearm_server = True

                if self.verbose: print_notice('Completed TCP connection: %s' % self.get_arrow_string())

                if self.server.client_ctx:
                    self.dst = self.server.client_ctx.wrap_socket(
                        self.dst,
                        server_hostname=self.target.hostname,
                        do_handshake_on_connect=False
                    )

                    self.state_server = STATE_UNINITIALIZED
                else:
                    self.state_server = STATE_CONNECTED
                    self.server.register_socket(self.src, TcpRelaySession.CLIENT_FLAGS)

            except BlockingIOError:
                # Connection not immediately successful, but not already in the pending list (initial accept loop).
                self.server.register_socket(self.dst, EPOLLOUT)
            except (ConnectionError, OSError) as e:
                # ConnectionError: Likely a reset connection (target not listening?)
                # OSError: Possibly a timeout, or no route to host.
                if self.verbose: log_error('Connection %s: %s' % (self.get_arrow_string(), e))
                self.shutdown()

        if self.running and self.state_server == STATE_UNINITIALIZED:

            rearm_server = False

            try:
                self.dst.do_handshake()
                rearm_server = True

                self.state_server = STATE_CONNECTED
                self.register_socket(self.src, TcpRelaySession.CLIENT_FLAGS)

                if self.verbose: print_notice('Server SSL initialized for %s' % self.get_arrow_string())
            except (SSLWantReadError, SSLWantWriteError, BlockingIOError) as e:
                self.re_arm(self.dst, TcpRelaySession.CLIENT_FLAGS)
            except ssl.SSLCertVerificationError as e:
                if self.verbose: print_error('Failed to verify SSL certificate for %s in %s: %s' % (colour_blue(self.target.hostname), self.get_arrow_string(), e))
                self.shutdown()
            except (SSLError, OSError) as e:
                if self.verbose: print_error('SSL handshake error error for %s: %s' % (self.get_arrow_string(), e))
                self.shutdown()

        if rearm_server: self.re_arm(self.dst)

    def handle_data(self, fd, event):

        if fd == self.src.fileno():
            sock_in = self.src
            sock_out = self.dst

            if (event & EPOLLIN and self.state_client == STATE_UNINITIALIZED): self.handle_connection()
        else:
            sock_in = self.dst
            sock_out = self.src

            if (event & EPOLLOUT and self.state_server == STATE_UNCONNECTED) or (event & EPOLLIN and self.state_server == STATE_UNINITIALIZED):
                self.handle_connection() # Update on pending connection. Try again.

        if not (self.state_client == STATE_CONNECTED and self.state_server == STATE_CONNECTED):
            self.re_arm(sock_in)
            return

        # Check for closing messages
        closing = event & (EPOLLHUP | EPOLLRDHUP)
        data = None
        force_rearm = False

        if event & EPOLLPRI: sock_out.send(sock_in.read(1, socket.MSG_OOB), socket.MSG_OOB)

        if event & EPOLLIN:
            try:
                # Note: Originally, I had a 'while True' loop inside of this try/catch
                #        that broke when no data was read. This worked fine for vanilla
                #        connections, but it did not play nice with calling SSLSocket.recv()
                #        with a client->relay connection using SSL.
                #       The solution seems to be to only read data once per invocation of epoll.poll()/handle_data()

                data = sock_in.recv(1024)
                if data: sock_out.send(data)
            except (SSLWantReadError, SSLWantWriteError): force_rearm = True
            except socket.error as e: print_exception(e, self)

        if closing and not (data or force_rearm): self.shutdown() # Double-check that no data was read
        else: self.re_arm(sock_in) # Re-arm socket

    def re_arm(s, sock, flags = 0):
        if s.running and sock.fileno() > 0: s.server.epoll_socket.modify(sock.fileno(), flags or s.CLIENT_FLAGS)

    def shutdown(s):
        if not s.running: return
        if s.verbose: log_notice('Closing: %s' % s.get_arrow_string())

        subjects = [(s.state_server, s.dst, True), (s.state_client, s.src, s.state_server == STATE_CONNECTED)]
        for state, sock, do_deregister in subjects:
            fd = sock.fileno()
            del s.server.sessions[fd]

            if do_deregister:
                s.server.unregister_socket(sock)

            try: sock.shutdown(socket.SHUT_RDWR)
            except: pass
            sock.close()

        s.running = False

class TcpRelayTarget(object):
    def __init__(s, t_ip, t_port, t_host):
        s.ip = t_ip
        s.port = t_port
        s.hostname = t_host
    __str__ = lambda s: colour_addr(s.ip, s.port, s.hostname)

# Run
if __name__ == '__main__':
    try: exit(TcpRelayServer().run())
    except KeyboardInterrupt:
        print('')
        exit(130)
