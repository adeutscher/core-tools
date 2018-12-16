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

# Define arguments

# Flags
common.args.add_opt(common.OPT_TYPE_FLAG, "l", TITLE_LOCAL_LINKS, "Only show local links (symbolic links that point to within the shared directory).")
common.args.add_opt(common.OPT_TYPE_FLAG, "n", TITLE_NO_LINKS, "Do not allow symbolic links. Overrides local links.")
common.args.add_opt(common.OPT_TYPE_FLAG, "r", TITLE_REVERSE, "Display listings in reverse order.")
common.args.add_opt(common.OPT_TYPE_FLAG, "t", TITLE_TIMESORT, "Display listings sorted by time (as opposed to alphabetically).")
common.args.add_validator(common.validate_common_directory)

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

        reverse_order = common.args[TITLE_REVERSE]

        if common.args[TITLE_TIMESORT]:
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
                reachable = not (common.args[TITLE_NO_LINKS] or (common.args[TITLE_LOCAL_LINKS] and not os.path.realpath(fullname).startswith(os.getcwd() + "/")))

                if not reachable:
                    # Symbolic link is inaccessible. Override extra info to plainly say 'symlink'.
                    if common.args[TITLE_NO_LINKS]:
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
            if common.args[TITLE_LOCAL_LINKS] and not os.path.realpath(path).startswith(os.getcwd() + "/"):
                return self.send_error(404, "File not found")
            elif common.args[TITLE_NO_LINKS]:
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
    common.args.process(sys.argv)

    common.announce_common_arguments("Serving files")

    if common.args[TITLE_NO_LINKS]:
        common.print_notice("Ignoring all symbolic links.")

    if common.args[TITLE_LOCAL_LINKS]:
        common.print_notice("Serving only local symbolic links.")

    common.serve(SimpleHTTPVerboseReqeustHandler, True)
