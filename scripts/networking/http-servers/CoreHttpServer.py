#!/usr/bin/env python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

# Basic includes
import base64, getopt, getpass, os, mimetypes, posixpath, re, shutil, ssl, socket, struct, sys, time, urllib, BaseHTTPServer
from random import randint
from SocketServer import ThreadingMixIn

from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ThreadingMixIn
import getopt, os, re, socket, struct, sys

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message):
    print "%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message)

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
    stack.reverse()
    fname, lineno = next((t for t in stack if t[0] in local_files), (stack[-1]))

    print stack

    fname = os.path.split(fname)[1]
    print_error("Unexpected %s(%s%s, Line %s): %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, colour_text(fname, COLOUR_GREEN), lineno, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

# Variables

DEFAULT_AUTH_PROMPT = "Authorization Required"
DEFAULT_TIMEOUT = 10

DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = 8080

REGEX_INET4='^(([0-9]){1,3}\.){3}([0-9]{1,3})$'

TITLE_BIND = "bind"
TITLE_PORT = "port"
TITLE_POST = "post"
TITLE_TIMEOUT = "timeout"
TITLE_VERBOSE="verbose"

TITLE_AUTH_PROMPT = "prompt"
TITLE_PASSWORD = "password"
TITLE_USER = "user"

TITLE_SSL_CERT = "SSL certfile"
TITLE_SSL_KEY = "SSL keyfile"

TITLE_ALLOW = "allow address/range"
TITLE_ALLOW_FILE = "allow address/range file"
TITLE_DENY = "deny address/range"
TITLE_DENY_FILE = "deny address/range file"

TITLE_USER_AGENT = "user-agent pattern"

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

        if opt and opt.multiple:
            default = []

        # Silly note: Doing a get() out of a dictionary when the stored
        #   value of the key is None will not fall back to default
        value = self.args.get(arg, self.defaults.get(arg))
        if value is None:
            return default
        return value

    def __setitem__(self, key, value):
        self.args[key] = value

    def add_opt(self, opt_type, flag, label, description = None, required = False, default = None, converter=str, multiple = False, strict_single = False):

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
            raise Exception("Duplicate label (new: %s%s): %s" % (arg, label))
        if multiple and strict_single:
            raise Exception("Cannot have an argument with both 'multiple' and 'strict_single' set to True.")
        # These do not cover harmless checks on arg modifiers with flag values.

        obj = OptArg()
        obj.opt_type = opt_type
        obj.label = label
        obj.required = required and opt_type & MASK_OPT_TYPE_ARG
        obj.default = default
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
            print l

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

    opt_type = 0

    def is_flag(self):
        return self.opt_type in (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG)

    def get_printout_help(self, opt):

        desc = self.description or "No description defined"

        if self.is_flag():
            return "  %s: %s" % (opt, desc)
        else:
            return "  %s <%s>: %s" % (opt, self.label, desc)

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
args.add_opt(OPT_TYPE_FLAG, "P", TITLE_POST, "Accept POST data. The server will not process it, but it won't raise any error either.")
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
for default, title in [(DEFAULT_AUTH_PROMPT, TITLE_AUTH_PROMPT), ("", TITLE_USER), ("", TITLE_PASSWORD)]:
    args.add_opt(OPT_TYPE_LONG, title, title, "Specify authentication %s." % title, default = default)

def validate_common_arguments(self):
    errors = []

    port = self[TITLE_PORT]
    if port < 0 or port > 65535:
        errors.append("Port must be 0-65535. Given: %s" % colour_text(port))

    if self[TITLE_TIMEOUT] <= 0:
        errors.append("Timeout must be a positive value. Given: %s" % colour_text(COLOUR_BOLD, self.args[TITLE_PORT]))

    for label in [TITLE_SSL_CERT, TITLE_SSL_KEY]:
        path = self[label]
        if path and not os.path.isfile(path):
            errors.append("%s not found: %s" % (label, colour_text(path, COLOUR_GREEN)))

    if TITLE_SSL_KEY in self.args and not TITLE_SSL_CERT in self.args:
        errors.append("%s path provided, but no %s path was provided." % (TITLE_SSL_KEY, TITLE_SSL_CERT))

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

    if args[TITLE_POST]:
        print_notice("Accepting %s messages. Will not process, but will not throw a %s code either." % (colour_text("POST"), colour_text("501", COLOUR_RED)))

    if TITLE_TIMEOUT in args:
        print_notice("Read socket timeout: %s" % colour_text(args[TITLE_TIMEOUT]))

    for label, title in [("certificate", TITLE_SSL_CERT), ("key", TITLE_SSL_KEY)]:
        path = args[title]
        if path:
            print_notice("SSL %s file: %s" % (label, colour_text(path, COLOUR_GREEN)))

    if args[TITLE_USER]:
        print_notice("Basic authentication enabled (User: %s)" % colour_text(args.get(TITLE_USER, "<EMPTY>")))

    access.announce_filter_actions()

    for ua in args[TITLE_USER_AGENT]:
        print_notice("Whitelisted user agent pattern: %s" % colour_text(ua))

DEFAULT_TARGET = os.getcwd() # Most implementations consider the target to be the current directory. Override if this is not the case.
def get_target():
    return args.last_operand(DEFAULT_TARGET)

def get_target_information():
    return (args[TITLE_BIND], args[TITLE_PORT], get_target())

def serve(handler, change_directory = False):
    bind_address, bind_port, directory = get_target_information()
    try:
        if change_directory:
            os.chdir(directory)
        server = ThreadedHTTPServer((bind_address, bind_port), handler)

        if args[TITLE_SSL_CERT]:
            server.socket = ssl.wrap_socket(server.socket, server_side=True, keyfile=args[TITLE_SSL_KEY], certfile=args[TITLE_SSL_CERT])

        print_notice("Starting server, use <Ctrl-C> to stop")
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl-C
        server.kill_requests()
        print ""
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
DEFAULT_ERROR_MESSAGE = """
<html>
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

class CoreHttpServer(BaseHTTPServer.BaseHTTPRequestHandler):

    server_version = "CoreHttpServer"
    alive = True

    # (Kludgy) responses to specific problems without overriding an entire method.
    log_on_send_error = False

    path = None
    headers = None

    error_message_format = DEFAULT_ERROR_MESSAGE

    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.setup()

    def check_authorization(self):
        # Check for authorization (by default with the Authorization header),
        #  then pass to check_credentials to confirm them against a password back-end.

        if not self.check_authorization_required():
            return True

        verbose = args[TITLE_VERBOSE]

        raw_creds = self.headers.getheader("Authorization", "").split()
        if not raw_creds or len(raw_creds) < 2:
            return False

        # Decode
        creds_list = []
        try:
            creds_list = base64.b64decode(raw_creds[1]).split(":")
        except TypeError:
            pass

        if len(creds_list) < 2:
            # Creds message invalid, too few fields within.
            return False

        # User and password from the user.
        user = creds_list[0]
        password = ":".join(creds_list[1:])
        return self.check_credentials(user, password)

    def check_authorization_required(self):
        return TITLE_USER in args or TITLE_PASSWORD in args

    def check_credentials(self, user, password):
        wanted_user = args[TITLE_USER]
        wanted_password = args[TITLE_PASSWORD]
        return wanted_user == user and wanted_password == password

    def copyobj(self, src, dst):
        while self.alive:
            buf = src.read(16*1024)
            if not (buf and self.alive):
                break
            dst.write(buf)
        self.alive = False
        src.close()

    def do_GET(self):
        """Serve a GET request."""
        f = self.send_head()
        if f:
            self.copyobj(f, self.wfile)

    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

    def get_command(self):
        command = self.command
        if self.command == "POST" and args[TITLE_POST]:
            command = "GET"
        return command

    def get_header_dict(self, header_str):
        d = {}
        for l in str(header_str).split("\r\n"):
            if not l:
                continue
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
        ext = ext.lower()
        if ext in self.extensions_map:
            return self.extensions_map[ext]
        else:
            return self.extensions_map['']

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
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = 1
                return

            if not self.parse_request():
                # An error code has been sent, just exit
                return

            if not self.check_authorization():
                return self.send_error(401, args[TITLE_AUTH_PROMPT])

            command = self.get_command()

            mname = 'do_' + command
            if not hasattr(self, mname):
                # Leave this as 'self.command' to not expose any possible custom handling from get_command().
                self.send_error(501, "Unsupported method (%r)" % self.command)
                return
            method = getattr(self, mname)
            method()
            self.wfile.flush() #actually send the response if not already done.
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
            if values[1] == '404' and len(words) > 1 and words[1].endswith("favicon.ico"):
                # Do not bother printing not-found information on favicon.ico.
                return

        http_code_colour = COLOUR_RED
        extra_info = ''
        try:
            response_code = int(values[1])
        except ValueError:
            response_code = "???"

        # Adjust colouring and/or add context in extra_info message.
        if response_code == 200:
            http_code_colour = COLOUR_GREEN
        elif response_code in (301, 307):
            http_code_colour = COLOUR_PURPLE
            extra_info = '[%s]' % colour_text("Redirect", COLOUR_PURPLE)
        elif response_code == 404:
            extra_info = '[%s]' % colour_text("File Not Found", COLOUR_RED)
        elif response_code == 502:
            extra_info = '[%s]' % colour_text("Bad Gateway", COLOUR_RED)

        # Does address string match the client address? If not, print both.
        s = self.address_string()
        footer = ""

        # A 400 (bad request) error is more likely to contain corrupted information.
        # A likely cause of a bad request is a non-HTTP protocol being used (e.g. HTTPS, SSH).
        # We do not want to print this information, so we will be overwriting our values tuple.
        if response_code == 400:
            values = (colour_text("BAD REQUEST", COLOUR_RED), response_code, values[2])
        else:
            # Non-400 response.
            request_items = values[0].split(" ")
            values = (" ".join([request_items[0], colour_text(request_items[1], COLOUR_GREEN), request_items[2]]), values[1], values[2])

            if args[TITLE_VERBOSE]:
                user_agent = self.headers.getheader("User-Agent")
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
        forward_spec = None
        if self.headers:
            forward_spec = self.headers.getheader("X-Forwarded-For", "").strip()

        if forward_spec:
            forward_components = [c.strip() for c in forward_spec.split(",")]
            forward_addr = forward_components.pop(0)
            if forward_addr and re.match(REGEX_INET4, forward_addr):
                proxy_src = forward_addr
                proxy_steps = forward_components
        else:
            # As a fallback, try the 'Forwarded' header put forward by RFC 7239.

            try:
                forward_spec = self.headers.getheader("Forwarded", "").strip()
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

    def parse_request(self):
        """Parse a request (internal).
        The request should be stored in self.raw_requestline; the results
        are in self.command, self.path, self.request_version and
        self.headers.
        Return True for success, False for failure; on failure, an
        error is sent back.
        """
        self.command = None  # set in case of error on the first line
        self.request_version = version = self.default_request_version
        self.close_connection = 1
        requestline = self.raw_requestline
        requestline = requestline.rstrip('\r\n')
        self.requestline = requestline
        self.headers_dict = {}
        words = requestline.split()

        if len(words) == 3:
            command, path, version = words
            if version[:5] != 'HTTP/':
                self.send_error(400, "Bad request version (%r)" % version)
                return False
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
                self.send_error(400, m)
                return False
            if version_number >= (1, 1) and self.protocol_version >= "HTTP/1.1":
                self.close_connection = 0
            if version_number >= (2, 0):
                self.send_error(505,
                          "Invalid HTTP Version (%s)" % base_version_number)
                return False
        elif len(words) == 2:
            command, path = words
            self.close_connection = 1
            if command != 'GET':
                self.send_error(400,
                                "Bad HTTP/0.9 request type (%s)" % command)
                return False
        elif not words:
            # TODO: Confirm why this check is as it is...
            return False
        else:
            m = "Bad request syntax"
            if len(requestline) < 30:
                m += " (%s)" % requestline
            self.send_error(400, m)
            return False
        self.command, self.path, self.request_version = command, path, version

        # Examine the headers and look for a Connection directive
        self.headers = self.MessageClass(self.rfile, 0)
        # I was not able to successfully use the MIMEMessage object, so parsing it into a dictionary instead.
        self.headers_dict = self.get_header_dict(self.headers)

        # Access control checks
        user_agent_match = not args[TITLE_USER_AGENT]
        if not user_agent_match:
            # At least one match is present
            user_agent = self.headers.getheader("User-Agent")
            if user_agent:
                for p in args[TITLE_USER_AGENT]:
                    user_agent_match = re.search(p, user_agent)
                    if user_agent_match:
                        break # Avoid redundant checks

        if not user_agent_match or not access.is_allowed(self.client_address[0]):
            self.send_error(403,"Access Denied")
            return False

        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif (conntype.lower() == 'keep-alive' and
              self.protocol_version >= "HTTP/1.1"):
            self.close_connection = 0
        return True

    def render_breadcrumbs(self, path):
        current = "/"
        items = [(current, "Root")]

        for item in path.split("/"):
            if not item:
                continue
            current += item + "/"
            items.append((current, item))
        content = ""
        i = 0
        for item in items:
            i += 1
            if i == len(items):
                content += " / <strong>%s</strong>" % item[1]
            else:
                content += " / <a href='%s'>%s</a>" % (item[0], item[1])
        return content

    def run(self):
        """
        Separation of tasks in standard __init__
        """
        try:
            self.handle()
        finally:
            self.finish()

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
            short, long = self.responses[code]
        except KeyError:
            short, long = '???', '???'
        if message is None:
            message = short
        explain = long
        self.log_error("code %d, message %s", code, message)
        # using _quote_html to prevent Cross Site Scripting attacks (see bug #1100201)
        content = (self.error_message_format % {'code': code, 'message': self.quote_html(message), 'explain': explain})
        self.send_response(code, self.path)
        self.send_header("Content-Type", self.error_content_type)
        self.send_header('Connection', 'close')
        if code == 401:
            self.send_header('WWW-Authenticate', 'Basic realm="%s"' % message)
        self.end_headers()
        if self.command != 'HEAD' and code >= 200 and code not in (204, 304):
            self.wfile.write(content)
        if self.log_on_send_error:
            self.log_message('"%s" %s %s', self.requestline, code, None)

    def send_redirect(self, target):
        # redirect browser - doing basically what apache does
        self.send_response(307)
        self.send_header("Location", target)
        self.end_headers()
        return None

    def serve_content(self, content, code = 200, mimetype = "text/html"):
        f = StringIO()
        f.write(content)
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        encoding = sys.getfilesystemencoding()
        self.send_header("Content-type", "text/html; charset=%s" % encoding)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f

    def serve_file(self, path):

        if not (os.path.exists(path) and os.path.isfile(path)):
            return self.send_error(404, "File not found.")

        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not found")
            return None
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
        path = posixpath.normpath(urllib.unquote(path))

        if not include_cwd:
            # Return path as-is
            return path

        # Prepare to tack on current working directory.
        words = path.split('/')
        words = filter(None, words)
        path = os.getcwd()
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

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
        return (2L<<n-1)-1

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

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

    requests = {}
    alive = True

    def finish_request(self, request, client_address):
        """Finish one request by instantiating RequestHandlerClass."""

        if not self.alive:
            return

        req = self.RequestHandlerClass(request, client_address, self)
        req.rfile._sock.settimeout(args[TITLE_TIMEOUT])
        self.requests[client_address] = req

        try:
            req.run()
        except Exception as e:
            print_exception(e, colour_text(client_address[0], COLOUR_GREEN))

        del self.requests[client_address]

    def kill_requests(self):
        self.alive = False
        for client_address in self.requests.keys():
            self.requests[client_address].alive = False

access = NetAccess()
