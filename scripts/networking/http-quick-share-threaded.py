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

def announce_filter_action(action, title, address, ip):
    if sys.stdout.isatty():
        if ip == address:
            print "%s %s: \033[1;92m%s\033[0m" % (action, title, address)
        else:
            print "%s %s: \033[1;92m%s\033[0m (\033[1;92m%s\033[0m)" % (action, title, address, ip)
    else:
        if ip == address:
            print "%s %s: %s" % (action, title, address)
        else:
            print "%s %s: %s (%s)" % (action, title, address, ip)

# Credit for IP functions: http://code.activestate.com/recipes/66517/

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
        if sys.stderr.isatty():
            print >> sys.stderr, "Unable to resolve: \033[1;92m%s\033[0m" % candidate
        else:
            print >> sys.stderr, "Unable to resolve: %s" % candidate
        return (True, None, None)

def ip_validate_cidr(candidate):
    a = candidate.split("/")[0]
    m = candidate.split("/")[1]
    try:
        if socket.gethostbyname(a) and int(m) <= 32:
            return (False, ip_network_mask(a, m))
        else:
            if sys.stderr.isatty():
                print >> sys.stderr, "Invalid CIDR address: \033[1;92m%s\033[0m" % candidate
            else:
                print >> sys.stderr, "Invalid CIDR address: %s" % candidate
    except socket.gaierror:
        if sys.stderr.isatty():
            print >> sys.stderr, "Invalid CIDR address: \033[1;92m%s\033[0m" % candidate
        else:
            print >> sys.stderr, "Invalid CIDR address: %s" % candidate
    return (True, None)

def process_arguments():
    args = {"denied_addresses":[], "denied_networks":[],"allowed_addresses":[], "allowed_networks":[]}
    error = False

    try:
        opts, flat_args = getopt.gnu_getopt(sys.argv[1:],"a:b:d:p:")
    except getopt.GetoptError as e:
        print "GetoptError: %s" % e
        sys.exit(1)
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
        elif opt in ("-p"):
            args["port"] = int(arg)
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
            list = os.listdir(path)
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None
        list.sort(key=lambda a: a.lower())
        f = StringIO()
        displaypath = cgi.escape(urllib.unquote(self.path))
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Directory listing for %s (%s)</title>\n" % (displaypath, os.getcwd()))
        f.write("<body>\n<h2>Directory listing for %s</h2>\n" % displaypath)
        f.write("<h3>Full path: %s%s</h3>\n" % (os.getcwd(), displaypath))
        f.write(self.render_breadcrumbs(displaypath))
        f.write("<hr>\n<ul>\n")

        if not self.path == "/":
            f.write('<li><a href="..">%s</a>\n' % cgi.escape("<UP ONE LEVEL>"))
        for name in list:
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
                f.write('<li><a href="%s">%s</a> %s\n'
                        % (urllib.quote(linkname), cgi.escape(displayname), extrainfo))
            else:
                f.write('<li><strong>%s</strong> %s\n'
                        % (cgi.escape(displayname), extrainfo))
        f.write("</ul>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        encoding = sys.getfilesystemencoding()
        self.send_header("Content-type", "text/html; charset=%s" % encoding)
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f

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
        if sys.stdout.isatty():
            print "Path \033[1;92m%s\033[0m does not seem to exist." % os.path.realpath(directory)
        else:
            print "Path %s does not seem to exist." % os.path.realpath(directory)
        exit(1)
    os.chdir(directory)

    if sys.stdout.isatty():
        print "Sharing \033[1;92m%s\033[0m on %s:%d" % (os.path.realpath(directory), bind_address, bind_port)
    else:
        print "Sharing %s on %s:%d" % (os.path.realpath(directory), bind_address, bind_port)
    try:
        server = ThreadedHTTPServer((bind_address, bind_port), SimpleHTTPVerboseReqeustHandler)
        print "Starting server, use <Ctrl-C> to stop"
        server.serve_forever()
    except socket.error as e:
        print "SocketError: %s" % e
        exit(1)
    except KeyboardInterrupt:
        exit(130)
