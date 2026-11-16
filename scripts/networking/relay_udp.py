#!/usr/bin/env python3

from __future__ import print_function

# General
import errno, getopt, os, random, re, sys, time
from collections import deque

# Networking
import fcntl, select, socket, struct
from select import EPOLLERR, EPOLLHUP, EPOLLIN, EPOLLOUT

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


def colour_addr(ip, port, host=None):
    if host and host != ip:
        return '[%s:%s (%s)]' % (colour_blue(ip), colour_text(port), colour_blue(host))
    return '%s:%s' % (colour_blue(ip), colour_text(port))


def colour_blue(text):
    return colour_text(text, COLOUR_BLUE)


def colour_green(text):
    return colour_text(text, COLOUR_GREEN)


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

# Accepted (case-insensitive) values for flags set through environment variables.
#   Empty values are treated as unset.
ENV_FLAG_TRUE = ("1", "true", "yes", "on")
ENV_FLAG_FALSE = ("0", "false", "no", "off")


class ArgHelper:

    args = {}
    defaults = {}
    raw_args = {}
    operands = []

    operand_environment = None
    operand_text = None

    errors = []
    validators = []

    opts = {
        OPT_TYPE_FLAG: {},
        OPT_TYPE_SHORT: {},
        OPT_TYPE_LONG: {},
        OPT_TYPE_LONG_FLAG: {},
    }
    opts_by_label = {}

    def __init__(self):
        self.add_opt(
            OPT_TYPE_FLAG,
            "h",
            TITLE_HELP,
            description="Display a help menu and then exit.",
        )

    def __contains__(self, arg):
        return arg in self.args

    def __getitem__(self, arg, default=None):
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
        # Environment variables are converted into self.args during validation.
        value = self.args.get(arg)
        if value is None:
            value = self.defaults.get(arg)

        if value is None:
            return default
        return value

    def __setitem__(self, key, value):
        self.args[key] = value

    def add_opt(
        self,
        opt_type,
        flag,
        label,
        description=None,
        required=False,
        default=None,
        default_colour=None,
        default_announce=False,
        environment=None,
        converter=str,
        multiple=False,
        strict_single=False,
        action=None,
    ):

        if opt_type not in self.opts:
            raise Exception("Bad option type: %s" % opt_type)

        has_arg = opt_type & MASK_OPT_TYPE_ARG

        prefix = "-"
        match_pattern = "^[a-z0-9]$"
        if opt_type & MASK_OPT_TYPE_LONG:
            prefix = "--"
            match_pattern = r'^[a-z0-9\-]+$'  # ToDo: Improve on this regex?

        arg = prefix + flag

        # Check for errors. Developer errors get intrusive exceptions instead of the error list.
        if not label:
            raise Exception("No label defined for flag: %s" % arg)
        if not flag:
            raise Exception("No flag defined for label: %s" % label)
        if not opt_type & MASK_OPT_TYPE_LONG and len(flag) - 1:
            raise Exception(
                "Short options must be 1-character long."
            )  # A bit redundant, but more informative
        if not re.match(match_pattern, flag, re.IGNORECASE):
            raise Exception("Invalid flag value: %s" % flag)  # General format check
        for g in self.opts:
            if (
                opt_type & MASK_OPT_TYPE_LONG == g & MASK_OPT_TYPE_LONG
                and arg in self.opts[g]
            ):
                raise Exception("Flag already defined: %s" % label)
        if label in self.opts_by_label:
            raise Exception("Duplicate label (new: %s): %s" % (arg, label))
        if multiple and strict_single:
            raise Exception(
                "Cannot have an argument with both 'multiple' and 'strict_single' set to True."
            )
        if action and has_arg:
            raise Exception("Only flags can have an action: %s" % label)
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
        obj.action = action

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
        l = ["%s=" % key for key in sorted(self.opts[OPT_TYPE_LONG].keys())] + sorted(
            self.opts[OPT_TYPE_LONG_FLAG].keys()
        )
        return [re.sub("^-+", "", i) for i in l]

    def describe_environment(self, base, multiple=False):
        if multiple:
            return "%s, %s" % (colour_text(base), colour_text("%s_<n>" % base))
        return colour_text(base)

    def get_environment_names(self, base, multiple=False):
        # Get the environment variable names to check for an option, in order.
        # Options that can be specified multiple times accept the base name as well as
        #   any name with a zero-or-greater integer suffix (e.g. BASE_0, BASE_1, etc).
        #   One does not exclude the other. BASE, BASE_0, and BASE_1 are all checked.
        if not multiple:
            return [base]
        # Scanning the whole environment is probably less efficient than counting up from
        #   BASE_0 until a name is missing, but this also covers accidental gaps in numbering
        #   (e.g. BASE_0 and BASE_2 with no BASE_1). It is a one-time argument-parsing cost.
        pattern = re.compile(r"^%s_([0-9]+)$" % re.escape(base))
        numbered = []
        for key in os.environ:
            m = pattern.match(key)
            if m:
                numbered.append((int(m.group(1)), key))
        return [base] + [key for index, key in sorted(numbered)]

    def get_environment_values(self, base, multiple=False):
        # Treat empty values as unset.
        return [
            os.environ[n]
            for n in self.get_environment_names(base, multiple)
            if os.environ.get(n)
        ]

    def convert_value(self, raw_value, opt):
        value = None

        try:
            value = opt.converter(raw_value)
        except:
            pass

        if value is None:
            self.errors.append(
                "Unable to convert %s to %s: %s"
                % (
                    colour_text(opt.label),
                    opt.converter.__name__,
                    colour_text(raw_value),
                )
            )

        return value

    get = __getitem__

    def hexit(self, exit_code=0):

        s = "./%s" % os.path.basename(sys.argv[0])
        lines = []
        for label, section in [
            ("Flags", OPT_TYPE_FLAG),
            ("Options", OPT_TYPE_SHORT),
            ("Long Flags", OPT_TYPE_LONG_FLAG),
            ("Long Options", OPT_TYPE_LONG),
        ]:
            if not self.opts[section]:
                continue

            lines.append("%s:" % label)
            for f in sorted(self.opts[section].keys()):
                obj = self.opts[section][f]
                s += obj.get_printout_usage(f)
                lines.append(obj.get_printout_help(f))

        if self.operand_text:
            s += " %s" % self.operand_text
            if self.operand_environment:
                lines.append("Operands:")
                lines.append(
                    "  %s (Environment: %s)"
                    % (
                        self.operand_text,
                        self.describe_environment(self.operand_environment, True),
                    )
                )

        _print_message(COLOUR_PURPLE, "Usage", s)
        for l in lines:
            print(l)

        if exit_code >= 0:
            exit(exit_code)

    def last_operand(self, default=None):
        if not len(self.operands):
            return default
        return self.operands[-1]

    def load_args(self, cli_args=[]):
        if cli_args == sys.argv:
            cli_args = cli_args[1:]

        if not cli_args:
            return True

        try:
            output_options, self.operands = getopt.gnu_getopt(
                cli_args, self._get_opts(), self._get_opts_long()
            )
        except Exception as e:
            self.errors.append("Error parsing arguments: %s" % str(e))
            return False

        for opt, optarg in output_options:
            found = False
            for has_arg, opt_type_tuple in [
                (True, (OPT_TYPE_SHORT, OPT_TYPE_LONG)),
                (False, (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG)),
            ]:
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

    def process(self, args=[], exit_on_error=True, print_errors=True):

        # If basic argument loading failed, then don't bother to validate
        validate = self.load_args(args)

        if self[TITLE_HELP]:
            self.hexit(0)
        for obj in self.opts_by_label.values():
            if obj.action and self.args.get(obj.label):
                # Action flags run in place of normal processing, like the help menu.
                obj.action(self)
                exit(0)

        if validate:
            self.validate()

        if self.errors:
            if print_errors:
                for e in self.errors:
                    print_error(e)

            if exit_on_error:
                exit(1)
        return not self.errors

    def set_operand_environment(self, name):
        # Operands given on the command line take priority over environment variables.
        self.operand_environment = name

    def set_operand_help_text(s, text):
        s.operand_text = text

    def validate(self):
        for key in self.raw_args:
            obj = self.opts_by_label[key]
            if not obj.has_arg:
                self.args[obj.label] = True
            if not obj.multiple:
                if obj.strict_single and len(self.raw_args[obj.label]) > 1:
                    self.errors.append(
                        "Cannot have multiple %s values." % colour_text(obj.label)
                    )
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
        # Fall back to environment variables for options not given on the command line,
        #   converting them the same way as command line values.
        for label, obj in self.opts_by_label.items():
            if not obj.environment or label in self.raw_args or label in self.args:
                continue
            raw_values = self.get_environment_values(obj.environment, obj.multiple)
            if not raw_values:
                continue
            if not obj.has_arg:
                if raw_values[-1].lower() in ENV_FLAG_TRUE:
                    self.args[label] = True
                elif raw_values[-1].lower() not in ENV_FLAG_FALSE:
                    self.errors.append(
                        "Unrecognized %s value for %s: %s"
                        % (
                            colour_text(obj.environment),
                            colour_text(label),
                            colour_text(raw_values[-1]),
                        )
                    )
            elif obj.multiple:
                self.args[label] = []
                for i in raw_values:
                    value = self.convert_value(i, obj)
                    if value is not None:
                        self.args[label].append(value)
            else:
                value = self.convert_value(raw_values[-1], obj)
                if value is not None:
                    self.args[label] = value
        if self.operand_environment and not self.operands:
            self.operands = self.get_environment_values(self.operand_environment, True)
        for m in [
            self.opts_by_label[o].label
            for o in self.opts_by_label
            if self.opts_by_label[o].required
            and o not in self.raw_args
            and o not in self.args
        ]:
            self.errors.append("Missing %s value." % colour_text(m))
        for v in self.validators:
            r = v(self)
            if r:
                if isinstance(r, list):
                    self.errors.extend(r)  # Append all list items
                else:
                    self.errors.append(r)  # Assume that this is a string.


class OptArg:
    def __init__(s, a):
        s.opt_type = 0
        s.args = a

    def is_flag(s):
        return s.opt_type in (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG)

    def get_printout_help(self, opt):

        desc = self.description or "No description defined"

        if self.is_flag():
            s = "  %s: %s" % (opt, desc)
        else:
            s = "  %s <%s>: %s" % (opt, self.label, desc)

        notes = []
        if self.default_announce:
            # Manually going to defaults table allows this core module
            # to have its help display reflect retroactive changes to defaults.
            notes.append(
                "Default: %s"
                % colour_text(self.args.defaults.get(self.label), self.default_colour)
            )
        if self.environment:
            notes.append(
                "Environment: %s"
                % self.args.describe_environment(self.environment, self.multiple)
            )
        if notes:
            s += " (%s)" % ", ".join(notes)
        return s

    def get_printout_usage(self, opt):

        if self.is_flag():
            s = opt
        else:
            s = "%s <%s>" % (opt, self.label)

        if self.required:
            return " %s" % s
        return " [%s]" % s


# Network Access Class
###


class NetAccess:
    # Basic IPv4 CIDR syntax check
    REGEX_INET4_CIDR = r'^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

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
        for action, address_list, network_list in [
            ("Allowing", self.allowed_addresses, self.allowed_networks),
            ("Denying", self.denied_addresses, self.denied_networks),
        ]:
            l = []
            l.extend([("address", s, i) for n, s, i in address_list])
            l.extend([("network", s, s) for n, s in network_list])

            for title, ip, address in l:
                if ip == address:
                    print_notice(
                        "%s %s: %s"
                        % (action, title, colour_text(address, COLOUR_GREEN))
                    )
                else:
                    print_notice(
                        "%s %s: %s (%s)"
                        % (
                            action,
                            title,
                            colour_text(address, COLOUR_GREEN),
                            colour_text(ip, COLOUR_GREEN),
                        )
                    )

    # Credit for initial IP functions: http://code.activestate.com/recipes/66517/

    def ip_strton(self, ip):
        # Convert decimal dotted quad string integer
        a, b, c, d = struct.unpack('BBBB', socket.inet_aton(ip))
        return (a << 24) + (b << 16) + (c << 8) + d

    def ip_validate_address(self, candidate):
        try:
            ip = socket.gethostbyname(candidate)
            return (True, self.ip_strton(ip), ip)
        except socket.gaierror:
            self.errors.append(
                "Unable to resolve: %s" % colour_text(candidate, COLOUR_GREEN)
            )
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
        self.errors.append(
            "Invalid CIDR address: %s" % colour_text(candidate, COLOUR_GREEN)
        )
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
            self.errors.append(
                "Path to %s file does not exist: %s"
                % (header, colour_text(path, COLOUR_GREEN))
            )
            return False
        with open(path) as f:
            for l in f.readlines():
                fn(l)

    def load_blacklist_file(self, path):
        return self.load_access_file(self.add_blacklist, path, "blacklist")

    def load_whitelist_file(self, path):
        return self.load_access_file(self.add_whitelist, path, "whitelist")


# Script Classes

TITLE_BIND = "bind"
TITLE_PORT = "port"
TITLE_VERBOSE = "verbose"

TITLE_BALANCE_ALL = "all"
TITLE_BALANCE_RANDOM = "random-target"
TITLE_BALANCE_ROUND_ROBIN = "round-robin"

TITLE_NO_RESPONSE = 'no-reply'
TITLE_TARGET_PORT = 'target-port'

TITLE_TUNNEL_SERVER = 'tunnel-server'
TITLE_TUNNEL_PORT = 'tunnel-port'
TITLE_TUNNEL_INTAKE = 'tunnel-intake'
TITLE_LAZY_RECONNECT = 'lazy-reconnect'

TITLE_ALLOW = 'allow address/range'
TITLE_ALLOW_FILE = 'allow address/range file'
TITLE_DENY = 'deny address/range'
TITLE_DENY_FILE = 'deny address/range file'

TITLE_DOCKER_SKELETON = "docker-skeleton"
TITLE_DOCKER_SKELETON_ENV = "docker-skeleton-env"

DOCKER_SCRIPT_DIR = "/opt/relay"
DOCKER_SERVICE = "udp-relay"

# Largest datagram that will be read or relayed.
BUFFER_SIZE = 65535
# Datagrams waiting on a busy UDP socket. Anything past this is dropped.
BACKLOG_LIMIT = 1024
# Sessions with no traffic in either direction for this many seconds are closed.
SESSION_TIMEOUT = 60

# TCP Tunnel Protocol
#
# Each end of a tunnel connection opens by sending TUNNEL_HELLO. After that, each
#   datagram is sent as a frame: a TUNNEL_HEADER (frame type, session ID, payload length)
#   followed by the payload.
# Session IDs are chosen by the intake end, one per UDP client. The tunnel server keeps
#   a separate socket to its targets for each session ID on each connection.
###

TUNNEL_HELLO = b"UDPRELAY\x01"
TUNNEL_HEADER = struct.Struct("!BIH")
TUNNEL_FRAME_DATA = 1
TUNNEL_FRAME_CLOSE = 2

# Unsent tunnel data allowed to build up on a slow connection. Datagrams that would
#   go past this are dropped, the same as they would be on a congested UDP path.
TUNNEL_BUFFER_LIMIT = 4 * 1024 * 1024
TUNNEL_READ_SIZE = 256 * 1024
# Seconds allowed to connect and exchange TUNNEL_HELLO.
TUNNEL_CONNECT_TIMEOUT = 10
# Delay range in seconds between failed connection attempts. The delay doubles
#   with each failure in a row.
TUNNEL_RECONNECT_MIN = 1
TUNNEL_RECONNECT_MAX = 30
# Keepalive settings to notice a dead tunnel (e.g. a dropped NAT mapping) between
#   datagrams. Options missing on this platform are skipped.
TUNNEL_SOCKET_OPTIONS = [
    ("TCP_KEEPIDLE", 30),
    ("TCP_KEEPINTVL", 10),
    ("TCP_KEEPCNT", 3),
    ("TCP_USER_TIMEOUT", 60000),
]


def drain_backlog(sock, backlog):
    # Send queued (data, addr) datagrams. Returns True once the backlog is empty.
    while backlog:
        try:
            sock.sendto(*backlog[0])
        except BlockingIOError:
            return False
        except OSError:
            pass  # Undeliverable. Drop it like any other lost datagram.
        backlog.popleft()
    return True


def send_datagram(sock, backlog, data, addr):
    # Send a datagram, queueing it if the socket is busy.
    # Returns True if the backlog needs to wait for the socket to be writable.
    if len(backlog) < BACKLOG_LIMIT:
        backlog.append((data, addr))
    return not drain_backlog(sock, backlog)


class UdpRelayServer:

    DEFAULT_BIND = "0.0.0.0"
    DEFAULT_PORT = 4444
    DEFAULT_TARGET_PORT = 4444
    DEFAULT_TUNNEL_PORT = 4444

    def __init__(self):

        self.access = NetAccess()

        ## Arguments
        args = ArgHelper()
        args.add_validator(self.validate_version)
        args.set_operand_help_text('target[:port] [target-2[:port]] ...')
        args.set_operand_environment("UDP_RELAY_TARGET")

        # Short flags
        args.add_opt(
            OPT_TYPE_FLAG,
            "v",
            TITLE_VERBOSE,
            "Verbose output.",
            environment="UDP_RELAY_VERBOSE",
        )

        # Short opts

        args.add_opt(
            OPT_TYPE_SHORT,
            "b",
            TITLE_BIND,
            "Address to bind to.",
            default=self.DEFAULT_BIND,
            default_announce=True,
            default_colour=COLOUR_GREEN,
            environment="UDP_RELAY_BIND",
        )
        args.add_opt(
            OPT_TYPE_SHORT,
            "p",
            TITLE_PORT,
            "Specify UDP bind port. With --%s, UDP datagrams are only accepted if this is set."
            % TITLE_TUNNEL_SERVER,
            converter=int,
            default=self.DEFAULT_PORT,
            default_announce=True,
            environment="UDP_RELAY_PORT",
        )
        args.add_opt(
            OPT_TYPE_LONG,
            TITLE_TARGET_PORT,
            TITLE_TARGET_PORT,
            'Specify default target port. With --%s, this is the default tunnel server port.'
            % TITLE_TUNNEL_INTAKE,
            default=self.DEFAULT_TARGET_PORT,
            default_announce=True,
            environment="UDP_RELAY_TARGET_PORT",
        )

        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_BALANCE_ALL,
            TITLE_BALANCE_ALL,
            'Broadcast message to all targets at once. Only responses from the first responding target will be forwarded to the clinet.',
            environment="UDP_RELAY_ALL",
        )
        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_BALANCE_RANDOM,
            TITLE_BALANCE_RANDOM,
            'Select between multiple targets at random.',
            environment="UDP_RELAY_RANDOM_TARGET",
        )
        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_BALANCE_ROUND_ROBIN,
            TITLE_BALANCE_ROUND_ROBIN,
            'Rotate between targets (default).',
            environment="UDP_RELAY_ROUND_ROBIN",
        )

        args.add_opt(
            OPT_TYPE_FLAG,
            'n',
            TITLE_NO_RESPONSE,
            'Do not listen for any response from the target servers.',
            environment="UDP_RELAY_NO_REPLY",
        )

        # TCP tunnel options
        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_TUNNEL_SERVER,
            TITLE_TUNNEL_SERVER,
            'Host the outbound end of a TCP tunnel, relaying datagrams from instances running with --%s to the targets.'
            % TITLE_TUNNEL_INTAKE,
            environment="UDP_RELAY_TUNNEL_SERVER",
        )
        args.add_opt(
            OPT_TYPE_LONG,
            TITLE_TUNNEL_PORT,
            TITLE_TUNNEL_PORT,
            'Specify TCP bind port for --%s.' % TITLE_TUNNEL_SERVER,
            converter=int,
            default=self.DEFAULT_TUNNEL_PORT,
            default_announce=True,
            environment="UDP_RELAY_TUNNEL_PORT",
        )
        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_TUNNEL_INTAKE,
            TITLE_TUNNEL_INTAKE,
            'Relay datagrams through TCP tunnels. Targets are instances running with --%s.'
            % TITLE_TUNNEL_SERVER,
            environment="UDP_RELAY_TUNNEL_INTAKE",
        )
        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_LAZY_RECONNECT,
            TITLE_LAZY_RECONNECT,
            'Do not reconnect a dropped tunnel until a datagram needs it. Tunnels still connect at startup. By default, tunnels are reconnected right away.',
            environment="UDP_RELAY_LAZY_RECONNECT",
        )

        args.add_opt(
            OPT_TYPE_SHORT,
            "a",
            TITLE_ALLOW,
            "Add network address or CIDR range to whitelist.",
            multiple=True,
            environment="UDP_RELAY_ALLOW",
        )
        args.add_opt(
            OPT_TYPE_SHORT,
            "A",
            TITLE_ALLOW_FILE,
            "Add addresses or CIDR ranges in file to whitelist.",
            multiple=True,
            environment="UDP_RELAY_ALLOW_FILE",
        )
        args.add_opt(
            OPT_TYPE_SHORT,
            "d",
            TITLE_DENY,
            "Add network address or CIDR range to blacklist.",
            multiple=True,
            environment="UDP_RELAY_DENY",
        )
        args.add_opt(
            OPT_TYPE_SHORT,
            "D",
            TITLE_DENY_FILE,
            "Add addresses or CIDR ranges in file to blacklist.",
            multiple=True,
            environment="UDP_RELAY_DENY_FILE",
        )

        # Docker helpers. These intentionally have no environment variables.
        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_DOCKER_SKELETON,
            TITLE_DOCKER_SKELETON,
            "Print a sample docker compose service definition for this relay, then exit.",
            action=self.print_docker_skeleton,
        )
        args.add_opt(
            OPT_TYPE_LONG_FLAG,
            TITLE_DOCKER_SKELETON_ENV,
            TITLE_DOCKER_SKELETON_ENV,
            "Print sample env file content for the docker compose service, then exit.",
            action=self.print_docker_skeleton_env,
        )

        args.add_validator(self.validate_common_arguments)
        args.add_validator(self.validate_access)

        self.args = args

        # Socket handlers by file descriptor. Each has a socket and a handle_event() method.
        self.handlers = {}
        self.sessions = {}
        self.sessions_by_sid = {}
        self.tunnel_connections = set()
        self.targets = []
        self._last_sid = 0

    def close_session(s, session):
        if s.verbose:
            print_notice('Closing session: %s' % session)
        del s.sessions[session.key]
        session.close()

    def get_target_random(s):
        # Prefer targets that are not waiting out a failed tunnel connection.
        return [random.choice([t for t in s.targets if t.is_available()] or s.targets)]

    def get_target_round_robin(s):
        for i in range(len(s.targets)):
            s._round_robin_index = (getattr(s, '_round_robin_index', -1) + 1) % len(
                s.targets
            )
            target = s.targets[s._round_robin_index]
            if target.is_available():
                break
        # If nothing is available, settle for the next target in the rotation.
        return [target]

    def init_server(self):
        self.epoll_socket = select.epoll()
        bind = self.args[TITLE_BIND]

        try:
            if self.udp_enabled:
                sock = self.new_socket()
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((bind, self.port))
                self.watch(UdpListener(self, sock))

            if self.tunnel_server:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((bind, self.tunnel_port))
                sock.listen(socket.SOMAXCONN)
                sock.setblocking(False)
                self.watch(TunnelListener(self, sock))
        except OSError as e:
            print_exception(e, 'binding to %s' % colour_blue(bind))
            return False

        # Tunnels connect at startup, even with lazy reconnection.
        if self.tunnel_intake:
            for t in self.targets:
                t.connect()

        return True

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
        if target_addr[0] in local_addresses and server_addr[0] in [
            "0.0.0.0",
            target_addr[0],
        ]:
            return True

        # Run through all options, not a loop.
        return False

    def new_session(s, key, reply, label):
        session = UdpRelaySession(s, key, reply, label)
        s.sessions[key] = session
        if session.sid is not None:
            s.sessions_by_sid[session.sid] = session
        if s.verbose:
            print_notice('New session: %s' % session)
        return session

    def new_sid(s):
        s._last_sid = (s._last_sid + 1) & 0xFFFFFFFF
        return s._last_sid

    def new_socket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        os.set_blocking(s.fileno(), False)
        s.setblocking(False)
        fcntl.fcntl(
            s, fcntl.F_SETFL, os.O_NONBLOCK
        )  # Redundant, but to be absolutely sure...

        return s

    def print_docker_skeleton(self, args):
        script_name = os.path.basename(__file__)
        lines = [
            "services:",
            "  %s:" % DOCKER_SERVICE,
            "    image: python:3-alpine",
            "    restart: unless-stopped",
            '    command: ["python3", "%s/%s"]' % (DOCKER_SCRIPT_DIR, script_name),
            "    env_file:",
            "      # Generate with: %s --%s > %s.env"
            % (script_name, TITLE_DOCKER_SKELETON_ENV, DOCKER_SERVICE),
            "      - %s.env" % DOCKER_SERVICE,
            "    environment:",
            "      # Print output as it happens instead of buffering it.",
            '      PYTHONUNBUFFERED: "1"',
            "    ports:",
            "      # The container port must match UDP_RELAY_PORT (default: %d)."
            % self.DEFAULT_PORT,
            "      # With UDP_RELAY_TUNNEL_SERVER, this is only used if UDP_RELAY_PORT is set.",
            '      - "%d:%d/udp"' % (self.DEFAULT_PORT, self.DEFAULT_PORT),
            "      # For UDP_RELAY_TUNNEL_SERVER, the container port must match UDP_RELAY_TUNNEL_PORT (default: %d)."
            % self.DEFAULT_TUNNEL_PORT,
            '      # - "%d:%d/tcp"'
            % (self.DEFAULT_TUNNEL_PORT, self.DEFAULT_TUNNEL_PORT),
            "    volumes:",
            "      - %s:%s/%s:ro"
            % (os.path.realpath(__file__), DOCKER_SCRIPT_DIR, script_name),
            "      # Mount any extra files, then refer to them by their container paths",
            "      #   (e.g. UDP_RELAY_ALLOW_FILE=%s/files/allow.txt)."
            % DOCKER_SCRIPT_DIR,
            "      # - ./files:%s/files:ro" % DOCKER_SCRIPT_DIR,
            "    # Uncomment to reach services on the docker host as 'host.docker.internal'.",
            "    # extra_hosts:",
            '    #   - "host.docker.internal:host-gateway"',
        ]
        print("\n".join(lines))

    def describe_env_multiple(self, base):
        return "All of %s, %s_0, %s_1, etc are read and combined." % (base, base, base)

    def print_docker_skeleton_env(self, args):
        target_env = args.operand_environment
        lines = [
            "# Environment file for %s, used by the '%s' docker compose service."
            % (os.path.basename(__file__), DOCKER_SERVICE),
            "# Empty values are treated as unset.",
            "# Flags accept %s to enable, or %s to disable."
            % ("/".join(ENV_FLAG_TRUE), "/".join(ENV_FLAG_FALSE)),
            "# Values that can be given multiple times accept the base name as well as numbered",
            "#   suffixes (e.g. %s, %s_0, %s_1, etc)."
            % (target_env, target_env, target_env),
            "#   All of them are read, so setting one does not stop the others from being used.",
            "#   Numbered suffixes are read in numeric order after the base name, gaps are allowed.",
            "",
            "# Relay target, formatted as target[:port]. At least one target is required.",
            "#   With UDP_RELAY_TUNNEL_INTAKE, targets are tunnel servers instead.",
            "#   Names resolve from inside the container, so 'localhost' is the container itself.",
            "#   %s" % self.describe_env_multiple(target_env),
            "%s=" % target_env,
            "#%s_0=" % target_env,
            "#%s_1=" % target_env,
        ]
        for label, obj in args.opts_by_label.items():
            if not obj.environment:
                continue
            lines.extend(["", "# %s" % obj.description])
            if obj.multiple:
                lines.append("#   %s" % self.describe_env_multiple(obj.environment))
                lines.append("#%s=" % obj.environment)
                lines.extend(["#%s_%d=" % (obj.environment, i) for i in range(2)])
            elif not obj.has_arg:
                lines.append("#%s=false" % obj.environment)
            else:
                default = args.defaults.get(label)
                if default is None:
                    default = ""
                lines.append("#%s=%s" % (obj.environment, default))
        print("\n".join(lines))

    def print_summary(s):
        # Summarize arguments
        if s.verbose:
            print_notice('Additional information shall be printed.')

        if s.no_reply:
            print_notice('Not expecting or relaying any replies from target server(s).')

        if s.tunnel_intake and s.lazy_reconnect:
            print_notice(
                'Dropped tunnels will only be reconnected when a datagram needs them.'
            )

        sources = []
        if s.udp_enabled:
            sources.append(
                'UDP datagrams on %s' % colour_addr(s.args[TITLE_BIND], s.port)
            )
        if s.tunnel_server:
            sources.append(
                'tunnelled datagrams on TCP %s'
                % colour_addr(s.args[TITLE_BIND], s.tunnel_port)
            )
        source = ' and '.join(sources)

        # Kick off initialization with target-seeking being 'All'-mode.
        # Will be adjusted later in this method if this is not the case.
        s.get_targets = lambda: s.targets

        if len(s.targets) == 1:
            via = 'through the TCP tunnel at' if s.tunnel_intake else 'to'
            print_notice('Relaying %s %s %s' % (source, via, s.get_targets()[0]))

        else:
            hosts = 'TCP tunnels' if s.tunnel_intake else 'hosts'
            if s.args[TITLE_BALANCE_ALL]:
                print_notice(
                    'Relaying %s to all of the following %s:' % (source, hosts)
                )
            else:
                print_notice('Relaying %s to the following %s:' % (source, hosts))

            for t in s.targets:
                print_notice('  * %s' % t)

            if s.args[TITLE_BALANCE_ALL]:
                # Already initialized
                pass
            elif s.args[TITLE_BALANCE_RANDOM]:
                s.get_targets = s.get_target_random
            else:
                # Default to round-robin
                s.get_targets = s.get_target_round_robin

    def resolve_port(s, value, label):
        try:
            port = int(value)
            if port < 0 or port > 65535:
                return None, "%s must be 0-65535. Given: %s" % (
                    label,
                    colour_text(port),
                )
            return port, None
        except ValueError:
            return None, '%s is invalid. Given: %s' % (label, colour_text(value))

    def resolve_target_address(s, value):
        try:
            ip = socket.gethostbyname(value)
        except socket.gaierror:
            return (
                None,
                value,
                "Unable to resolve: %s" % colour_text(value, COLOUR_BLUE),
            )
        return ip, value, None

    def run(self):
        self.args.process(sys.argv)
        self.print_summary()
        if not self.init_server():
            return 1

        try:
            while True:
                for fd, event in self.epoll_socket.poll(1):
                    # A handler may have been closed by an earlier event in the same batch.
                    handler = self.handlers.get(fd)
                    if handler:
                        handler.handle_event(event)
                self.tick()

        finally:
            self.shutdown()
        return 0

    def set_events(s, handler, events):
        s.epoll_socket.modify(handler.socket.fileno(), events)

    def shutdown(s):
        for handler in list(s.handlers.values()):
            handler.socket.close()
        s.handlers.clear()
        s.epoll_socket.close()

    def tick(s):
        # Housekeeping, run on every pass of the main loop.
        now = time.time()
        for t in s.targets:
            t.tick(now)
        for c in list(s.tunnel_connections):
            c.check(now)

        # Look for expired sessions and clean them up.
        for session in [x for x in s.sessions.values() if x.is_closing()]:
            s.close_session(session)

    def unwatch(s, handler):
        # Must be called before closing the handler's socket.
        fd = handler.socket.fileno()
        if s.handlers.get(fd) is handler:
            del s.handlers[fd]
            s.epoll_socket.unregister(fd)

    def validate_access(self, args):
        a = self.access
        for i in args[TITLE_ALLOW]:
            a.add_whitelist(i)
        for i in args[TITLE_ALLOW_FILE]:
            a.load_whitelist_file(i)
        for i in args[TITLE_DENY]:
            a.add_blacklist(i)
        for i in args[TITLE_DENY_FILE]:
            a.load_blacklist_file(i)
        return a.errors

    def validate_common_arguments(self, args):
        errors = []
        self.all = args[TITLE_BALANCE_ALL]
        self.verbose = args[TITLE_VERBOSE]
        self.no_reply = args[TITLE_NO_RESPONSE]
        self.tunnel_server = args[TITLE_TUNNEL_SERVER]
        self.tunnel_intake = args[TITLE_TUNNEL_INTAKE]
        self.lazy_reconnect = args[TITLE_LAZY_RECONNECT]

        # A plain relay always listens for UDP datagrams.
        # A tunnel server only does so as well if a UDP port was explicitly given.
        self.udp_enabled = not self.tunnel_server or TITLE_PORT in args

        self.port, port_error = self.resolve_port(args[TITLE_PORT], 'Bind port')
        if port_error:
            errors.append(port_error)

        if self.tunnel_server:
            self.tunnel_port, port_error = self.resolve_port(
                args[TITLE_TUNNEL_PORT], 'Tunnel port'
            )
            if port_error:
                errors.append(port_error)
        elif TITLE_TUNNEL_PORT in args:
            print_warning(
                'Tunnel port given, but not hosting a tunnel server (--%s).'
                % TITLE_TUNNEL_SERVER
            )

        if self.lazy_reconnect and not self.tunnel_intake:
            print_warning(
                'Lazy reconnection only applies to tunnel intakes (--%s).'
                % TITLE_TUNNEL_INTAKE
            )

        # Local address that targets must not point back to.
        local_addr = None
        if self.tunnel_intake:
            if self.tunnel_server:
                local_addr = (args[TITLE_BIND], self.tunnel_port)
        elif self.udp_enabled:
            local_addr = (args[TITLE_BIND], self.port)

        target_class = TunnelTarget if self.tunnel_intake else UdpRelayTarget

        for target_items in [t.split(':') for t in self.args.operands]:

            target_ip, target_addr, target_err = self.resolve_target_address(
                target_items[0]
            )
            if target_err:
                errors.append(target_err)

            port_label = 'Target port for %s' % colour_blue(target_addr)
            if len(target_items) > 1:
                target_port, port_err = self.resolve_port(target_items[1], port_label)
            else:
                target_port, port_err = self.resolve_port(
                    args[TITLE_TARGET_PORT], port_label
                )
            if port_err:
                errors.append(port_err)

            # Check for obvious loops
            # If there is a problem with the IP/port information from up above,
            # then we will not bother with this check because loop checking might give false positives.
            if (
                local_addr
                and not target_err
                and not port_err
                and self.is_loop((target_ip, target_port), local_addr)
            ):
                errors.append(
                    "Bad target (avoiding a potential loop): %s"
                    % colour_addr(target_ip, target_port, target_addr)
                )

            # Always append target, even if it's generated a number of errors.
            # On account of the errors, this instance of the script won't survive past argument handling.
            self.targets.append(target_class(self, target_ip, target_port, target_addr))

        if not self.targets:
            errors.append('No relay target specified.')
        else:

            num_rotation_options = len(
                [
                    i
                    for i in [
                        TITLE_BALANCE_ALL,
                        TITLE_BALANCE_RANDOM,
                        TITLE_BALANCE_ROUND_ROBIN,
                    ]
                    if args[i]
                ]
            )
            if num_rotation_options > 1:
                if len(self.targets) > 1:
                    errors.append(
                        'Must only select one rotation type when using multiple targets.'
                    )
                # If there was only one target, let the user off with a warning.
                else:
                    print_warning(
                        '%s rotation options selected, but only one target was specified.'
                        % colour_text(num_rotation_options)
                    )

            if self.all:
                if len(self.targets) == 1:
                    print_warning('Multiply option enabled, but only one target.')
                    self.multiply = False  # Treat as a regular one-target relay.

        return errors

    def validate_version(self, args):
        if sys.version_info.major == 2:
            return 'This script currently only supports Python 3.'

    def watch(s, handler, events=EPOLLIN):
        fd = handler.socket.fileno()
        s.handlers[fd] = handler
        s.epoll_socket.register(fd, events)


class UdpListener:
    # Receives datagrams from UDP clients, and sends replies back to them.

    def __init__(s, srv, sock):
        s.srv = srv
        s.socket = sock
        s.backlog = deque()

    def handle_event(s, event):
        if event & EPOLLIN:
            try:
                while True:
                    data, addr = s.socket.recvfrom(BUFFER_SIZE)
                    if not s.srv.access.is_allowed(addr[0]):
                        continue

                    key = ('udp', addr)
                    session = s.srv.sessions.get(key) or s.srv.new_session(
                        key,
                        lambda reply, addr=addr: s.send_to(reply, addr),
                        colour_addr(addr[0], addr[1]),
                    )
                    session.send(data)
            except BlockingIOError:
                pass

        if event & EPOLLOUT and drain_backlog(s.socket, s.backlog):
            s.srv.set_events(s, EPOLLIN)

    def send_to(s, data, addr):
        if send_datagram(s.socket, s.backlog, data, addr):
            s.srv.set_events(s, EPOLLIN | EPOLLOUT)


class TunnelListener:
    # Accepts connections from tunnel intakes.

    def __init__(s, srv, sock):
        s.srv = srv
        s.socket = sock

    def handle_event(s, event):
        while True:
            try:
                sock, addr = s.socket.accept()
            except BlockingIOError:
                return
            except OSError as e:
                print_exception(e, 'accepting a tunnel connection')
                return

            if not s.srv.access.is_allowed(addr[0]):
                if s.srv.verbose:
                    print_notice(
                        'Denied tunnel connection from %s'
                        % colour_addr(addr[0], addr[1])
                    )
                sock.close()
                continue

            TunnelServerConnection(s.srv, sock, addr)


class TunnelStream:
    # Framed, non-blocking TCP stream. Shared by both ends of a tunnel.

    def __init__(s, srv):
        s.srv = srv
        s.socket = None
        s.connecting = False

    def check(s, now):
        if not s.socket:
            return
        if s.pending_error:
            s.close(str(s.pending_error))
        elif not s.hello_received and now - s.started > TUNNEL_CONNECT_TIMEOUT:
            s.close('timed out waiting for the tunnel to open')

    def disconnect(s):
        s.srv.unwatch(s)
        s.socket.close()
        s.socket = None
        s.connecting = False

    def flush(s):
        try:
            while s.outbuf:
                del s.outbuf[: s.socket.send(s.outbuf)]
        except BlockingIOError:
            pass
        except OSError as e:
            # Leave closing the connection to the event loop. This could have been
            #   called in the middle of relaying for one of this connection's sessions.
            s.pending_error = e
            return

        writing = bool(s.outbuf)
        if writing != s.writing:
            s.writing = writing
            s.srv.set_events(s, EPOLLIN | (EPOLLOUT if writing else 0))

    def handle_event(s, event):
        if event & EPOLLOUT:
            s.flush()
        if s.socket and event & (EPOLLIN | EPOLLHUP | EPOLLERR):
            s.read()
        if s.socket and s.pending_error:
            s.close(str(s.pending_error))

    def parse(s):
        if not s.hello_received:
            size = min(len(s.inbuf), len(TUNNEL_HELLO))
            if s.inbuf[:size] != TUNNEL_HELLO[:size]:
                s.close('peer is not a compatible UDP relay tunnel')
                return
            if size < len(TUNNEL_HELLO):
                return
            del s.inbuf[:size]
            s.hello_received = True
            s.on_hello()

        offset = 0
        while len(s.inbuf) - offset >= TUNNEL_HEADER.size:
            frame_type, sid, length = TUNNEL_HEADER.unpack_from(s.inbuf, offset)
            start = offset + TUNNEL_HEADER.size
            if len(s.inbuf) < start + length:
                break  # Wait for the rest of the frame.
            data = bytes(s.inbuf[start : start + length])
            offset = start + length

            if frame_type == TUNNEL_FRAME_DATA:
                s.on_data(sid, data)
            elif frame_type == TUNNEL_FRAME_CLOSE:
                s.on_close_session(sid)
            else:
                s.close('unknown tunnel frame type: %d' % frame_type)
                return
        del s.inbuf[:offset]

    def read(s):
        try:
            data = s.socket.recv(TUNNEL_READ_SIZE)
        except BlockingIOError:
            return
        except OSError as e:
            s.close(str(e))
            return

        if not data:
            s.close('connection closed by peer')
            return
        s.inbuf += data
        s.parse()

    def send_frame(s, frame_type, sid, data=b""):
        # Returns False if the frame was dropped.
        if not s.socket:
            return False
        if len(s.outbuf) + TUNNEL_HEADER.size + len(data) > TUNNEL_BUFFER_LIMIT:
            return False
        s.outbuf += TUNNEL_HEADER.pack(frame_type, sid, len(data))
        s.outbuf += data
        if not s.connecting:
            s.flush()
        return True

    def start(s, sock):
        sock.setblocking(False)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        for name, value in TUNNEL_SOCKET_OPTIONS:
            if hasattr(socket, name):
                sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, name), value)

        s.socket = sock
        s.inbuf = bytearray()
        s.outbuf = bytearray(TUNNEL_HELLO)
        s.hello_received = False
        s.pending_error = None
        s.started = time.time()


class TunnelServerConnection(TunnelStream):
    # Connection accepted from a tunnel intake.

    def __init__(s, srv, sock, addr):
        TunnelStream.__init__(s, srv)
        s.addr = addr
        s.start(sock)
        s.writing = False
        srv.watch(s, EPOLLIN)
        srv.tunnel_connections.add(s)
        s.flush()

    def __str__(s):
        return 'tunnel %s' % colour_addr(s.addr[0], s.addr[1])

    def close(s, reason):
        s.disconnect()
        s.srv.tunnel_connections.discard(s)
        for session in [x for k, x in s.srv.sessions.items() if k[0] is s]:
            s.srv.close_session(session)

        if s.hello_received:
            print_notice('Closed %s: %s' % (s, reason))
        else:
            print_warning('Rejected %s: %s' % (s, reason))

    def on_close_session(s, sid):
        session = s.srv.sessions.get((s, sid))
        if session:
            s.srv.close_session(session)

    def on_data(s, sid, data):
        key = (s, sid)
        session = s.srv.sessions.get(key) or s.srv.new_session(
            key,
            lambda reply: s.send_frame(TUNNEL_FRAME_DATA, sid, reply),
            '%s session %s' % (s, colour_text(sid)),
        )
        session.send(data)

    def on_hello(s):
        print_notice('Accepted %s' % s)


class TunnelTarget(TunnelStream):
    # Intake end of a tunnel, connecting out to a tunnel server.

    def __init__(s, srv, t_ip, t_port, t_host):
        TunnelStream.__init__(s, srv)
        s.ip = t_ip
        s.port = t_port
        s.hostname = t_host

        s.backoff = TUNNEL_RECONNECT_MIN
        s.failures = 0
        s.next_attempt = 0

    __str__ = lambda s: colour_addr(s.ip, s.port, s.hostname)
    get_addr = lambda s: (s.ip, s.port)

    def close(s, reason):
        s.disconnect()

        now = time.time()
        if s.hello_received:
            # A working tunnel dropped. Try again right away.
            s.backoff = TUNNEL_RECONNECT_MIN
            s.next_attempt = now
            print_warning(
                'Lost tunnel to %s: %s (%s)' % (s, reason, s.describe_retry(now))
            )
        else:
            s.next_attempt = now + s.backoff
            s.backoff = min(s.backoff * 2, TUNNEL_RECONNECT_MAX)
            # Only report the first failure in a row, unless being verbose.
            if not s.failures or s.srv.verbose:
                print_warning(
                    'Unable to open tunnel to %s: %s (%s)'
                    % (s, reason, s.describe_retry(now))
                )
            s.failures += 1

    def close_session(s, session):
        s.send_frame(TUNNEL_FRAME_CLOSE, session.sid)

    def connect(s):
        s.start(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        s.connecting = True
        s.writing = True
        s.srv.watch(s, EPOLLIN | EPOLLOUT)

        err = s.socket.connect_ex(s.get_addr())
        if err not in (0, errno.EINPROGRESS):
            s.close(os.strerror(err))

    def describe_retry(s, now):
        delay = max(0, int(round(s.next_attempt - now)))
        if s.srv.lazy_reconnect:
            if delay:
                return 'reconnecting when needed, no sooner than %ds' % delay
            return 'reconnecting when needed'
        if delay:
            return 'retrying in %ds' % delay
        return 'reconnecting'

    def handle_event(s, event):
        if s.connecting:
            err = s.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err:
                s.close(os.strerror(err))
                return
            try:
                s.socket.getpeername()
            except OSError:
                return  # Still connecting.
            s.connecting = False
        TunnelStream.handle_event(s, event)

    def is_available(s):
        # False while waiting out the delay after a failed connection attempt.
        return s.socket is not None or time.time() >= s.next_attempt

    def on_close_session(s, sid):
        pass  # The intake end decides when sessions end.

    def on_data(s, sid, data):
        session = s.srv.sessions_by_sid.get(sid)
        if session and s in session.targets:
            session.reply(data)

    def on_hello(s):
        s.backoff = TUNNEL_RECONNECT_MIN
        s.failures = 0
        print_notice('Opened tunnel to %s' % s)

    def send(s, session, data):
        if not s.socket and s.srv.lazy_reconnect and s.is_available():
            s.connect()
        # Datagrams are held while the tunnel is connecting, and dropped while it is down.
        s.send_frame(TUNNEL_FRAME_DATA, session.sid, data)

    def tick(s, now):
        if s.socket:
            s.check(now)
        elif not s.srv.lazy_reconnect and now >= s.next_attempt:
            s.connect()


class UdpRelaySession:
    def __init__(s, srv, key, reply, label):
        s.srv = srv
        s.key = key
        s.reply_to_client = reply
        s.label = label

        s.running = True
        s.time = time.time()

        s.targets = srv.get_targets()
        s.backlog = deque()
        s.socket = None
        s.sid = None

        if srv.tunnel_intake:
            # Tunnelled sessions share their tunnels' connections.
            s.sid = srv.new_sid()
        else:
            s.targets_addr = [t.get_addr() for t in s.targets]
            s.socket = srv.new_socket()
            srv.watch(s, s.get_events())

    def __str__(s):

        if len(s.targets) > 1:
            ts = colour_text('*')
        else:
            ts = s.targets[0]

        return '%s -> %s' % (s.label, ts)

    def close(s):
        if s.socket:
            s.srv.unwatch(s)
            s.socket.close()
            s.socket = None
        if s.sid is not None:
            s.srv.sessions_by_sid.pop(s.sid, None)
            for t in s.targets:
                t.close_session(s)

    def get_events(s):
        events = 0 if s.srv.no_reply else EPOLLIN
        if s.backlog:
            events |= EPOLLOUT
        return events

    def handle_event(s, event):
        # Data from a target server
        if event & EPOLLIN:
            try:
                while True:
                    data, addr = s.socket.recvfrom(BUFFER_SIZE)
                    if addr in s.targets_addr:
                        s.reply(data)
            except OSError:
                pass

        if event & EPOLLOUT:
            drain_backlog(s.socket, s.backlog)
            s.srv.set_events(s, s.get_events())

    def is_closing(s):
        return not s.backlog and (
            not s.running or time.time() - s.time > SESSION_TIMEOUT
        )

    def reply(s, data):
        s.time = time.time()
        s.reply_to_client(data)

    def send(s, data):
        s.time = time.time()
        for t in s.targets:
            t.send(s, data)

        # Without replies to wait for, a session with its own socket can close right away.
        # Tunnelled sessions stay open so that the tunnel server can keep using one
        #   socket for them, instead of opening a new one for every datagram.
        if s.srv.no_reply and s.socket:
            s.running = False


class UdpRelayTarget(object):
    def __init__(s, srv, t_ip, t_port, t_host):
        s.srv = srv
        s.ip = t_ip
        s.port = t_port
        s.hostname = t_host

    __str__ = lambda s: colour_addr(s.ip, s.port, s.hostname)
    get_addr = lambda s: (s.ip, s.port)
    is_available = lambda s: True

    def close_session(s, session):
        pass

    def send(s, session, data):
        if send_datagram(session.socket, session.backlog, data, s.get_addr()):
            s.srv.set_events(session, session.get_events())

    def tick(s, now):
        pass


# Run
if __name__ == '__main__':
    try:
        exit(UdpRelayServer().run())
    except KeyboardInterrupt:
        print('')
        exit(130)
