#!/usr/bin/env python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

# Basic includes
import base64, getopt, getpass, os, mimetypes, posixpath, re, shutil, ssl, socket, struct, sys, time, urllib
from random import randint

if sys.version_info[0] == 2:
    from BaseHTTPServer import HTTPServer
    from BaseHTTPServer import BaseHTTPRequestHandler

    from SocketServer import ThreadingMixIn

    from urllib import unquote
    from urlparse import parse_qs

    try:
        from cStringIO import StringIO
    except ImportError:
        from StringIO import StringIO

    FileNotFoundError = OSError
else:
    import http.client
    from http.server import HTTPServer
    from http.server import BaseHTTPRequestHandler

    from socketserver import ThreadingMixIn

    from urllib.parse import unquote
    from urllib.parse import parse_qs

    from io import StringIO

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message):
    print("%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message))

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
    print_error("Unexpected %s(%s%s, Line %s): %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, colour_text(fname, COLOUR_GREEN), lineno, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message)

# Variables

DEFAULT_AUTH_LIMIT = 5
DEFAULT_AUTH_PROMPT = "Authorization Required"
DEFAULT_AUTH_TIMEOUT = 300

DEFAULT_TIMEOUT = 10

DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = 8080

REGEX_INET4='^(([0-9]){1,3}\.){3}([0-9]{1,3})$'

TITLE_BIND = "bind"
TITLE_PORT = "port"
TITLE_TIMEOUT = "timeout"
TITLE_VERBOSE="verbose"

TITLE_AUTH_LIMIT = "attempt limit"
TITLE_AUTH_PROMPT = "prompt"
TITLE_AUTH_TIMEOUT = "attempt limit timeout"
TITLE_PASSWORD = "password"
TITLE_USER = "user"

TITLE_SSL_CERT = "SSL certfile"
TITLE_SSL_KEY = "SSL keyfile"

TITLE_ALLOW = "allow address/range"
TITLE_ALLOW_FILE = "allow address/range file"
TITLE_DENY = "deny address/range"
TITLE_DENY_FILE = "deny address/range file"

TITLE_USER_AGENT = "user-agent pattern"

AUTH_BAD_NOT_FOUND = 0
AUTH_BAD_PASSWORD = 1
AUTH_GOOD_CREDS = 2

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

import getopt, os, re, sys

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

args = ArgHelper()

# Short opts
args.add_opt(OPT_TYPE_FLAG, "v", TITLE_VERBOSE, "Verbose output.")
# Short flags
args.add_opt(OPT_TYPE_SHORT, "T", TITLE_TIMEOUT, "Read socket timeout (default: %s)." % colour_text(DEFAULT_TIMEOUT), converter = int, default = DEFAULT_TIMEOUT)
args.add_opt(OPT_TYPE_SHORT, "a", TITLE_ALLOW, "Add network address or CIDR range to whitelist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "A", TITLE_ALLOW_FILE, "Add addresses or CIDR ranges in file to whitelist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "b", TITLE_BIND, "Address to bind to (Default: %s)." % colour_text(DEFAULT_BIND, COLOUR_GREEN), default = DEFAULT_BIND)
args.add_opt(OPT_TYPE_SHORT, "d", TITLE_DENY, "Add network address or CIDR range to blacklist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "D", TITLE_DENY_FILE, "Add addresses or CIDR ranges in file to blacklist.", multiple = True)
args.add_opt(OPT_TYPE_SHORT, "p", TITLE_PORT, "Specify server bind port (Default: %s)." % colour_text(DEFAULT_PORT), converter = int, default = DEFAULT_PORT)

args.add_opt(OPT_TYPE_SHORT, "c", TITLE_SSL_CERT, "SSL certificate file path (PEM format). Can also contain the SSL key.")
args.add_opt(OPT_TYPE_SHORT, "k", TITLE_SSL_KEY, "SSL key file path (PEM format).")

# Long flags
args.add_opt(OPT_TYPE_LONG, "user-agent", TITLE_USER_AGENT, "Regular expression to match user agents. When this option is in use, the client must match at least one provided pattern.", multiple = True)
args.add_opt(OPT_TYPE_LONG, "auth-limit", TITLE_AUTH_LIMIT, "Number of attempts allowed within lockout period (0 for unlimited attempts).", converter = int, default = DEFAULT_AUTH_LIMIT, default_announce = True)
args.add_opt(OPT_TYPE_LONG, "auth-timeout", TITLE_AUTH_TIMEOUT, "Login attempts timeout in seconds (0 for unlimited).", converter = int, default = DEFAULT_AUTH_TIMEOUT, default_announce = True)
for default, title in [(DEFAULT_AUTH_PROMPT, TITLE_AUTH_PROMPT), ("", TITLE_USER), ("", TITLE_PASSWORD)]:
    args.add_opt(OPT_TYPE_LONG, title, title, "Specify authentication %s." % title, default = default)

def validate_common_arguments(self):
    errors = []

    port = self[TITLE_PORT]
    if port < 0 or port > 65535:
        errors.append("Port must be 0-65535. Given: %s" % colour_text(port))

    if self[TITLE_TIMEOUT] <= 0:
        errors.append("Timeout must be a positive value. Given: %s" % colour_text(self.args[TITLE_PORT]))

    for label in [TITLE_SSL_CERT, TITLE_SSL_KEY]:
        path = self[label]
        if path and not os.path.isfile(path):
            errors.append("%s not found: %s" % (label, colour_text(path, COLOUR_GREEN)))

    if TITLE_SSL_KEY in self.args and not TITLE_SSL_CERT in self.args:
        errors.append("%s path provided, but no %s path was provided." % (TITLE_SSL_KEY, TITLE_SSL_CERT))

    if self[TITLE_AUTH_LIMIT] < 0:
        errors.append('Auth limit must be greater than or equal to 0.')
    if self[TITLE_AUTH_TIMEOUT] < 0:
        errors.append('Auth timeout must be greater than or equal to 0.')

    if TITLE_USER in self or TITLE_PASSWORD in self:
        authentication_stores.append(SimpleAuthStore(self[TITLE_USER], self[TITLE_PASSWORD]))
    else:
        if TITLE_AUTH_LIMIT in self.args:
            print_warning("Auth limit specified, but no authentication credentials were specified.")
        if TITLE_AUTH_TIMEOUT in self.args:
            print_warning("Auth timeout specified, but no authentication credentials were specified.")

    return errors

args.add_validator(validate_common_arguments)

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

def validate_common_directory(self):
    directory = get_target()
    if not os.path.isdir(directory):
        return "Path %s does not seem to exist." % colour_text(os.path.realpath(directory), COLOUR_GREEN)

# End option definitions

def announce_common_arguments(verb = "Hosting content"):

    bind_address, bind_port, directory = get_target_information()
    directory = os.path.realpath(directory)

    if verb:
        print_notice("%s in %s on %s" % (verb, colour_text(directory, COLOUR_GREEN), colour_text("%s:%d" % (bind_address, bind_port), COLOUR_GREEN)))

    if args[TITLE_VERBOSE]:
        print_notice("Extra information shall also be printed.")

    if TITLE_TIMEOUT in args:
        print_notice("Read socket timeout: %s" % colour_text(args[TITLE_TIMEOUT]))

    for label, title in [("certificate", TITLE_SSL_CERT), ("key", TITLE_SSL_KEY)]:
        path = args[title]
        if path:
            print_notice("SSL %s file: %s" % (label, colour_text(os.path.realpath(path), COLOUR_GREEN)))

    if args[TITLE_USER]:
        print_notice("Basic authentication enabled (User: %s)" % colour_text(args.get(TITLE_USER, "<EMPTY>")))

        timeout_wording = "infinite"
        if args[TITLE_AUTH_TIMEOUT]:
            timeout_wording = '%ss' % args[TITLE_AUTH_TIMEOUT]
        print_notice('Authentication timeout: %s' % colour_text(timeout_wording))

    access.announce_filter_actions()

    for ua in args[TITLE_USER_AGENT]:
        print_notice("Whitelisted user agent pattern: %s" % colour_text(ua))

ENCODING = 'utf-8'

def convert_bytes(string_data):

    if isinstance(string_data, bytes):
        return string_data # Already bytes
    if isinstance(string_data, list):
        return [convert_bytes(i) for i in data]

    if sys.version_info[0] >= 3:
        return bytes(string_data, ENCODING)
    return bytes(string_data)

def convert_str(data):

    if isinstance(data, str):
        return data # Already a string
    if isinstance(data, list):
        return [convert_str(i) for i in data]

    if sys.version_info[0] >= 3:
        return str(data, ENCODING)
    return str(data)

DEFAULT_TARGET = os.getcwd() # Most implementations consider the target to be the current directory. Override if this is not the case.
def get_target():
    return args.last_operand(DEFAULT_TARGET)

def get_target_information():
    return (args[TITLE_BIND], args[TITLE_PORT], get_target())

def serve(handler, change_directory = False, data = None):
    bind_address, bind_port, directory = get_target_information()
    server = None
    try:

        server = ThreadedHTTPServer((bind_address, bind_port), handler)
        server.data = data

        if args[TITLE_SSL_CERT]:
            keyfile = os.path.realpath(args[TITLE_SSL_KEY])
            certfile = os.path.realpath(args[TITLE_SSL_CERT])
            server.socket = ssl.wrap_socket(server.socket, server_side=True, keyfile=args[TITLE_SSL_KEY], certfile=args[TITLE_SSL_CERT])

        if change_directory:
            os.chdir(directory)

        print_notice("Starting server, use <Ctrl-C> to stop")
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl-C
        if server:
            server.kill_requests()
        print("")
    except ssl.SSLError as e:
        m = "Unexpected %s: " % colour_text(type(e).__name__, COLOUR_RED)
        if re.match("^\[SSL\] PEM lib", str(e)):
            # '[SSL] PEM lib (_ssl.c:2798)' is super-unhelpful, so we will provide our own error message.
            # Unconfirmed: Is a missing key the only that can cause this?
            m+= "Must specify a key file or a cert file that also contains a key."
        else:
            # Append regular error message
            m += str(e)
        print_error(m)
    except Exception as e:
        print_exception(e)
        exit(1)

# Default error message template
DEFAULT_ERROR_MESSAGE = """<html>
    <head>
        <title>Error Response: %(code)d</title>
    </head>
    <body>
        <h1>Error Response</h1>
        <p>Error code %(code)d.</p>
        <p>Message: %(message)s.</p>
        <p>Error code explanation: %(code)s = %(explain)s.
    </body>
</html>
"""

ATTR_REQUEST_LINE = 'requestline'
ATTR_REQUEST_VERSION = 'request_version'
ATTR_RAW_RLINE = 'raw_requestline'
ATTR_PATH = 'path'
ATTR_FILE_PATH = 'file_path'
ATTR_HEADERS = 'headers'
ATTR_COMMAND = 'command'

class CoreHttpServer(BaseHTTPRequestHandler, object):

    server_version = "CoreHttpServer"
    alive = True

    # (Kludgy) responses to specific problems without overriding an entire method.
    log_on_send_error = False

    error_message_format = DEFAULT_ERROR_MESSAGE

    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.setup()
        self.request_sane = False

    def check_authentication(self):

        # Check for authorization (by default with the Authorization header),
        #  then pass to check_credentials to confirm them against a password back-end.

        if not authentication_stores:
            return True

        user = getattr(self, '_user', None)
        password = getattr(self, '_password', None)

        client = self.client_address[0]
        # Convenient shorthand
        auth_timeout = args[TITLE_AUTH_TIMEOUT]
        auth_limit = args[TITLE_AUTH_LIMIT]

        have_record = client in self.server.attempts
        if auth_limit and auth_timeout and have_record:
            # Clean expired attempts from storage.
            t = time.time()
            trimmed_attempts = [x for x in self.server.attempts[client] if x + auth_timeout >= t]
            if trimmed_attempts:
                self.server.attempts[client] = trimmed_attempts
            else:
                del self.server.attempts[client]
                have_record = False

        if auth_limit and len(self.server.attempts.get(client, [])) >= auth_limit:
            # Client has already exceeded maximum attempts.
            # Do not even make an attempt against authentication stores.
            return False

        success = False
        for store in authentication_stores:
            result = store.authenticate(user, password)
            success = result == AUTH_GOOD_CREDS
            if result >= AUTH_BAD_PASSWORD:
                break

        if auth_limit and not success:
            # Note failed attempt
            if have_record:
                # Append to existing record if we have a current record and a non-infinite timeout that is not filled.
                # A bit overkill since the attempt blocking above should prevent the attempt records for the client from
                #   growing further...
                if auth_timeout or len(self.server.attempts[client]) < auth_limit:
                    self.server.attempts[client].append(time.time())
            else:
                # No known record or first offense of an infinite timeout
                self.server.attempts[client] = [time.time()]
        return success

    def copyobj(self, src, dst, outgoing = True):
        if not src:
            return

        while self.alive:
            buf = src.read(16*1024)
            if not (buf and self.alive):
                break
            dst.write(convert_bytes(buf))

        if not outgoing:
            return

        self.alive = False
        src.close()

    def invoke(self, method):
        """Serve a request."""

        f = None
        try:
            f = method()
            self.copyobj(f, self.wfile)
        except Exception as e:
            print_exception(e, colour_text(self.client_address[0], COLOUR_GREEN))
            if not f:
                self.send_error(500)

    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

    def get_command(self):
        return getattr(self, ATTR_COMMAND, "GET")

    def get_header_dict(self, src):
        d = CaselessDict()

        for l in [l for l in re.split("\r?\n", str(src)) if l]:
            items = l.split(":")
            if items[1:]:
                d[items[0]] = ":".join(items[1:]).strip()

        return d

    def guess_type(self, path):
        """Guess the type of a file.
        Argument is a PATH (a filename).
        Return value is a string of the form type/subtype,
        usable for a MIME Content-type header.
        The default implementation looks the file's extension
        up in the table self.extensions_map, using application/octet-stream
        as a default; however it would be permissible (if
        slow) to look inside the data to make a better guess.
        """

        base, ext = posixpath.splitext(path)
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        return self.extensions_map.get(ext.lower(), '')

    def handle_one_request(self):
        """Handle a single HTTP request.
        You normally don't need to override this method; see the class
        __doc__ string for information on how to handle specific HTTP
        commands such as GET and POST.

        That being said, I overrode this function in order to have a
        nice upstream spot to put the whitelist/blacklist feature.
        """

        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                return self.send_error(414)
            if not self.raw_requestline:
                self.close_connection = 1
                return

            if not self.parse_request():
                # An error code has been sent, just exit
                return

            # Implementation-specific header parsing
            # Check for high-priority information that is necessary before we
            #   potentially slam the door in the client's face.
            for m in [getattr(self, m) for m in dir(self) if m.startswith('parse_preauth_header_')]:
                if not m():
                    return

            if not self.check_authentication():
                return self.send_error(401, args[TITLE_AUTH_PROMPT])

            # Implementation-specific header parsing
            for m in [getattr(self, m) for m in dir(self) if m.startswith('parse_header_')]:
                if not m():
                    return

            command = self.get_command()

            mname = 'do_' + command
            if not hasattr(self, mname):
                # Leave this as 'self.command' to not expose any possible custom handling from get_command().
                self.send_error(501, "Unsupported method (%r)" % self.command)
                return
            self.invoke(getattr(self, mname))

            self.wfile.flush()
        except socket.timeout:
            # a read or a write timed out.  Discard this connection
            self.close_connection = 1
            return self.send_error(408, "Data timeout (%s seconds)" % args[TITLE_TIMEOUT])

    def log_date_time_string(self):
        """Return the current time formatted for logging."""
        now = time.time()
        year, month, day, hh, mm, ss, x, y, z = time.localtime(now)
        return "%04d-%02d-%02d %02d:%02d:%02d" % (
                year, month, day, hh, mm, ss)

    def log_message(self, fmt, *values):
        """Log an arbitrary message.
        This is used by all other logging functions.  Override
        it if you have specific logging wishes.
        The first argument, fmt, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).
        The client host and current date/time are prefixed to
        every message.

        Modified to have a bit more colour, as Apache-style logging was not deemed a requirement for this script.
        """

        if type(values[0]) == int:
            # Errors may be presented as tuples starting with error code as int.
            # Do not bother printing extra information on error codes in a new line.
            return
        else:
            words = values[0].split()
            if values[1] == '404' and len(words) > 1 and words[1].lower().endswith("favicon.ico"):
                # Do not bother printing not-found information on favicon.ico.
                return

        http_code_colour = COLOUR_RED
        extra_info = ''
        try:
            response_code = int(values[1])
        except ValueError:
            response_code = "???"

        # Adjust colouring and/or add context in extra_info message.
        if response_code >= 200 and response_code < 300:
            http_code_colour = COLOUR_GREEN
        elif response_code in (301, 307):
            http_code_colour = COLOUR_PURPLE
            extra_info = '[%s]' % colour_text("Redirect", COLOUR_PURPLE)
        elif response_code == 404:
            extra_info = '[%s]' % colour_text("File Not Found", COLOUR_RED)
        elif response_code == 502:
            extra_info = '[%s]' % colour_text("Bad Gateway", COLOUR_RED)

        user = getattr(self, '_user', None)
        if user:
            extra_info = "[User: %s]%s" % (colour_text(user), extra_info)

        # Does address string match the client address? If not, print both.
        s = self.address_string()
        footer = ""

        # A 400 (bad request) error is more likely to contain corrupted information.
        # A likely cause of a bad request is a non-HTTP protocol being used (e.g. HTTPS, SSH).
        # We do not want to print this information, so we will be overwriting our values tuple.
        if response_code == 400 and not self.request_sane:
            values = (colour_text("BAD REQUEST", COLOUR_RED), response_code, values[2])
        else:
            # Non-400 response.
            # ToDo: account for possible index error here...
            request_items = values[0].split(" ")
            original_values = values
            values = (" ".join([request_items[0], colour_text(request_items[1], COLOUR_GREEN), request_items[2]]), values[1], values[2])

            if args[TITLE_VERBOSE]:
                user_agent = self.headers.get("User-Agent")
                if user_agent:
                    footer=" (User Agent: %s)" % colour_text(user_agent.strip())

        trailer = "[%s][%s]%s: %s%s\n" % (colour_text(self.log_date_time_string(), COLOUR_BOLD), colour_text(values[1], http_code_colour), extra_info, values[0], footer)
        src = "%s " % colour_text(self.client_address[0], COLOUR_GREEN)

        if s != self.client_address[0]:
            src += "(%s)" % colour_text(s, COLOUR_GREEN)

        # When a a proxy such as Squid or Apache forwards information,
        # (ProxyPass/ProxyPassReverse directives for Apache),
        # the original client's IP is stored in the 'X-Forwarded-For' header.
        # Trust this value as the true client address if it regexes to an IPv4 address.
        proxy_src = None
        proxy_steps = []
        forward_spec = getattr(self, ATTR_HEADERS, CaselessDict()).get("X-Forwarded-For")

        if forward_spec:
            forward_components = [c.strip() for c in forward_spec.split(",")]
            forward_addr = forward_components.pop(0)
            if forward_addr and re.match(REGEX_INET4, forward_addr):
                proxy_src = forward_addr
                proxy_steps = forward_components
        else:
            # As a fallback, try the 'Forwarded' header put forward by RFC 7239.

            try:
                forward_spec = getattr(self, ATTR_HEADERS, CaselessDict()).get("Forwarded")
                forward_addr = forward_spec.split(";")[2].split("=")[1]
                if forward_addr and re.match(REGEX_INET4, forward_addr):
                    proxy_src = forward_addr
            except:
                # Lazy approach. Skip validation of lists by encasing everything in a try-catch.
                pass

        if proxy_src:
            old_src = src.strip()
            src = "%s [proxy via " % colour_text(proxy_src, COLOUR_GREEN)

            if proxy_steps:
                first = True
                for step in proxy_steps:
                    if not first:
                        first += "->"
                    first = False
                    if re.match(REGEX_INET4, step):
                        src += colour_text(step, COLOUR_GREEN)
                    else:
                        # Wonky input. Maliciously formed?
                        # For now, just say "???" and deal with any troubles as they come up.
                        src += colour_text("???")
                src += "->%s" % old_src
            else:
                # One proxy step, quick and simple.
                src += old_src
            src += "]"

        sys.stdout.write("%s%s" % (src, trailer))
        sys.stdout.flush()

    def quote_html(self, html):
        return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def parse_path(self, raw_path):
        """Translate a /-separated PATH to the local filename syntax.
        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)
        """
        # abandon query parameters

        items = raw_path.split('?',1)

        get = {}
        if len(items) > 1:
            get = parse_qs(items[1])

        items = items[0].split('#',1)

        section = ''
        if len(items) > 1:
            section = items[1]

        path = posixpath.normpath(unquote(items[0]))

        words = [_f for _f in path.split('/') if _f]
        self.base_directory = file_path = os.getcwd()
        path = '/'

        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue

            file_path = os.path.join(file_path, word)
            path = os.path.join(path, word)

        if items[0].endswith('/'):
            file_path = '%s/' % file_path
            if not path.endswith('/'):
                path = '%s/' % path

        self.path = path
        self.section = section
        self.file_path = file_path
        self.get = get

    def parse_preauth_header_agent(self):
        if not args[TITLE_USER_AGENT]:
            return True
        # At least one match is present
        user_agent = self.headers.get('User-Agent')
        if not user_agent:
            return send_error(403)

        for p in args[TITLE_USER_AGENT]:
            user_agent_match = re.search(p, user_agent)
            if user_agent_match:
                return True
        # Was not able to find a match
        return send_error(403)

    def parse_preauth_header_connection(self):
        # Examine the headers and look for a Connection directive
        conntype = self.headers.get('Connection', '')
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif (conntype.lower() == 'keep-alive' and self.protocol_version >= "HTTP/1.1"):
            self.close_connection = 0
        return True

    def parse_preauth_header_user_authorization(self):

        value = getattr(self, ATTR_HEADERS, CaselessDict())["Authorization"]
        if not value:
            return True

        # Store bad-header response in a central place
        response_bad = lambda : self.send_error(400, 'Bad Authorization Header')

        raw_creds = value.split()
        if not raw_creds or len(raw_creds) < 2:
            # Incorrect credential format.
            return response_bad()

        # Decode
        try:
            creds_list = convert_str(convert_bytes(base64.b64decode(raw_creds[1])).split(convert_bytes(":")))
        except TypeError as e:
            return response_bad()

        if len(creds_list) < 2:
            # Creds message invalid, too few fields within.
            return response_bad()

        self._user = creds_list[0]
        self._password = ":".join(creds_list[1:])
        return True

    def parse_request(self):
        """Parse a request (internal).
        The request should be stored in self.raw_rline; the results
        are in self.command, self.path, self.request_version and
        self.headers.
        Return True for success, False for failure; on failure, an
        error is sent back.
        """

        self.requestline = convert_str((getattr(self, ATTR_RAW_RLINE, None) or "").rstrip(convert_bytes('\r\n')))
        words = self.requestline.split()

        if len(words) == 3:
            command, path, version = words
            if version[:5] != 'HTTP/':
                return self.send_error(400, "Bad request version (%r)" % version)

            self.request_sane = True

            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                m = "Bad request version"
                if len(version) < 20:
                    m += " (%r)" % version
                return self.send_error(400, m)
            if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
                self.close_connection = 0
            if version_number >= (2, 0):
                return self.send_error(505,
                          "Invalid HTTP Version (%s)" % base_version_number)
        elif len(words) == 2:
            command, path = words
            version = "HTTP/0.9" # Assume 0.9
            self.close_connection = 1
            if command != 'GET':
                return self.send_error(400, "Bad HTTP/0.9 request type (%s)" % command)
        else:
            m = "Bad request syntax"
            if len(getattr(self, ATTR_REQUEST_LINE, "")) < 30:
                m += " (%s)" % getattr(self, ATTR_REQUEST_LINE, "")
            return self.send_error(400, m)

        self.command, self.request_version = command, version

        try:
            self.parse_path(path)
        except FileNotFoundError:
            return self.send_error(404)

        # Parsing into a case-insensitive dictionary for simplicity.
        if sys.version_info[0] == 2:
            self.headers = self.get_header_dict(self.MessageClass(self.rfile, 0))
        else:
            mc = http.client.parse_headers(self.rfile, _class=self.MessageClass).__str__()
            self.headers = self.get_header_dict(mc)

        return True

    def render_breadcrumbs(self, path):

        base_parts = []
        path_parts = []
        current = '/'

        items = [p for p in (path or '').split('/') if p]
        i = 0
        for item in items:
            i += 1
            current += item + '/'
            if i == len(items):
                # Current directory
                path_parts.append((item, None))
            else:
                # Parent directory of current
                path_parts.append((item, current))

        items = [p for p in (self.base_directory or '').split('/') if p]
        i = 0
        for item in items:
            i += 1
            if i == len(items) and path_parts:
                # Link to root directory
                base_parts.append((item, '/'))
            else:
                # Unsharable item, parent of root directory
                base_parts.append((item, None))

        content = ""
        for text, link in base_parts + path_parts:
            if link:
                content += "/<a href='%s'>%s</a>" % (link, text)
            else:
                content += "/%s" % text
        return content

    def run(self):
        """
        Separation of tasks in standard __init__
        """
        try:
            self.handle()
        finally:
            self.finish()

    def send_common_headers(self, mimetype, length):
        encoding = sys.getfilesystemencoding()
        self.send_header("Content-Type", "%s; charset=%s" % (mimetype, encoding))
        self.send_header("Content-Length", str(length))

    def send_error(self, code, message=None):
        """Send and log an error reply.
        Arguments are the error code, and a detailed message.
        The detailed message defaults to the short entry matching the
        response code.
        This sends an error response (so it must be called before any
        output has been generated), logs the error, and finally sends
        a piece of HTML explaining the error to the user.
        """
        try:
            short_msg, long_msg = self.responses[code]
        except KeyError:
            short_msg, long_msg = '???', '???'
        if message is None:
            message = short_msg

        self.log_error("code %d, message %s", code, message)

        f = None
        length = 0

        try:
            # using _quote_html to prevent Cross Site Scripting attacks (see bug #1100201)
            if(code >= 200 and
                code not in (
                    204, # No Content
                    205, # Reset Content
                    304  # Not Modified
                )):

                self.send_response(code, message)
                self.send_header('Connection', 'close')
                if code == 401:
                    self.send_header('WWW-Authenticate', 'Basic realm="%s"' % message)

                self.send_header("Content-Type", self.error_content_type)

                content = self.error_message_format % {'code': code, 'message': self.quote_html(message), 'explain': long_msg}
                f, length = self.serve_content_prepare(content)
                self.send_header('Content-Length', str(length))

            self.end_headers()
            self.copyobj(f, self.wfile, False)

        except IOError:
            # Don't shed too many tears for an error that fails
            #   to send. The connection is about to be closed anyways.
            pass

        if self.log_on_send_error:
            self.log_message('"%s" %s %s', getattr(self, 'requestline', '???'), code, message)

        return False

    def send_redirect(self, target):
        # redirect browser - doing basically what apache does
        self.send_response(307)
        self.send_header("Location", target)
        self.end_headers()
        return None

    def serve_content(self, content = None, code = 200, mimetype = "text/html"):

        f, length = self.serve_content_prepare(content)
        self.send_response(code)
        self.send_common_headers(mimetype, length)
        self.end_headers()
        return f

    def serve_content_prepare(self, content):

        if not content:
            return None, 0

        f = StringIO()
        f.write(content)
        length = f.tell()
        f.seek(0)

        return f, length

    def serve_file(self, path):

        if not (os.path.exists(path) and os.path.isfile(path)):
            return self.send_error(404, 'Not Found')

        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            return self.send_error(404, 'Not Found')
        self.send_response(200)
        self.send_header("Content-type", ctype)
        fs = os.fstat(f.fileno())
        self.send_header("Content-Length", str(fs[6]))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def translate_path(self, path, include_cwd = True):
        """Translate a /-separated PATH to the local filename syntax.
        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        SimpleHttpServer implementation.
        """
        # abandon query parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        # Reminder: The use of posixpath.normpath accounts for
        # potential malicious crafted request paths.
        path = posixpath.normpath(unquote(path))

        if not include_cwd:
            # Return path as-is
            return path

        # Prepare to tack on current working directory.
        words = path.split('/')
        words = [_f for _f in words if _f]
        path = os.getcwd()
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

class CaselessDict(dict):
    # Case-insensitive dictionary.
    # Inspired by: https://stackoverflow.com/questions/2082152/case-insensitive-dictionary
    # Made some extra adjustments to the original concept because I wanted to
    #   have my cake and eat it too by not modifying any stored keys.
    # This particular version also makes the assumption all stored values will be strings.
    def __init__(s, src = None):
        if src:
            for k in list(src.keys()):
                s[k] = src[k]
        super(CaselessDict, s).__init__()

    def __contains__(s, key):
        return key.lower() in [k.lower() for k in list(s.keys())]

    # Credit for __getitem__/__setitem__:
    def __setitem__(s, key, val):
        if s.__contains__(key):
            for old in [k for k in list(s.keys()) if k.lower() == key.lower()]:
                del s[old]
        super(CaselessDict, s).__setitem__(key, val.strip())

    def get(s, key, default = ""):
        # Get the first (and hopefully only) key match.
        keys = [k for k in list(s.keys()) if k.lower() == key.lower()]
        if not keys:
            return default
        return super(CaselessDict, s).get(keys[0])

    __getitem__ = get

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
        # Return a mask of n bits as a long integer
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

class SimpleAuthStore:
    def __init__(self, user, password):
        self.__user = user
        self.__password = password

    def authenticate(self, user, password):
        if user == self.__user:
            if password == self.__password:
                return AUTH_GOOD_CREDS
            return AUTH_BAD_PASSWORD
        return AUTH_BAD_NOT_FOUND

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

    attempts = {}
    requests = {}
    alive = True

    def finish_request(self, request, client_address):
        """Finish one request by instantiating RequestHandlerClass."""

        if not self.alive:
            return

        req = self.RequestHandlerClass(request, client_address, self)
        if sys.version_info[0] == 2:
            req.rfile._sock.settimeout(args[TITLE_TIMEOUT])

        self.requests[client_address] = req
        req.run()
        del self.requests[client_address]

    def kill_requests(self):
        self.alive = False
        for client_address in list(self.requests.keys()):
            self.requests[client_address].alive = False

access = NetAccess()
authentication_stores = []
