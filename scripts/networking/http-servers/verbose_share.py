#!/usr/bin/env python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

import cgi, datetime, getopt, os, re, socket, sys, urllib
import CoreHttpServer as common
from CoreHttpServer import args, print_notice
common.local_files.append(os.path.realpath(__file__))

# Specific to browser sharer

if sys.version_info[0] == 2:
    from cgi import escape
    from urllib import quote
    from urlparse import unquote
else:
    from html import escape
    from urllib.parse import quote, unquote

# Script Content

DEFAULT_REVERSE = False
DEFAULT_TIMESORT = False

TITLE_NO_LINKS = "nolinks"
TITLE_LOCAL_LINKS = "locallinks"
TITLE_UPLOAD = 'upload'
TITLE_MAX_LENGTH = 'max-length'

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
args.add_opt(common.OPT_TYPE_FLAG, 'u', TITLE_UPLOAD, 'Enable uploading of files.')
args.add_opt(common.OPT_TYPE_LONG, TITLE_MAX_LENGTH, TITLE_MAX_LENGTH, "Maximum content length.", converter = int)

args.add_validator(common.validate_common_directory)

class SimpleHTTPVerboseReqeustHandler(common.CoreHttpServer):

    server_version = "CoreHttpServer (Content Serving)"

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)
        if args[TITLE_UPLOAD]:
            self.do_POST = self.action_POST

    def action_POST(self):

        # Use the content-length header, though being user-defined input it's not really trustworthy.
        try:
            l = int(self.headers.get('content-length', 0))
            if l < 0:
                # Parsed properly, but some joker put in a negative number.
                raise ValueError()
        except ValueError:
            return self.serve_content("Illegal Content-Length header value: %s" % self.headers.get('content-length', 0), 400)

        m = args[TITLE_MAX_LENGTH]
        if m and l > m:
            return self.serve_content('Maximum length: %d' % m, code = 413)

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                'REQUEST_METHOD':'POST',
                'CONTENT_TYPE':self.headers['Content-Type'],
            }
        )

        if 'file' not in form:
            return self.serve_content('No file provided.', 400)

        filename = form['file'].filename
        if not filename:
            # No FileName provided
            return self.serve_content('No file name.', 400)
        elif not re.match(r"^[\w\-. _\?]+$", filename) or filename in ['.', '..']:
            # Validate filename
            return self.serve_content('Invalid file name.', 400)

        if not os.path.isdir(self.file_path):
            return self.send_error(404)

        with open(os.path.join(self.file_path, filename), 'wb') as output_file:
            # TODO: How to handle a user lying in their Content-Length header?
            self.copyobj(form['file'].file, output_file, False)

        return self.serve_content(self.render_file_table(self.file_path), code = 200)

    def do_GET(self):
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

            for index in ["index.html", "index.htm"]:
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            if path == self.file_path:
                return self.list_directory(path)

        return self.serve_file(path)

    def humansize(self, nbytes):
        if nbytes == 0: return '0B'
        i = 0
        while nbytes >= 1000 and i < len(self.suffixes)-1:
            nbytes /= 1000.
            i += 1
        f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
        return '%s%s' % (f, self.suffixes[i])

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).
        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().
        """

        table_content = self.render_file_table(path)
        if not table_content:
            # Intentionally keeping the reason for this vague.
            # Could be due to a not-found file or a permissions problem.
            self.send_error(404, "Unable to list directory")
            return None

        displaypath = escape(unquote(getattr(self, common.ATTR_PATH, "/")))

        uploadContent = ''
        if args[TITLE_UPLOAD]:
            uploadContent = """
    <script>
    // Script source: https://codepen.io/PerfectIsShit/pen/zogMXP

    function _(el) {
      return document.getElementById(el);
    }

    function uploadFile() {
      var file = _("file").files[0];
      var formdata = new FormData();
      formdata.append("file", file);
      var ajax = new XMLHttpRequest();

      ajax.size = file.size;
      ajax.upload.addEventListener("progress", handleProgress, false);
      ajax.addEventListener("load", handleComplete, false);
      ajax.addEventListener("error", handleError, false);
      ajax.addEventListener("abort", handleAbort, false);

      var url = window.location.pathname;
      var urlParams = new URLSearchParams(window.location.search).toString();
      if(urlParams != "") {
        url += "?" + urlParams;
      }

      ajax.open("POST", url);
      ajax.send(formdata);

      _("status").innerHTML = "Upload Started";
      _("progressBar").value = 0;
    }

    function handleAbort(event) {
      _("status").innerHTML = "Upload Aborted";
      _("progressBar").value = 0;
    }

    function handleComplete(event) {
      code = event.target.status;
      var reset = true;
      if(code == 501) {
        _("status").innerHTML = "Uploading is not enabled.";
      } else if(code == 500) {
        _("status").innerHTML = "Server error";
      } else if(code == 413) {
        _("status").innerHTML = "Content too large: " + event.target.responseText + event.target.size.toString();
      } else if(code == 404) {
        _("status").innerHTML = "Directory not found: " + window.location.pathname;
      } else if(code == 400) {
        _("status").innerHTML = "BAD REQUEST: " + event.target.responseText;
      } else if(code == 200) {
        _("status").innerHTML = "Upload Complete";
        _("table").innerHTML = event.target.responseText;
        _("progressBar").value = 100;
        reset = false;
      } else {
        _("status").innerHTML = "Unexpected Response Code: " + code.toString();
      }

      if(reset) {
        _("progressBar").value = 0;
      }

    }

    function handleError(event) {
      _("status").innerHTML = "Upload Failed";
      _("progressBar").value = 0;
    }

    function handleProgress(event) {
      _("loaded_n_total").innerHTML = "Uploaded " + event.loaded + " bytes of " + event.total;
      var percent = (event.loaded / event.total) * 100;
      _("progressBar").value = Math.round(percent);
      _("status").innerHTML = Math.round(percent) + "% Uploaded...";
    }

    </script>
      <form id="upload_form" enctype="multipart/form-data" method="post">
      <input type="file" name="file" id="file" onchange="uploadFile()"><br>
      <progress id="progressBar" value="0" max="100" style="width:350px;"></progress>
      <p id="status">&nbsp;</p>
    </form>
"""

        htmlContent = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
  <head>
    <title>Directory listing for %s (%s)</title>
    <style>
      body { font-family: "Poppins", "Roboto", Sans-serif; padding: 25px; }
      table { border-collapse: collapse; }
      th { text-align: left; }
      tr.hover-row:hover { background-color: rgba(0,0,0,.075); }
      td { vertical-align: text-top; padding: 5px 0px; margin: 0px; }
      tr td { border-top: 1px solid #dee2e6; }
      h2 { color: #555; font-size: 22px; font-weight: 600; margin: 0; line-height: 1.2; margin-bottom: 25px; }
      a { text-decoration: none; }
      .c_name { min-width: 300px; padding-left: 25px; }
      .c_mod { align: right; padding: 5px 20px; min-width: 175px; }
      .c_size { align: right; padding: 5px 10px 5px 20px; min-width: 125px; }
      .c_info { align: right; min-width: 175px; }
      .s_dead { color: #821e00; }
      .path { font-weight: bold; }
    </style>
  </head>
  <body>
    <h2>Directory: %s</h2>%s
    <div id="table">
        %s
    </div>
  </body>
</html>
""" % (displaypath, self.base_directory, # Title
        self.render_breadcrumbs(displaypath),
        uploadContent,
        table_content
    )

        return self.serve_content(htmlContent)

    def render_file_table(self, path):

        try:
            fileNames = os.listdir(path)
        except os.error:
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

                    extrainfo = "Symlink to directory <span class='path'>%s</span>" % escape(os.path.realpath(fullname))
                elif os.path.isfile(os.path.realpath(fullname)):
                    # File via Symlink
                    extrainfo = "Symlink to %s file <span class='path'>%s</span>" % (self.humansize(os.stat(fullname).st_size), escape(os.path.realpath(fullname)))
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

        content = """<table>
        <tr><th class="c_name">%s</th><th class="c_size">%s</th><th class="c_mod">%s</th><th class="c_info">%s</th></tr>
        """ % (
            self.render_header("Name", LABEL_CATEGORY_NAME, reverse, category_label, path),
            self.render_header("Size", LABEL_CATEGORY_SIZE, reverse, category_label, path),
            self.render_header("Last Modified", LABEL_CATEGORY_MTIME, reverse, category_label, path),
            self.render_header("Description", LABEL_CATEGORY_TYPE, reverse, category_label, path)
        )

        if getattr(self, common.ATTR_PATH, "/") != "/":
            content += '      <tr class="hover-row"><td class="c_name"><a href="..">%s</a></td><td class="c_size">-</td><td class="c_mod">&nbsp;</td><td class="c_info">&nbsp;</td></tr>\n' % escape("<UP ONE LEVEL>")

        for item in items:

            mtime_display = '&nbsp;'
            if item.get('mtime'):
                mtime_display = datetime.datetime.fromtimestamp(item.get('mtime')).strftime('%Y-%m-%d %H:%M:%S')

            if item.get('linkname') and item.get('reachable', False):
                parts = (quote(item.get('linkname')), escape(item.get('displayname')), item.get('size_display'), mtime_display, item.get('extrainfo'))
                content += '      <tr class="hover-row"><td class="c_name"><a href="%s">%s</a></td><td class="c_size">%s</td><td class="c_mod">%s</td><td class="c_info">%s</td></tr>\n' % parts
            else:
                # Not reachable - dead symlink
                parts = (escape(item.get('displayname')), item.get('size_display'), mtime_display, item.get('extrainfo'))
                content += '      <tr class="hover-row"><td class="c_name s_dead">%s</td><td class="c_size">%s</td><td class="c_mod">%s</td><td class="c_info">%s</td></tr>\n' % parts

        content += """
        <tr><td colspan="5"></td></table>
        """

        return content

    def render_header(self, label, target, reverse, current, path):

        get = '?%s=%s' % (LABEL_GET_CATEGORY, target)

        if target == current:
            flip_order = LABEL_ORDER_DESCENDING
            if reverse:
                flip_order = LABEL_ORDER_ASCENDING
            get = '%s&%s=%s' % (get, LABEL_GET_ORDER, flip_order)

        return '<a href="%s%s">%s</a>' % (quote(self.path), get, label)

if __name__ == '__main__':
    args.process(sys.argv)

    common.announce_common_arguments("Serving files")

    if args[TITLE_NO_LINKS]:
        print_notice("Ignoring all symbolic links.")

    if args[TITLE_LOCAL_LINKS]:
        print_notice("Serving only local symbolic links.")

    if args[TITLE_UPLOAD]:
        common.print_warning('Uploading is enabled.')

        if args[TITLE_MAX_LENGTH]:
            common.print_notice('Maximum content length: %s' % common.colour_text('%sB' % args[TITLE_MAX_LENGTH]))

    common.serve(SimpleHTTPVerboseReqeustHandler, True)
