#!/usr/bin/env python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

# Basic includes
import base64, getopt, getpass, os, mimetypes, posixpath, re, shutil, ssl, socket, struct, sys, urllib, BaseHTTPServer
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

def __print_message(colour, header, message):
    print "%s[%s]: %s" % (colour_text(colour, header), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

def colour_text(colour, text):
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
    __print_message(COLOUR_RED, "Error", message)

def print_notice(message):
    __print_message(COLOUR_BLUE, "Notice", message)

# Variables

DEFAULT_AUTH_PROMPT = "Authorization Required"
DEFAULT_POST = False
DEFAULT_VERBOSE = False

DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_PORT_SSL = 8443

REGEX_INET4='^(([0-9]){1,3}\.){3}([0-9]{1,3})$'

TITLE_BIND = "bind"
TITLE_PORT = "port"
TITLE_POST = "post"
TITLE_DIR = "dir"
TITLE_VERBOSE="verbose"

TITLE_AUTH_PROMPT = "prompt"
TITLE_PASSWORD = "password"
TITLE_USER = "user"

TITLE_SSL_CERT = "SSL certfile"
TITLE_SSL_KEY = "SSL keyfile"

# Option Definitions

OPT_TYPE_FLAG = "flag"
OPT_TYPE_SHORT = "short"
OPT_TYPE_LONG = "long"
OPT_TYPE_LONG_FLAG = "long flag"

class Opt:
    def __init__(self, opt, description, label):
        self.opt = opt
        self.description = description
        self.label = label

    def get_description(self):
        if self.description:
            return self.description
        return "No description defined."

    def get_label(self):
        if self.label:
            return self.label
        return "???"

opts = { OPT_TYPE_FLAG: {}, OPT_TYPE_SHORT: {}, OPT_TYPE_LONG: {}, OPT_TYPE_LONG_FLAG: {}}

def add_opt(opt_type, flag, description=None, label=None):
    if opt_type not in opts:
        raise Exception("Bad type: %s" % opt_type)

    if flag in opts[opt_type]:
        raise Exception("Flag already exists: %s" % flag)

    opts[opt_type][flag] = Opt(flag, description, label)

def get_opts():
    s = ""
    for key in opts[OPT_TYPE_FLAG]:
        s += key
    for key in opts[OPT_TYPE_SHORT]:
        s += "%s:" % key
    return s

def get_opts_long():
    return ["%s=" % key for key in sorted(opts[OPT_TYPE_LONG].keys())] + sorted(opts[OPT_TYPE_LONG_FLAG].keys())

def handle_common_argument(opt, arg):
    global args
    global access

    good = True
    processed = True

    if opt in ("-a"):
        error = access.add_whitelist(arg) or error
    elif opt in ("-A"):
        error = access.load_whitelist_file(arg) or error
    elif opt in ("-b"):
        args[TITLE_BIND] = arg
    elif opt in ("-c"):
        args[TITLE_SSL_CERT] = arg
    elif opt in ("-d"):
        good = access.add_blacklist(arg) and good
    elif opt in ("-D"):
        good = access.load_blacklist_file(arg) and good
    elif opt in ("-k"):
        args[TITLE_SSL_KEY] = arg
    elif opt in ("-h"):
        hexit(0)
    elif opt in ("-p"):
        raw_int_args[TITLE_PORT] = arg
    elif opt in ("-P"):
        args[TITLE_POST] = True
    elif opt in ("-v"):
        args[TITLE_VERBOSE] = True
    elif opt in ("--password"):
        args[TITLE_PASSWORD] = arg
    elif opt in ("--prompt"):
        args[TITLE_AUTH_PROMPT] = arg
    elif opt in ("--user"):
        args[TITLE_USER] = arg
    else:
        processed = False

    return good, processed

def validate_common_arguments():

    errors = []

    for k in sorted(raw_int_args.keys()):
        try:
            args[k] = int(raw_int_args[k])
        except ValueError:
            errors.append("Invalid port number: %s" % colour_text(COLOUR_BOLD, raw_int_args[k]))

    if TITLE_PORT in args:
        if args[TITLE_PORT] < 0 or args[TITLE_PORT] > 65535:
            errors.append("Port must be 0-65535. Given: %s" % colour_text(COLOUR_BOLD, args[TITLE_PORT]))

    for label, title in [("certificate", TITLE_SSL_CERT), ("key", TITLE_SSL_KEY)]:
        path = args.get(title)
        if path and not os.path.isfile(path):
            errors.append("SSL %s file not found: %s" % (label, colour_text(COLOUR_GREEN, path)))

    # TODO: Some more detailed SSL validation?

    return errors


def hexit(exit_code = 0):
    s = "./%s" % os.path.basename(sys.argv[0])
    lines = []
    if opts[OPT_TYPE_FLAG]:
        lines.append("Flags:")
        s += " [-%s]" % "".join([opts[OPT_TYPE_FLAG][f].opt for f in opts[OPT_TYPE_FLAG]])
        lines.extend(["  -%s: %s" % (opts[OPT_TYPE_FLAG][f].opt, opts[OPT_TYPE_FLAG][f].get_description()) for f in sorted(opts[OPT_TYPE_FLAG].keys())])
    if opts[OPT_TYPE_SHORT]:
        lines.append("Options:")
        s += " %s" % " ".join(["[-%s %s]" % (opts[OPT_TYPE_SHORT][f].opt, opts[OPT_TYPE_SHORT][f].label) for f in sorted(opts[OPT_TYPE_SHORT].keys())])
        lines.extend(["  -%s <%s>: %s" % (opts[OPT_TYPE_SHORT][f].opt, opts[OPT_TYPE_SHORT][f].get_label(), opts[OPT_TYPE_SHORT][f].get_description()) for f in sorted(opts[OPT_TYPE_SHORT])])
    if opts[OPT_TYPE_LONG_FLAG]:
        lines.append("Long Flags:")
        s += " %s" % " ".join("[--%s]" % f for f in sorted(opts[OPT_TYPE_LONG_FLAG].keys()))
        lines.extend(["  --%s: %s" % (f, opts[OPT_TYPE_LONG_FLAG][f].get_description()) for f in sorted(opts[OPT_TYPE_LONG_FLAG].keys())])
    if opts[OPT_TYPE_LONG]:
        lines.append("Long Options:")
        s += " %s" % " ".join(["[--%s %s]" % (opts[OPT_TYPE_LONG][f].opt, opts[OPT_TYPE_LONG][f].label) for f in sorted(opts[OPT_TYPE_LONG].keys())])
        lines.extend(["  --%s <%s>: %s" % (opts[OPT_TYPE_LONG][f].opt, opts[OPT_TYPE_LONG][f].get_label(), opts[OPT_TYPE_LONG][f].get_description()) for f in sorted(opts[OPT_TYPE_LONG].keys())])
    __print_message(COLOUR_PURPLE, "Usage", s)
    for l in lines:
        print l
    exit(exit_code)

# Short opts
add_opt(OPT_TYPE_FLAG, "h", "Display help menu and exit.")
add_opt(OPT_TYPE_FLAG, "P", "Accept POST data. The server will not process it, but it won't raise any error either.")
add_opt(OPT_TYPE_FLAG, "v", "Verbose output.")
# Short flags
add_opt(OPT_TYPE_SHORT, "a", "Add network address or CIDR range to whitelist.", "allow-address/range")
add_opt(OPT_TYPE_SHORT, "A", "Add addresses or CIDR ranges in file to whitelist.", "allow-list-file")
add_opt(OPT_TYPE_SHORT, "b", "Address to bind to (default: %s)." % DEFAULT_BIND, "bind-address")
add_opt(OPT_TYPE_SHORT, "d", "Add network address or CIDR range to blacklist.", "deny-address/range")
add_opt(OPT_TYPE_SHORT, "D", "Add addresses or CIDR ranges in file to blacklist.", "deny-list-file")
add_opt(OPT_TYPE_SHORT, "p", "Specify server bind port (HTTP Default: %s, SSL Default: %s)." % (DEFAULT_PORT, DEFAULT_PORT_SSL), "port")

add_opt(OPT_TYPE_SHORT, "c", "SSL certificate file path (PEM format). Can also contain the SSL key.", "certfile")
add_opt(OPT_TYPE_SHORT, "k", "SSL key file path (PEM format).", "keyfile")

# Long flags
for t in [TITLE_AUTH_PROMPT, TITLE_USER, TITLE_PASSWORD]:
    add_opt(OPT_TYPE_LONG, t, "Specify authentication %s." % t, t)

# End option definitions

def announce_common_arguments(verb = "Hosting content"):

    bind_address, bind_port, directory = get_target_information()

    if verb:
        print_notice("%s in %s on %s" % (verb, colour_text(COLOUR_GREEN, directory), colour_text(COLOUR_GREEN, "%s:%d" % (bind_address, bind_port))))

    if args.get(TITLE_VERBOSE, DEFAULT_VERBOSE):
        print_notice("Extra information shall also be printed.")

    if args.get(TITLE_POST, DEFAULT_POST):
        print_notice("Accepting %s messages. Will not process, but will not throw a %s code either." % (colour_text(COLOUR_BOLD, "POST"), colour_text(COLOUR_RED, "501")))

    for label, title in [("certificate", TITLE_SSL_CERT), ("key", TITLE_SSL_KEY)]:
        path = args.get(title)
        if path:
            print_notice("SSL %s file: %s" % (label, colour_text(COLOUR_GREEN, path)))

    if args.get(TITLE_USER):
        print_notice("Basic authentication enabled (User: %s)" % colour_text(COLOUR_BOLD, args.get(TITLE_USER, "<EMPTY>")))

def get_default_port():
    if args.get(TITLE_SSL_CERT):
        return DEFAULT_PORT_SSL
    return DEFAULT_PORT

def get_target_information():
    return (args.get(TITLE_BIND, DEFAULT_BIND), args.get(TITLE_PORT, get_default_port()), args.get(TITLE_DIR, os.getcwd()))

def serve(handler, change_directory = False):
    bind_address, bind_port, directory = get_target_information()
    try:
        if change_directory:
            os.chdir(directory)
        server = ThreadedHTTPServer((bind_address, bind_port), handler)

        if args.get(TITLE_SSL_CERT):
            server.socket = ssl.wrap_socket(server.socket, server_side=True, keyfile=args.get(TITLE_SSL_KEY), certfile=args.get(TITLE_SSL_CERT))

        print_notice("Starting server, use <Ctrl-C> to stop")
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl-C
        server.kill_requests()
        exit(130)
    except ssl.SSLError as e:
        m = "Unexpected %s: " % colour_text(COLOUR_RED, type(e).__name__)
        if re.match("^\[SSL\] PEM lib", str(e)):
            # '[SSL] PEM lib (_ssl.c:2798)' is super-unhelpful, so we will provide our own error message.
            # Unconfirmed: Is a missing key the only that can cause this?
            m+= "Must specify a key file or a cert file that also contains a key."
        else:
            # Append regular error message
            m += str(e)
        print_error(m)
    except Exception as e:
        print_error("Unexpected %s: %s" % (colour_text(COLOUR_RED, type(e).__name__), str(e)))
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
    log_on_send_error = False

    error_message_format = DEFAULT_ERROR_MESSAGE

    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.setup()

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

    def get_header_dict(self, header_str):
        return {l.split(":")[0]:":".join(l.split(":")[1:]) for l in str(header_str).split("\r\n") if l}

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

            verbose = args.get(TITLE_VERBOSE, DEFAULT_VERBOSE)
            wanted_user = args.get(TITLE_USER, "")
            wanted_password = args.get(TITLE_PASSWORD, "")
            if wanted_user or wanted_password:
                raw_creds = self.headers_dict.get("Authorization", "").split()
                if not raw_creds or len(raw_creds) < 2:
                    # No creds message
                    if verbose:
                        print_error("Client provided no credentials.")
                    return self.send_error(401, args.get(TITLE_AUTH_PROMPT, DEFAULT_AUTH_PROMPT))

                # Decode
                creds_list = []
                try:
                    creds_list = base64.b64decode(raw_creds[1]).split(":")
                except TypeError:
                    pass

                if len(creds_list) < 2:
                    # Creds message invalid, too few fields within.
                    if verbose:
                        print_error("Client provided an invalid Authorization header.")
                    return self.send_error(401, args.get(TITLE_AUTH_PROMPT, DEFAULT_AUTH_PROMPT))
                user = creds_list[0]
                password = ":".join(creds_list[1:])
                if user != wanted_user or password != wanted_password:
                    # Bad Credentials
                    if verbose:
                        # Also printing credentials.
                        # This is supposed to be used for quick, silly sharing scripts.
                        # If this ever gets used for something more serious, this printout should be removed.
                        print_error("Client provided invalid credentials: (User: %s)(Password: %s)" % (colour_text(COLOUR_BOLD, user), colour_text(COLOUR_BOLD, password)))
                    return self.send_error(401, args.get(TITLE_AUTH_PROMPT, DEFAULT_AUTH_PROMPT))

            if self.command == "POST" and args.get(TITLE_POST, DEFAULT_POST):
                self.command = "GET"

            mname = 'do_' + self.command
            if not hasattr(self, mname):
                self.send_error(501, "Unsupported method (%r)" % self.command)
                return
            method = getattr(self, mname)
            method()
            self.wfile.flush() #actually send the response if not already done.
        except socket.timeout, e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = 1
            return

    def log_message(self, format, *values):
        """Log an arbitrary message.
        This is used by all other logging functions.  Override
        it if you have specific logging wishes.
        The first argument, FORMAT, is a format string for the
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

        if response_code == 200:
            http_code_colour = COLOUR_GREEN
        elif response_code in (301, 307):
            http_code_colour = COLOUR_PURPLE
            extra_info = '[%s]' % colour_text(COLOUR_PURPLE, "Redirect")
        elif response_code == 404:
            extra_info = '[%s]' % colour_text(COLOUR_RED, "File Not Found")

        # Does address string match the client address? If not, print both.
        s = self.address_string()
        footer = ""

        # A 400 (bad request) error is more likely to contain corrupted information.
        # A likely cause of a bad request is a non-HTTP protocol being used (e.g. HTTPS, SSH).
        # We do not want to print this information, so we will be overwriting our values tuple.
        if response_code == 400:
            values = (colour_text(COLOUR_RED, "BAD REQUEST"), response_code, values[2])
        else:
            # Non-400 response.
            request_items = values[0].split(" ")
            values = (" ".join([request_items[0], colour_text(COLOUR_GREEN, request_items[1]), request_items[2]]), values[1], values[2])

            if args.get(TITLE_VERBOSE, DEFAULT_VERBOSE):
                user_agent = self.headers_dict.get("User-Agent")
                if user_agent:
                    footer=" (User Agent: %s)" % colour_text(COLOUR_BOLD, user_agent.strip())

        trailer = "[%s][%s]%s: %s%s\n" % (colour_text(COLOUR_BOLD, self.log_date_time_string()), colour_text(http_code_colour, values[1]), extra_info, values[0], footer)
        src = "%s " % colour_text(COLOUR_GREEN, self.client_address[0])

        if s != self.client_address[0]:
            src += "(%s)" % colour_text(COLOUR_GREEN, s)

        # When a a proxy such as Squid or Apache forwards information,
        # (ProxyPass/ProxyPassReverse directives for Apache),
        # the original client's IP is stored in the 'X-Forwarded-For' header.
        # Trust this value as the true client address if it regexes to an IPv4 address.
        proxy_src = None
        proxy_steps = []
        forward_spec = self.headers_dict.get("X-Forwarded-For", "").strip()
        if forward_spec:
            forward_components = [c.strip() for c in forward_spec.split(",")]
            forward_addr = forward_components.pop(0)
            if forward_addr and re.match(REGEX_INET4, forward_addr):
                proxy_src = forward_addr
                proxy_steps = forward_components
        else:
            # As a fallback, try the 'Forwarded' header put forward by RFC 7239.
            forward_spec = self.headers_dict.get("Forwarded", "").strip()
            try:
                forward_addr = forward_spec.split(";")[2].split("=")[1]
                if forward_addr and re.match(REGEX_INET4, forward_addr):
                    proxy_src = forward_addr
            except:
                # Lazy approach. Skip validation of lists by encasing everything in a try-catch.
                pass

        if proxy_src:
            old_src = src.strip()
            src = "%s [proxy via " % colour_text(COLOUR_GREEN, proxy_src)

            if proxy_steps:
                first = True
                for step in proxy_steps:
                    if not first:
                        first += "->"
                    first = False
                    if re.match(REGEX_INET4, step):
                        src += colour_text(COLOUR_GREEN, step)
                    else:
                        # Wonky input. Maliciously formed?
                        # For now, just say "???" and deal with any troubles as they come up.
                        src += colour_text(COLOUR_BOLD, "???")
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

        if not access.is_allowed(self.client_address[0]):
            self.send_error(403,"Access Denied")
            return False

        # Examine the headers and look for a Connection directive
        self.headers = self.MessageClass(self.rfile, 0)
        # I was not able to successfully use the MIMEMessage object, so parsing it into a dictionary instead.
        self.headers_dict = self.get_header_dict(self.headers)

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
                    print_notice("%s %s: %s" % (action, title, colour_text(COLOUR_GREEN, address)))
                else:
                    print_notice("%s %s: %s (%s)" % (action, title, colour_text(COLOUR_GREEN, address), colour_text(COLOUR_GREEN, ip)))

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
            self.errors.append("Unable to resolve: %s" % colour_text(COLOUR_GREEN, candidate))
            return (False, None, None)

    def ip_validate_cidr(self, candidate):
        a = candidate.split("/")[0]
        m = candidate.split("/")[1]
        try:
            if socket.gethostbyname(a) and int(m) <= 32:
                return (True, self.ip_network_mask(a, m))
        except socket.gaierror:
            pass
        self.errors.append("Invalid CIDR address: %s" % colour_text(COLOUR_GREEN, candidate))
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
            self.errors.append("Path to %s file does not exist: %s" % (header, colour_text(COLOUR_GREEN, path)))
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

        try:
            req = self.RequestHandlerClass(request, client_address, self)
            self.requests[client_address] = req
            req.run()
        except Exception as e:
            print_error("%s: %s" % (colour_text(COLOUR_GREEN, client_address[0]), e))
        del self.requests[client_address]

    def kill_requests(self):
        self.alive = False
        for client_address in self.requests.keys():
            self.requests[client_address].alive = False

args = {}
raw_int_args = {}
access = NetAccess()