#!/usr/bin/python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

# Basic includes
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ThreadingMixIn
import getopt, os, re, socket, struct, sys
# Extra imports used in improved directory listing
import base64, cgi, socket, urllib
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

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

def print_error(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_RED, "Error", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_notice(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_BLUE, "Notice", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

DEFAULT_AUTH_PROMPT = "Authorization Required"

def hexit(exit_code):
    print "%s [-a allow-address/range] [-A allow-list-file] [-b bind-address] [-d deny-address/range] [-D deny-list-file] [-h] [-p port] [-P] [-r] [-t]" % os.path.basename(sys.argv[0])
    exit(exit_code)

def process_arguments():
    args = {}
    error = False
    errors = []
    global access
    access = NetAccess()

    try:
        opts, flat_args = getopt.gnu_getopt(sys.argv[1:],"a:A:b:d:D:hp:Prt", ["password=", "prompt=", "user="])
    except getopt.GetoptError as e:
        print "GetoptError: %s" % e
        hexit(1)
    for opt, arg in opts:
        if opt in ("-a"):
            error = access.add_whitelist(arg) or error
        elif opt in ("-A"):
            error = access.load_whitelist_file(arg) or error
        elif opt in ("-b"):
            args["bind"] = arg
        elif opt in ("-d"):
            error = access.add_blacklist(arg) or error
        elif opt in ("-D"):
            error = access.load_blacklist_file(arg) or error
        elif opt in ("-h"):
            hexit(0)
        elif opt in ("-p"):
            args["port"] = int(arg)
        elif opt in ("-P"):
            args["post"] = True
        elif opt in ("-r"):
            args["reverse"] = True
        elif opt in ("-t"):
            args["timesort"] = True
        elif opt in ("--password"):
            args["password"] = arg
        elif opt in ("--prompt"):
            args["auth-prompt"] = arg
        elif opt in ("--user"):
            args["user"] = arg

    switch_arg = False
    if len(flat_args):
        args["dir"] = flat_args[len(flat_args)-1]

    if len(access.errors):
        error = True
        errors.extend(access.errors)

    if not error:
        access.announce_filter_actions()
    else:
        for e in errors:
            print "Error: %s" % e

    return error, args

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
        error = False
        candidate = candidate.strip()
        if re.match(self.REGEX_INET4_CIDR, candidate):
            e, n = self.ip_validate_cidr(candidate)
            error = e
            if not e:
                # No error
                net_list.append((n, candidate))
        else:
            e, a, astr = self.ip_validate_address(candidate)
            error = e
            if not e:
                # No error
                addr_list.append((a, candidate, astr))
        return error

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
                    print "%s %s: %s%s%s" % (action, title, COLOUR_GREEN, address, COLOUR_OFF)
                else:
                    print "%s %s: %s%s%s (%s%s%s)" % (action, title, COLOUR_GREEN, address, COLOUR_OFF, COLOUR_GREEN, ip, COLOUR_OFF)

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
            return (False, self.ip_strton(ip), ip)
        except socket.gaierror:
            self.errors.append("Unable to resolve: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF))
            return (True, None, None)

    def ip_validate_cidr(self, candidate):
        a = candidate.split("/")[0]
        m = candidate.split("/")[1]
        try:
            if socket.gethostbyname(a) and int(m) <= 32:
                return (False, self.ip_network_mask(a, m))
        except socket.gaierror:
            pass
        self.errors.append("Invalid CIDR address: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF))
        return (True, None)

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
            self.errors.append("Path to %s file does not exist: %s%s%s" % (header, COLOUR_GREEN, path, COLOUR_OFF))
            return False
        with open(path) as f:
            for l in f.readlines():
                fn(l)

    def load_blacklist_file(self, path):
        return self.load_access_file(self.add_blacklist, path, "blacklist")

    def load_whitelist_file(self, path):
        return self.load_access_file(self.add_whitelist, path, "whitelist")

class SimpleHTTPVerboseReqeustHandler(SimpleHTTPRequestHandler):

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    alive = True

    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.setup()
        # Note: Later run steps are in run() method

    def do_GET(self):
        """Serve a GET request."""
        f = self.send_head()
        if f:
            while self.alive:
                buf = f.read(16*1024)
                if not (buf and self.alive):
                    break
                self.wfile.write(buf)
            self.alive = False
            f.close()

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

            if not access.is_allowed(self.client_address[0]):
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(403,"Access Denied")
                return

            if not self.parse_request():
                # An error code has been sent, just exit
                return

            wanted_user = args.get("user", "")
            wanted_password = args.get("password", "")
            if wanted_user or wanted_password:
                raw_creds = self.headers_dict.get("Authorization", "").split()
                if not raw_creds or len(raw_creds) < 2:
                    # No creds message
                    return self.send_error(401, args.get("auth-prompt", DEFAULT_AUTH_PROMPT))
                creds_list = base64.b64decode(raw_creds[1]).split(":")
                if len(creds_list) < 2:
                    # Creds message invalid, too few fields within.
                    return self.send_error(401, args.get("auth-prompt", DEFAULT_AUTH_PROMPT))
                user = creds_list[0]
                password = ":".join(creds_list[1:])
                if user != wanted_user or password != wanted_password:
                    # Bad Credentials
                    return self.send_error(401, args.get("auth-prompt", DEFAULT_AUTH_PROMPT))

            if self.command == "POST" and args.get("post", False):
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

    def humansize(self, nbytes):
        if nbytes == 0: return '0B'
        i = 0
        while nbytes >= 1024 and i < len(self.suffixes)-1:
            nbytes /= 1024.
            i += 1
        f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
        return '%s%s' % (f, self.suffixes[i])

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).
        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().
        """
        try:
            itemlist = os.listdir(path)
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None

        if args.get("timesort", False):
            itemlist.sort(key=lambda a: os.path.getmtime(os.path.join(path, a)), reverse=args.get("reverse", False))
        else:
            itemlist.sort(key=lambda a: a.lower(), reverse=args.get("reverse", False))

        f = StringIO()
        displaypath = cgi.escape(urllib.unquote(self.path))
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">\n')
        f.write("<html>\n<title>Directory listing for %s (%s)</title>\n" % (displaypath, os.getcwd()))
        f.write("<body>\n  <h2>Directory listing for %s</h2>\n" % displaypath)
        f.write("    <h3>Full path: %s%s</h3>\n" % (os.getcwd(), displaypath))
        f.write("        <p>%s</p>\n" % self.render_breadcrumbs(displaypath))
        f.write("      <hr>\n      <ul>\n")

        if not self.path == "/":
            f.write('        <li><a href="..">%s</a></li>\n' % cgi.escape("<UP ONE LEVEL>"))
        for name in itemlist:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            extrainfo = ""

            # Note: a link to a directory displays with @ and links with /
            if os.path.islink(fullname):
                displayname = name + "@"

                # Append / for directories or @ for symbolic links
                if os.path.isdir(os.path.realpath(fullname)):
                    # Directory via Symlink
                    displayname = name + "/@"
                    linkname = name + "/"

                    extrainfo = "(Symlink to directory <strong>%s</strong>)" % cgi.escape(os.path.realpath(fullname))
                elif os.path.isfile(os.path.realpath(fullname)):
                    # File via Symlink
                    extrainfo = "(Symlink to %s file <strong>%s</strong>)" % (self.humansize(os.stat(fullname).st_size), cgi.escape(os.path.realpath(fullname)))
                else:
                    # Dead symlink
                    linkname = None
                    extrainfo = "(Dead symlink to <strong>%s</strong>)" % os.readlink(fullname)
            elif os.path.isdir(fullname):
                # Directory
                displayname = name + "/"
                linkname = name + "/"
                extrainfo = "(Directory)"
            else:
                # File
                extrainfo = "(%s File)" % self.humansize(os.stat(fullname).st_size)

            if linkname:
                f.write('        <li><a href="%s">%s</a> %s</li>\n'
                        % (urllib.quote(linkname), cgi.escape(displayname), extrainfo))
            else:
                f.write('        <li><strong>%s</strong> %s</li>\n'
                        % (cgi.escape(displayname), extrainfo))
        f.write("      </ul>\n      <hr>\n  </body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        encoding = sys.getfilesystemencoding()
        self.send_header("Content-type", "text/html; charset=%s" % encoding)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f

    def log_message(self, format, *args):
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

        if type(args[0]) == int:
            # Errors may be presented as tuples starting with error code as int.
            # Do not bother printing extra information on error codes in a new line.
            return
        else:
            words = args[0].split()
            if args[1] == '404' and len(words) > 1 and words[1].endswith("favicon.ico"):
                # Do not bother printing not-found information on favicon.ico.
                return

        http_code_colour = COLOUR_RED
        extra_info = ''
        try:
            response_code = int(args[1])
        except ValueError:
            response_code = "???"

        if response_code == 200:
            http_code_colour = COLOUR_GREEN
        elif response_code in (301, 307):
            http_code_colour = COLOUR_PURPLE
            extra_info = '[%s%s%s]' % (COLOUR_PURPLE, "Redirect", COLOUR_OFF)
        elif response_code == 404:
            extra_info = '[%s%s%s]' % (COLOUR_RED, "File Not Found", COLOUR_OFF)

        # Does address string match the client address? If not, print both.
        s = self.address_string()

        # A 400 (bad request) error is more likely to contain corrupted information.
        # A likely cause of a bad request is a non-HTTP protocol being used (e.g. HTTPS, SSH).
        # We do not want to print this information, so we will be overwriting our args tuple.
        if response_code == 400:
            args = ("%s%s%s" % (COLOUR_RED, "BAD REQUEST", COLOUR_OFF), response_code, args[2])

        if s == self.client_address[0]:
            sys.stdout.write("%s%s%s [%s%s%s][%s%s%s]%s: %s\n" % (COLOUR_GREEN, self.address_string(), COLOUR_OFF, COLOUR_BOLD, self.log_date_time_string(), COLOUR_OFF, http_code_colour, args[1], COLOUR_OFF, extra_info, args[0]))
        else:
            sys.stdout.write("%s%s%s (%s%s%s)[%s%s%s][%s%s%s]%s: %s\n" % (COLOUR_GREEN, s, COLOUR_OFF, COLOUR_GREEN, self.client_address[0], COLOUR_OFF, COLOUR_BOLD, self.log_date_time_string(), COLOUR_OFF, http_code_colour, args[1], COLOUR_OFF, extra_info, args[0]))

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
                self.send_error(400, "Bad request version (%r)" % version)
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
                                "Bad HTTP/0.9 request type (%r)" % command)
                return False
        elif not words:
            return False
        else:
            self.send_error(400, "Bad request syntax (%r)" % requestline)
            return False
        self.command, self.path, self.request_version = command, path, version

        # Examine the headers and look for a Connection directive
        self.headers = self.MessageClass(self.rfile, 0)
        # I was not able to successfully use the MIMEMessage object, so parsing it into a dictionary instead.
        self.headers_dict = {l.split(":")[0]:":".join(l.split(":")[1:]) for l in str(self.headers).split("\r\n") if l}

        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif (conntype.lower() == 'keep-alive' and
              self.protocol_version >= "HTTP/1.1"):
            self.close_connection = 0
        return True

    def quote_html(self, html):
        return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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
        self.send_response(code, message)
        self.send_header("Content-Type", self.error_content_type)
        self.send_header('Connection', 'close')
        if code == 401:
            self.send_header('WWW-Authenticate', 'Basic realm="%s"' % message)
        self.end_headers()
        if self.command != 'HEAD' and code >= 200 and code not in (204, 304):
            self.wfile.write(content)

    def send_head(self):
        """Common code for GET and HEAD commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            if not self.path.endswith('/'):
                return self.send_redirect(self.path + "/")
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
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

    def send_redirect(self, target):
        # redirect browser - doing basically what apache does
        self.send_response(307)
        self.send_header("Location", target)
        self.end_headers()
        return None

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
            print_error("%s%s%s: %s" % (COLOUR_GREEN, client_address[0], COLOUR_OFF, e))
        del self.requests[client_address]

    def kill_requests(self):
        self.alive = False
        for client_address in self.requests.keys():
            self.requests[client_address].alive = False

if __name__ == '__main__':
    error, args = process_arguments()
    if error:
        exit(1)
    bind_address = args.get("bind", "0.0.0.0")
    bind_port = args.get("port", 8080)
    directory = args.get("dir", os.getcwd())
    if not os.path.isdir(directory):
        print_error("Path %s%s%s does not seem to exist." % (COLOUR_GREEN, os.path.realpath(directory), COLOUR_OFF))
        exit(1)

    print_notice("Sharing %s%s%s on %s%s:%d%s" % (COLOUR_GREEN, os.path.realpath(directory), COLOUR_OFF, COLOUR_GREEN, bind_address, bind_port, COLOUR_OFF))

    if args.get("post", False):
        print_notice("Accepting %s%s%s messages. Will not process, but will not throw a %s%s%s code either." % (COLOUR_BOLD, "POST", COLOUR_OFF, COLOUR_RED, "501", COLOUR_OFF))

    if args.get("user"):
        print("Basic authentication enabled (User: %s%s%s)" % (COLOUR_BOLD, args.get("user", "<EMPTY>"), COLOUR_OFF))

    try:
        os.chdir(directory)
        server = ThreadedHTTPServer((bind_address, bind_port), SimpleHTTPVerboseReqeustHandler)
        print_notice("Starting server, use <Ctrl-C> to stop")
        server.serve_forever()
    except socket.error as e:
        print_error("SocketError: %s" % e)
        exit(1)
    except KeyboardInterrupt:
        # Ctrl-C
        server.kill_requests()
        exit(130)
