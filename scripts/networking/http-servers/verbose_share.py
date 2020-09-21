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
TITLE_MAX_LENGTH = 'max-length'
TITLE_UPLOAD = 'upload'
TITLE_UPLOAD_NO_CLOBBER = 'no-clobber'

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
args.add_opt(common.OPT_TYPE_LONG_FLAG, TITLE_UPLOAD_NO_CLOBBER, TITLE_UPLOAD_NO_CLOBBER, 'Do not allow uploaded files to overwrite existing files.')
args.add_opt(common.OPT_TYPE_LONG, TITLE_MAX_LENGTH, TITLE_MAX_LENGTH, "Maximum content length.", converter = int)

args.add_validator(common.validate_common_directory)

class SimpleHTTPVerboseReqeustHandler(common.CoreHttpServer):

    server_version = "CoreHttpServer (Content Serving)"

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

    def __init__(self, request, client_address, server):
        if sys.version_info.major < 3:
            super(SimpleHTTPVerboseReqeustHandler, self).__init__(request, client_address, server)
        else:
            super().__init__(request, client_address, server)
        self.ranges_enabled = True
        if args[TITLE_UPLOAD]:
            self.do_POST = self.action_POST

    def action_POST(self):
        """
        Accept an uploaded file.

        This method is not named do_POST because it is only enabled if the upload flag (-u) is used.

        Original source is baot of StackOverflow: https://stackoverflow.com/questions/28217869/python-basehttpserver-file-upload-with-maxfile-size
        """

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

        path_save = os.path.join(self.file_path, filename)

        if os.path.exists(path_save) and not os.path.isfile(path_save):
            return self.serve_content('Destination exists as a non-file', code = 406)

        if args[TITLE_UPLOAD_NO_CLOBBER] and os.path.isfile(path_save):
            return self.serve_content('File already exists.', code = 302)

        try:
            with open(path_save, 'wb') as output_file:
                # TODO: How to handle a user lying in their Content-Length header?
                self.copyobj(form['file'].file, output_file, False)
        except IOError:
            if os.path.isfile(path_save):
                os.remove(path_save)
            return self.serve_content('Failed to save file.', code = 500)

        return self.serve_content(self.render_file_table(self.file_path), code = 200)

    def copyobj(self, src, dst, outgoing = True):
        if not src:
            return

        start, end, remaining = (0, 0, -1)
        if getattr(self, 'clip', False):
            start, end = self.ranges[0]
            remaining = end - start + 1 # Account for zero-indexing
        if start:
            src.seek(start)

        while self.alive and remaining:
            buflen = 16*1024
            if remaining > 0:
                buflen = min(remaining, buflen)

            buf = src.read(buflen)
            if not (buf and self.alive):
                break
            remaining -= len(buf)
            dst.write(common.convert_bytes(buf))

        if not outgoing:
            return

        self.alive = False
        src.close()

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

            if not getattr(self, common.ATTR_PATH, "").endswith("/"):
                return self.send_redirect("%s/" % getattr(self, common.ATTR_PATH, ""))

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

      ajax.size = file.size; // Used by 413 error response
      ajax.filename = file.name; // Used by 406 error response
      ajax.percent = 0; // Used by handleProgress
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

      setProgress();
    }

    function handleAbort(event) {
      setStatus("Upload Aborted");
      setPercent();
    }

    function handleComplete(event) {
      code = event.target.status;
      var reset = true;
      if(code == 501) {
        // For this to happen, the server would need to be restarted with upload mode not enabled.
        setStatus("Uploading is not enabled.");
      } else if(code == 500) {
        setStatus("Server error");
      } else if(code == 413) {
        setStatus("Content too large: " + event.target.responseText + event.target.size.toString());
      } else if(code == 406) {
        var filePath = window.location.pathname;
        if(!filePath.endsWith("/")) {
          filePath += "/";
        }

        setStatus("Path already used by non-file: " + filePath + event.target.filename);
      } else if(code == 404) {
        setStatus("Directory not found: " + window.location.pathname);
      } else if(code == 400) {
        setStatus("BAD REQUEST: " + event.target.responseText);
      } else if(code == 302) {
        setStatus("File already exists.")
      } else if(code == 200) {
        setStatus("Upload Complete");
        _("table").innerHTML = event.target.responseText;
        setPercent(100);
        reset = false;
      } else {
        setStatus("Unexpected Response Code: " + code.toString());
      }

      if(reset) {
        setPercent();
      }

    }

    function handleError(event) {
      _("status").innerHTML = "Upload Failed";
      setPercent();
    }

    function handleProgress(event) {
      var p = Math.round((event.loaded / event.total) * 100);
      if(p == event.target.percent) {
        return; // No new information, don't bother updating
      }
      event.target.percent = p;

      setProgress(p);
    }

    function setPercent(percent = 0) {
      _("progressBar").value = percent;
    }

    function setProgress(percent = 0) {
      var p = Math.round(percent);
      setPercent(p);
      setStatus(p + "% Uploaded...");
    }

    function setStatus(str) {
      _("status").innerHTML = str;
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

    def parse_header_range(self):

        self.ranges = []

        header_range = self.headers['Range']
        if not header_range:
            # No range provided, no need to parse further
            return True

        # Store bad-range response in a central place
        response_bad = lambda : self.send_error(400, 'Bad Request Range Header')

        p1 = r'^bytes=(\d+\-\d*|\d*-\d+)(, (\d+\-\d*|\d*-\d+))?$'
        p2 = r'^(\d+\-\d*|\d*-\d+)$'

        match = re.match(p1, header_range)
        if not match:
            return response_bad()

        groupings = [g for g in match.groups() if re.match(p2, str(g))]

        conv = lambda v, i: int(v.split('-')[i] or 0)
        ranges = sorted([[conv(g, 0), conv(g, 1)] for g in groupings], key=lambda a: a[0])

        for r in ranges:
            start = r[0]
            end = r[1]

            if not end and not start:
                # Request for '0-0' (that is to say, the entire thing)
                # Chrome does this for video files, for instance
                continue

            if end == start or end and end < start:
                return response_bad()

        ranges_b = [ranges[0]]

        for r in ranges[1:]:
            start = r[0]
            end = r[1]

            if not start:
                # No non-first range may start at 0.
                return response_bad()

            if not ranges_b[-1][1]:
                # No non-last ranges may end at 0.
                return response_bad()

            if start - 1 == ranges_b[-1][1]:
                # If multiple neighboring ranges are given, then merge them together
                ranges_b[-1][1] = end
                continue

            if start <= ranges_b[-1][1]:
                # Ranges may not overlap
                return response_bad()

            ranges_b.append([start, end])

        self.ranges = [(r[0], r[1]) for r in ranges_b]

        if len(self.ranges) >= 2:
            # The script currently does not support handling multiple ranges
            return self.send_error(501, "Multiple ranges not supported" % self.command)

        return True

    def render_header(self, label, target, reverse, current, path):

        get = '?%s=%s' % (LABEL_GET_CATEGORY, target)

        if target == current:
            flip_order = LABEL_ORDER_DESCENDING
            if reverse:
                flip_order = LABEL_ORDER_ASCENDING
            get = '%s&%s=%s' % (get, LABEL_GET_ORDER, flip_order)

        return '<a href="%s%s">%s</a>' % (quote(self.path), get, label)

    def serve_content(self, content = None, code = 200, mimetype = "text/html"):

        f, length = self.serve_content_prepare(content)

        if self.ranges:

            start, end = self.ranges[0]
            if end >= length:
                return self.send_error(416)

            if code == 200:
                # Clip 200 content, not error content
                code = 206
                self.clip = True
                length_total = length
                length = end - start + 1 # Account for zero-indexing

        self.send_response(code)
        self.send_common_headers(mimetype, length)
        self.send_header('Accept-Ranges', 'bytes')
        if getattr(self, 'clip', False):

            display_values = {
                'start': start,
                'end': length-1,
                'total': length_total
            }
            if end:
                display_values['end'] = end

            self.send_header('Content-Range', 'bytes %(start)d-%(end)d/%(total)d' % display_values)

        self.end_headers()
        return f

    def serve_file(self, path):

        if not (os.path.exists(path) and os.path.isfile(path)):
            return self.send_error(404, 'Not Found')

        ctype = self.guess_type(path)
        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            f = open(path, 'rb')
            fs = os.fstat(f.fileno())
            length = fs[6]
            if self.ranges:
                start, end = self.ranges[0]

                if end >= length:
                    return self.send_error(416)

                self.clip = True
                length_total = length
                length = end - start + 1 # Account for zero-indexing
        except IOError:
            return self.send_error(404, 'Not Found')

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))

        if getattr(self, 'clip', False):

            display_values = {
                'start': start,
                'end': length-1,
                'total': length_total
            }
            if end:
                display_values['end'] = end

            self.send_header('Content-Range', 'bytes %(start)d-%(end)d/%(total)d' % display_values)
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

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
            print_notice('Maximum content length: %s' % common.colour_text('%sB' % args[TITLE_MAX_LENGTH]))

        if args[TITLE_UPLOAD_NO_CLOBBER]:
            print_notice('Uploads will %s be able to overwrite each other.' % common.colour_text('NOT'))
        else:
            common.print_warning('Uploads will be able to overwrite each other.')

    common.serve(SimpleHTTPVerboseReqeustHandler, True)
