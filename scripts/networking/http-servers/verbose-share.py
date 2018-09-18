#!/usr/bin/env python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

import getopt, os, socket, sys, urllib
import CoreHttpServer as common

# Specific to browser sharer

import cgi

# Script Content

DEFAULT_REVERSE = False
DEFAULT_TIMESORT = False

TITLE_REVERSE = "reverse"
TITLE_TIMESORT = "timesort"
TITLE_NO_LINKS = "nolinks"
TITLE_LOCAL_LINKS = "locallinks"

def hexit(exit_code):
    print "%s [-a allow-address/range] [-A allow-list-file] [-b bind-address] [-d deny-address/range] [-D deny-list-file] [-h] [-l] [-n] [-p port] [-P] [-r] [-t] [-v]" % os.path.basename(sys.argv[0])
    exit(exit_code)

def process_arguments():

    # Verbose Sharing Arguments

    good = True
    errors = []

    short_opts = common.common_short_opts + "hlnrt"
    long_opts = common.common_long_opts + [ "--local-links", "--no-links" ]

    try:
        opts, flat_args = getopt.gnu_getopt(sys.argv[1:], short_opts, long_opts)
    except getopt.GetoptError as e:
        print "GetoptError: %s" % str(e)
        hexit(1)
    for opt, arg in opts:
        common_good, processed = common.handle_common_argument(opt, arg)
        good = common_good and good

        if processed:
            continue

        if opt in ("-h"):
            hexit(0)
        elif opt in ("-l", "--local-links"):
            common.args[TITLE_LOCAL_LINKS] = True
        elif opt in ("-n", "--no-links"):
            common.args[TITLE_NO_LINKS] = True
        elif opt in ("-r"):
            common.args[TITLE_REVERSE] = True
        elif opt in ("-t"):
            common.args[TITLE_TIMESORT] = True

    switch_arg = False
    if flat_args:
        common.args[common.TITLE_DIR] = flat_args[len(flat_args)-1]

    if len(common.access.errors):
        good = False
        errors.extend(common.access.errors)

    if good:
        common.access.announce_filter_actions()
    else:
        for e in errors:
            common.print_error(e)

    return good

class SimpleHTTPVerboseReqeustHandler(common.CoreHttpServer):

    server_version = "CoreHttpServer (Content Serving)"

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
            itemlist = os.listdir(path)
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None

        reverse_order = common.args.get(TITLE_REVERSE, DEFAULT_REVERSE)

        if common.args.get(TITLE_TIMESORT, DEFAULT_TIMESORT):
            itemlist.sort(key=lambda a: os.path.getmtime(os.path.join(path, a)), reverse = reverse_order)
        else:
            itemlist.sort(key=lambda a: a.lower(), reverse = reverse_order)

        displaypath = cgi.escape(urllib.unquote(self.path))
        htmlContent = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
    <head>
        <title>Directory listing for %s (%s)</title>
    </head>
    <body>
        <h2>Directory listing for %s</h2>
        <h3>Full path: %s%s</h3>
        <p>%s</p>
        <hr>
        <ul>
""" % (displaypath, os.getcwd(), # Title
        displaypath,
        os.getcwd(), displaypath, # Full path
        self.render_breadcrumbs(displaypath)) # Breadcrumbs

        if self.path != "/":
            htmlContent += '        <li><a href="..">%s</a></li>\n' % cgi.escape("<UP ONE LEVEL>")
        for name in itemlist:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            extrainfo = ""
            reachable = True

            if os.path.islink(fullname):
                # Note: a link to a directory displays with @ and links with /
                displayname = name + "@"
                reachable = not (common.args.get(TITLE_NO_LINKS, False) or (common.args.get(TITLE_LOCAL_LINKS, False) and not os.path.realpath(fullname).startswith(os.getcwd() + "/")))

                if not reachable:
                    # Symbolic link is inaccessible. Override extra info to plainly say 'symlink'.
                    if common.args.get(TITLE_NO_LINKS, False):
                        extrainfo = "(Symlink)"
                    else:
                        # Implies local links only, meaning an unreachable link is external.
                        extrainfo = "(External Symlink)"
                elif os.path.isdir(os.path.realpath(fullname)):
                    # Directory via Symlink
                    # Append / for directories or @ for symbolic links
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

            if linkname and reachable:
                htmlContent += '        <li><a href="%s">%s</a> %s</li>\n' % (urllib.quote(linkname), cgi.escape(displayname), extrainfo)
            else:
                htmlContent += '        <li><strong>%s</strong> %s</li>\n' % (cgi.escape(displayname), extrainfo)
        htmlContent += "      </ul>\n      <hr>\n  </body>\n</html>\n"
        return self.serve_content(htmlContent)

    def send_head(self):
        """Common code for GET and HEAD commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """
        path = self.translate_path(self.path)
        if os.path.exists(path):
            # Symbolic link judgement.
            # Paths with denied symbolic links will pretend to be 404 errors.
            if common.args.get(TITLE_LOCAL_LINKS, False) and not os.path.realpath(path).startswith(os.getcwd() + "/"):
                return self.send_error(404, "File not found")
            elif common.args.get(TITLE_NO_LINKS, False):
                # If all symbolic links are banned, then we must trace our
                #   way down an existing path to make sure that no symbolic link exists
                curr = path
                while True:
                    if os.path.islink(curr):
                        return self.send_error(404, "File not found")
                    if curr == path:
                        break
                    curr = os.path.dirname(path);

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
        return self.serve_file(path)

if __name__ == '__main__':
    if not process_arguments():
        exit(1)

    bind_address, bind_port, directory = common.get_target_information()

    if not os.path.isdir(directory):
        common.print_error("Path %s does not seem to exist." % common.colour_text(common.COLOUR_GREEN, os.path.realpath(directory)))
        exit(1)

    common.announce_common_arguments("Serving files")

    if common.args.get(TITLE_NO_LINKS, False):
        common.print_notice("Ignoring all symbolic links.")

    elif common.args.get(TITLE_LOCAL_LINKS, False):
        common.print_notice("Serving only local symbolic links.")

    common.serve(SimpleHTTPVerboseReqeustHandler, True)
