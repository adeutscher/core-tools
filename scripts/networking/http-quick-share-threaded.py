#!/usr/bin/python   

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

# Basic includes
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ThreadingMixIn
import getopt, os, sys
# Extra imports used in improved directory listing
import cgi, urllib
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

def process_arguments():
    args = {}
    try:
        opts, flat_args = getopt.gnu_getopt(sys.argv[1:],"b:p:")
    except getopt.GetoptError:
        print "GetoptError"
        sys.exit(1)
    for opt, arg in opts:
        if opt in ("-b"):
            args["bind"] = arg
        elif opt in ("-p"):
            args["port"] = int(arg)
    switch_arg = False
    if len(flat_args):
        args["dir"] = flat_args[len(flat_args)-1]
    return args

class SimpleHTTPVerboseReqeustHandler(SimpleHTTPRequestHandler):

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

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
                # Append / for directories or @ for symbolic links
                if os.path.isdir(os.path.realpath(fullname)):
                    # Directory via Symlink
                    displayname = name + "/@"
                    linkname = name + "/"
                    extrainfo = "(Symlink to directory <strong>%s</strong>)" % cgi.escape(os.path.realpath(fullname))
                else:
                    # File via Symlink
                    displayname = name + "@"
                    linkname = name + "/"
                    extrainfo = "(Symlink to %s file <strong>%s</strong>)" % (self.humansize(os.stat(fullname).st_size), cgi.escape(os.path.realpath(fullname)))
            elif os.path.isdir(fullname):
                # Directory
                displayname = name + "/"
                linkname = name + "/"
                extrainfo = "(Directory)"
            else:
                # File
                extrainfo = "(%s File)" % self.humansize(os.stat(fullname).st_size)

            f.write('<li><a href="%s">%s</a> %s\n'
                    % (urllib.quote(linkname), cgi.escape(displayname), extrainfo))
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
            print item
            i += 1
            if i == len(items):
                content += " / <strong>%s</strong>" % item[1]
            else:
                content += " / <a href='%s'>%s</a>" % (item[0], item[1])
        return content

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

if __name__ == '__main__':
    args = process_arguments()
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

    server = ThreadedHTTPServer((bind_address, bind_port), SimpleHTTPVerboseReqeustHandler)
    if sys.stdout.isatty():
        print "Sharing \033[1;92m%s\033[0m on %s:%d" % (os.path.realpath(directory), bind_address, bind_port)
    else:
        print "Sharing %s on %s:%d" % (os.path.realpath(directory), bind_address, bind_port)
    print "Starting server, use <Ctrl-C> to stop"
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        exit(130)
