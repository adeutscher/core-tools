#!/usr/bin/env python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

import datetime, getopt, os, socket, sys, urllib
import CoreHttpServer as common
from CoreHttpServer import args, print_notice
common.local_files.append(os.path.realpath(__file__))

# Specific to browser sharer

import cgi

# Script Content

DEFAULT_REVERSE = False
DEFAULT_TIMESORT = False

TITLE_NO_LINKS = "nolinks"
TITLE_LOCAL_LINKS = "locallinks"

LABEL_GET_CATEGORY = 'C'
LABEL_GET_ORDER = 'O'

LABEL_ORDER_DESCENDING = 'D'
LABEL_ORDER_ASCENDING = 'A'

LABEL_CATEGORY_NAME = 'N'
LABEL_CATEGORY_MTIME = 'M'
LABEL_CATEGORY_SIZE = 'S'
LABEL_CATEGORY_TYPE = 'T'

# Define arguments

# Flags
args.add_opt(common.OPT_TYPE_FLAG, "l", TITLE_LOCAL_LINKS, "Only show local links (symbolic links that point to within the shared directory).")
args.add_opt(common.OPT_TYPE_FLAG, "n", TITLE_NO_LINKS, "Do not allow symbolic links. Overrides local links.")
args.add_validator(common.validate_common_directory)

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
            fileNames = os.listdir(path)
        except os.error:
            # Intentionally keeping the reason for this vague.
            # Could be due to a not-found file or a permissions problem.
            self.send_error(404, "Unable to list directory")
            return None

        items = []
        for name in fileNames:

            fullname = os.path.join(path, name)
            displayname = linkname = name
            extrainfo = ''
            reachable = True
            size = 0
            size_display = '-'
            obj_type = 'File'
            mtime = 0.0
            is_file = False

            if os.path.islink(fullname):

                # Note: a link to a directory displays with @ and links with /
                displayname = name + "@"
                reachable = not (args[TITLE_NO_LINKS] or (args[TITLE_LOCAL_LINKS] and not os.path.realpath(fullname).startswith(os.getcwd() + "/")))
                obj_type = 'Sym'

                if not reachable:
                    # Symbolic link is inaccessible. Override extra info to plainly say 'symlink'.
                    if args[TITLE_NO_LINKS]:
                        extrainfo = "(Symlink)"
                    else:
                        # Implies local links only, meaning an unreachable link is external.
                        extrainfo = "(External Symlink)"
                elif os.path.isdir(os.path.realpath(fullname)):
                    # Directory via Symlink
                    # Append / for directories or @ for symbolic links
                    displayname = name + "/@"
                    linkname = name + "/"

                    extrainfo = "Symlink to directory <span class='path'>%s</span>" % cgi.escape(os.path.realpath(fullname))
                elif os.path.isfile(os.path.realpath(fullname)):
                    # File via Symlink
                    extrainfo = "Symlink to %s file <span class='path'>%s</span>" % (self.humansize(os.stat(fullname).st_size), cgi.escape(os.path.realpath(fullname)))
                    is_file = True
                else:
                    # Dead symlink
                    linkname = None
                    extrainfo = "Dead symlink to <span class='path'>%s</span>" % os.readlink(fullname)

            elif os.path.isdir(fullname):
                # Directory
                displayname = name + "/"
                linkname = name + "/"
                obj_type += 'Dir'
            else:
                # File
                is_file = True

            if reachable and is_file:
                size = os.stat(fullname).st_size
                size_display = self.humansize(size)
                mtime = os.path.getmtime(os.path.join(path, name))

            obj = {}
            obj['rawname'] = name
            obj['mtime'] = mtime
            obj['linkname'] = linkname
            obj['displayname'] = displayname
            obj['extrainfo'] = extrainfo
            obj['reachable'] = reachable
            obj['type'] = obj_type
            obj['size'] = size
            obj['size_display'] = size_display

            items.append(obj)

        default_category_label = LABEL_CATEGORY_NAME
        default_order_label = LABEL_ORDER_ASCENDING

        category_label = next(iter(reversed(self.get.get(LABEL_GET_CATEGORY, []))), default_category_label).upper()
        if category_label not in (LABEL_CATEGORY_NAME, LABEL_CATEGORY_MTIME, LABEL_CATEGORY_SIZE, LABEL_CATEGORY_TYPE):
            category = default_category_label

        order_label = next(iter(reversed(self.get.get(LABEL_GET_ORDER, []))), default_order_label).upper()
        if order_label not in (LABEL_ORDER_ASCENDING, LABEL_ORDER_DESCENDING):
            order = default_order_label

        reverse = False
        if order_label == LABEL_ORDER_DESCENDING:
            reverse = True

        if category_label == LABEL_CATEGORY_MTIME:
            items.sort(key=lambda a: (a['mtime'], a['rawname'].lower()), reverse = reverse)
        elif category_label == LABEL_CATEGORY_SIZE:
            items.sort(key=lambda a: (a['size'], a['rawname'].lower()), reverse = reverse)
        elif category_label == LABEL_CATEGORY_TYPE:
            items.sort(key=lambda a: (a['type'], a['rawname'].lower()), reverse = reverse)
        else:
            items.sort(key=lambda a: a['rawname'].lower(), reverse = reverse)

        displaypath = cgi.escape(urllib.unquote(getattr(self, common.ATTR_PATH, "/")))
        htmlContent = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
  <head>
    <title>Directory listing for %s (%s)</title>
    <style>
      th { text-align: left; }
      td { vertical-align: text-top; }
      tr:nth-child(even) {background-color: #f2f2f2;}
      .c_mod { align: right; padding: 0px 10px; min-width: 175px; }
      .c_size { align: right; padding: 0px 10px; }
      .c_info { align: right; }
      .s_dead { color: #821e00; }
      .path { font-weight: bold; }
    </style>
  </head>
  <body>
    <h2>Directory listing for %s</h2>
    <h3>Full path: %s%s</h3>
    <p>%s</p>
    <table>
      <tr><th>%s</th><th class="c_mod">%s</th><th class="c_size">%s</th><th class="c_info">%s</th></tr>
""" % (displaypath, os.getcwd(), # Title
        displaypath,
        os.getcwd(),
        displaypath, # Full path
        self.render_breadcrumbs(displaypath),
        self.render_header("Name", LABEL_CATEGORY_NAME, reverse, category_label, path),
        self.render_header("Last Modified", LABEL_CATEGORY_MTIME, reverse, category_label, path),
        self.render_header("Size", LABEL_CATEGORY_SIZE, reverse, category_label, path),
        self.render_header("Description", LABEL_CATEGORY_TYPE, reverse, category_label, path)
    ) # Breadcrumbs

        if getattr(self, common.ATTR_PATH, "/") != "/":
            htmlContent += '      <tr class="r_0"><td class="c_name"><a href="..">%s</a></td><td class="c_mod">&nbsp;</td><td class="c_size">-</td><td class="c_info">&nbsp;</td></tr>\n' % cgi.escape("<UP ONE LEVEL>")

        for item in items:

            mtime_display = '&nbsp;'
            if item.get('mtime'):
                mtime_display = datetime.datetime.fromtimestamp(item.get('mtime')).strftime('%Y-%m-%d %H:%M:%S')

            if item.get('linkname') and item.get('reachable', False):
                htmlContent += '      <tr><td class="c_name"><a href="%s">%s</a></td><td class="c_mod">%s</td><td class="c_size">%s</td><td class="c_info">%s</td></tr>\n' % (urllib.quote(item.get('linkname')), cgi.escape(item.get('displayname')), mtime_display, item.get('size_display'), item.get('extrainfo'))
            else:
                # Not reachable - dead symlink
                htmlContent += '      <tr><td class="c_name s_dead">%s</td><td class="c_mod">%s</td><td class="c_size">%s</td><td class="c_info">%s</td></tr>\n' % (cgi.escape(item.get('displayname')), mtime_display, item.get('size_display'), item.get('extrainfo'))

        htmlContent += '    <tr><td colspan="5"><hr></td></table>\n  </body>\n</html>\n'
        return self.serve_content(htmlContent)

    def render_header(self, label, target, reverse, current, path):

        get = '?%s=%s' % (LABEL_GET_CATEGORY, target)

        if target == current:
            flip_order = LABEL_ORDER_DESCENDING
            if reverse:
                flip_order = LABEL_ORDER_ASCENDING
            get = '%s&%s=%s' % (get, LABEL_GET_ORDER, flip_order)

        return '<a href="%s%s">%s</a>' % (urllib.quote(self.path), get, label)

    def send_head(self):
        """Common code for GET and HEAD commands.
        This sends the response code and MIME headers.
        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.
        """

        path = self.file_path

        if os.path.exists(path):
            # Symbolic link judgement.
            # Paths with denied symbolic links will pretend to be 404 errors.
            if args[TITLE_LOCAL_LINKS] and not ("%s/" % os.path.realpath(path)).startswith(os.getcwd() + "/"):
                return self.send_error(404, "File not found")
            elif args[TITLE_NO_LINKS]:
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
            if not getattr(self, common.ATTR_FILE_PATH, "").endswith("/"):
                return self.send_redirect("%s/" % getattr(self, common.ATTR_FILE_PATH, ""))
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        return self.serve_file(path)

if __name__ == '__main__':
    args.process(sys.argv)

    common.announce_common_arguments("Serving files")

    if args[TITLE_NO_LINKS]:
        print_notice("Ignoring all symbolic links.")

    if args[TITLE_LOCAL_LINKS]:
        print_notice("Serving only local symbolic links.")

    common.serve(SimpleHTTPVerboseReqeustHandler, True)
