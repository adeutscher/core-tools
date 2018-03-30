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
import cgi, socket, urllib
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

# Basic syntax check
REGEX_INET4_CIDR='^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

if sys.stdout.isatty():
    # Colours for standard output.
    COLOUR_RED= '\033[1;91m'
    COLOUR_GREEN = '\033[1;92m'
    COLOUR_YELLOW = '\033[1;93m'
    COLOUR_BLUE = '\033[1;94m'
    COLOUR_PURPLE = '\033[1;95m'
    COLOUR_BOLD = '\033[1m'
    COLOUR_OFF = '\033[0m'
else:
    # Set to blank values if not to standard output.
    COLOUR_RED= ''
    COLOUR_GREEN = ''
    COLOUR_YELLOW = ''
    COLOUR_BLUE = ''
    COLOUR_PURPLE = ''
    COLOUR_BOLD = ''
    COLOUR_OFF = ''

def announce_filter_action(action, title, address, ip):
    if ip == address:
        print "%s %s: %s%s%s" % (action, title, COLOUR_GREEN, address, COLOUR_OFF)
    else:
        print "%s %s: %s%s%s (%s%s%s)" % (action, title, COLOUR_GREEN, address, COLOUR_OFF, COLOUR_GREEN, ip, COLOUR_OFF)

# Credit for IP functions: http://code.activestate.com/recipes/66517/

def hexit(exit_code):
    print "%s [-a allow-address/range] [-b bind-address] [-d deny-address/range] [-h] [-p port] [-P] [-r] [-t]" % os.path.basename(sys.argv[0])
    exit(exit_code)

def ip_make_mask(n):
    # Return a mask of n bits as a long integer
    return (2L<<n-1)-1

def ip_strton(ip):
    # Convert decimal dotted quad string to long integer
    return struct.unpack('<L',socket.inet_aton(ip))[0]

def ip_network_mask(ip, bits):
    # Convert a network address to a long integer
    return ip_strton(ip) & ip_make_mask(int(bits))

def ip_addrn_in_network(ip,net):
   # Is a numeric address in a network?
   return ip & net == net

def ip_validate_address(candidate):
    try:
        ip = socket.gethostbyname(candidate)
        return (False, ip_strton(ip), ip)
    except socket.gaierror:
        print >> sys.stderr, "Unable to resolve: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF)
        return (True, None, None)

def ip_validate_cidr(candidate):
    a = candidate.split("/")[0]
    m = candidate.split("/")[1]
    try:
        if socket.gethostbyname(a) and int(m) <= 32:
            return (False, ip_network_mask(a, m))
    except socket.gaierror:
        pass
    print >> sys.stderr, "Invalid CIDR address: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF)
    return (True, None)

def process_arguments():
    args = {"denied_addresses":[], "denied_networks":[],"allowed_addresses":[], "allowed_networks":[]}
    error = False

    try:
        opts, flat_args = getopt.gnu_getopt(sys.argv[1:],"a:b:d:hp:Prt")
    except getopt.GetoptError as e:
        print "GetoptError: %s" % e
        hexit(1)
    for opt, arg in opts:
        if opt in ("-a"):
            if re.match(REGEX_INET4_CIDR, arg):
                e, n = ip_validate_cidr(arg)
                error = error or e
                if not e:
                    # No error
                    args["allowed_networks"].append((n,arg))
            else:
                e, a, astr = ip_validate_address(arg)
                error = error or e
                if not e:
                    # No error
                    args["allowed_addresses"].append((a, arg, astr))
        elif opt in ("-b"):
            args["bind"] = arg
        elif opt in ("-d"):
            if re.match(REGEX_INET4_CIDR, arg):
                e, n = ip_validate_cidr(arg)
                error = error or e
                if not e:
                    # No error
                    args["denied_networks"].append((n, arg))
            else:
                e, a, astr = ip_validate_address(arg)
                error = error or e
                if not e:
                    # No error
                    args["denied_addresses"].append((a, arg, astr))
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
    switch_arg = False
    if len(flat_args):
        args["dir"] = flat_args[len(flat_args)-1]

    if not error:
        for t in [("allowed", "Allowing"), ("denied", "Denying")]:
            for n, s, i in args["%s_addresses" % t[0]]:
                announce_filter_action(t[1], "address", s, i)
            for n, s in args["%s_networks" % t[0]]:
                announce_filter_action(t[1], "network", s, s)

    return error, args

class SimpleHTTPVerboseReqeustHandler(SimpleHTTPRequestHandler):

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

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

            # Blacklist/Whitelist filtering
            allowed = True

            if len(args["allowed_addresses"]) or len(args["allowed_networks"]):
                # Whitelist processing, address is not allowed until it is cleared.
                allowed = False

                if self.client_address[0] in [a[2] for a in args["allowed_addresses"]]:
                    allowed = True
                else:
                    # Try checking allowed networks
                    cn = ip_strton(self.client_address[0])
                    for n in [n[0] for n in args["allowed_networks"]]:
                        if ip_addrn_in_network(cn, n):
                            allowed = True
                            break

            if args["denied_addresses"] or args["denied_networks"]:
                # Blacklist processing. A blacklist argument one-ups a whitelist argument in the event of a conflict

                if self.client_address[0] in [a[2] for a in args["denied_addresses"]]:
                    allowed = False
                else:
                    # Try checking denied networks
                    cn = ip_strton(self.client_address[0])
                    for n in [n[0] for n in args["denied_networks"]]:
                        if ip_addrn_in_network(cn, n):
                            allowed = False
                            break

            if not allowed:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(403,"Access Denied")
                return

            if not self.parse_request():
                # An error code has been sent, just exit
                return

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
        if args[1] == "200":
            http_code_colour = COLOUR_GREEN
        elif args[1] == "301":
            http_code_colour = COLOUR_PURPLE
            extra_info = '[%s%s%s]' % (COLOUR_PURPLE, "Redirect", COLOUR_OFF)
        elif args[1] == "404":
            extra_info = '[%s%s%s]' % (COLOUR_RED, "File Not Found", COLOUR_OFF)

        s = self.address_string()
        if s == self.client_address[0]:
            sys.stdout.write("%s%s%s [%s%s%s][%s%s%s]: %s\n" % (COLOUR_GREEN, self.address_string(), COLOUR_OFF, COLOUR_BOLD, self.log_date_time_string(), COLOUR_OFF, http_code_colour, args[1], COLOUR_OFF, args[0]))
        else:
            sys.stdout.write("%s%s%s (%s%s%s)[%s%s%s][%s%s%s]: %s\n" % (COLOUR_GREEN, self.address_string(), COLOUR_OFF, COLOUR_GREEN, self.client_address[0], COLOUR_OFF, COLOUR_BOLD, self.log_date_time_string(), COLOUR_OFF, http_code_colour, args[1], COLOUR_OFF, args[0]))

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

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

if __name__ == '__main__':
    error, args = process_arguments()
    if error:
        exit(1)
    bind_address = args.get("bind", "0.0.0.0")
    bind_port = args.get("port", 8080)
    directory = args.get("dir", os.getcwd())
    if not os.path.isdir(directory):
        print "Path %s does not seem to exist." % (COLOUR_GREEN, os.path.realpath(directory), COLOUR_OFF)
        exit(1)

    print "Sharing %s%s%s on %s%s:%d%s" % (COLOUR_GREEN, os.path.realpath(directory), COLOUR_OFF, COLOUR_GREEN, bind_address, bind_port, COLOUR_OFF)
    if args.get("post", False):
        print "Accepting %s%s%s messages. Will not process, but will not throw a %s%s%s code either." % (COLOUR_BOLD, "POST", COLOUR_OFF, COLOUR_RED, "501", COLOUR_OFF)
    try:
        os.chdir(directory)
        server = ThreadedHTTPServer((bind_address, bind_port), SimpleHTTPVerboseReqeustHandler)
        print "Starting server, use <Ctrl-C> to stop"
        server.serve_forever()
    except socket.error as e:
        print "SocketError: %s" % e
        exit(1)
    except KeyboardInterrupt:
        exit(130)
