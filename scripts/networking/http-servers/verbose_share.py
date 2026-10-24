#!/usr/bin/env python

# Based off of (via StackExchange):
#   * https://pymotw.com/2/BaseHTTPServer/index.html#module-BaseHTTPServer
#   * https://docs.python.org/2/library/simplehttpserver.html

import datetime, errno, getopt, os, random, re, socket, sys, tempfile, urllib
import CoreHttpServer as common
from CoreHttpServer import args, display_name, print_notice, quote_path

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

TITLE_MAX_LENGTH = 'max-length'
TITLE_UPLOAD = 'upload'
TITLE_UPLOAD_NO_CLOBBER = 'no-clobber'

# In-progress uploads are written to '.<name>.upload-<8 hex chars>' beside
#   their destination. Listings skip anything matching this.
UPLOAD_TEMP_SUFFIX = '.upload-'
UPLOAD_TEMP_PATTERN = re.compile(r'\.upload-[0-9a-f]{8}\Z')

# os.link() failures that mean the filesystem has no hard links (for example
#   FAT/exFAT, some FUSE and SMB mounts), as opposed to a real conflict.
LINK_UNSUPPORTED_ERRNOS = set(
    getattr(errno, n)
    for n in ('EPERM', 'EOPNOTSUPP', 'ENOTSUP', 'ENOSYS')
    if hasattr(errno, n)
)

# os.replace() is Python 3 only. os.rename() overwrites the same way on POSIX.
replace_file = getattr(os, 'replace', os.rename)

LABEL_GET_CATEGORY = 'C'
LABEL_GET_ORDER = 'O'

LABEL_ORDER_DESCENDING = 'D'
LABEL_ORDER_ASCENDING = 'A'

LABEL_CATEGORY_NAME = 'N'
LABEL_CATEGORY_MTIME = 'M'
LABEL_CATEGORY_SIZE = 'S'
LABEL_CATEGORY_TYPE = 'T'

# Define arguments

common.add_link_arguments()

args.add_validator(common.validate_common_directory)


def add_upload_arguments():
    # Opt-in, so that scripts reusing this handler do not inherit upload options.
    args.add_opt(common.OPT_TYPE_FLAG, 'u', TITLE_UPLOAD, 'Enable uploading of files.')
    args.add_opt(
        common.OPT_TYPE_LONG_FLAG,
        TITLE_UPLOAD_NO_CLOBBER,
        TITLE_UPLOAD_NO_CLOBBER,
        'Do not allow uploaded files to overwrite existing files.',
    )
    args.add_opt(
        common.OPT_TYPE_LONG,
        TITLE_MAX_LENGTH,
        TITLE_MAX_LENGTH,
        "Maximum content length of an upload in bytes.",
        converter=int,
    )


def upload_temp_token():
    return '%08x' % random.SystemRandom().getrandbits(32)


def decode_part_header(line):
    # Python 2 keeps the raw bytes, matching its byte-string paths.
    if sys.version_info[0] >= 3:
        return line.decode('utf-8', 'surrogateescape')
    return line


def fs_length(name):
    """Length of a native-string path in bytes, as the filesystem counts it."""
    if sys.version_info[0] >= 3:
        return len(os.fsencode(name))
    return len(name)


def path_limit(path, name, default):
    try:
        return os.pathconf(path, name)
    except (OSError, ValueError, AttributeError):
        return default


def supports_hard_links(directory):
    """Probe whether directory supports hard links.

    Returns None when it cannot tell (for example a read-only directory).

    This only checks the top of the shared directory. A different filesystem
    mounted somewhere inside it could still lack hard links, but finding
    every such mount definitively does not seem worth the trouble, and
    uploads fall back safely there anyway."""
    token = upload_temp_token()
    source = os.path.join(directory, '.link-probe%s%s' % (UPLOAD_TEMP_SUFFIX, token))
    target = os.path.join(directory, '.link-probe-b%s%s' % (UPLOAD_TEMP_SUFFIX, token))
    try:
        os.close(os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except (IOError, OSError):
        return None
    try:
        os.link(source, target)
        os.remove(target)
        return True
    except (IOError, OSError) as e:
        if e.errno in LINK_UNSUPPORTED_ERRNOS:
            return False
        return None
    finally:
        os.remove(source)


class BoundedReader(object):
    """Read at most a fixed number of bytes from a stream, with push-back."""

    def __init__(self, src, remaining):
        self.src = src
        self.remaining = remaining
        self.pending = b''

    def read(self, size):
        if self.pending:
            data, self.pending = self.pending[:size], self.pending[size:]
            return data
        data = self.src.read(min(size, self.remaining)) if self.remaining else b''
        self.remaining -= len(data)
        return data

    def readline(self, limit=65536):
        line = b''
        while len(line) < limit and not line.endswith(b'\n'):
            data = self.read(1024)
            if not data:
                break
            i = data.find(b'\n')
            if i >= 0:
                self.unread(data[i + 1 :])
                data = data[: i + 1]
            line += data
        return line

    def unread(self, data):
        self.pending = data + self.pending


def copy_until(reader, dst, marker):
    """Copy from reader to dst (None discards) up to marker, consuming the marker.

    Returns False if the stream ended before the marker was seen."""
    keep = len(marker) - 1
    buf = b''
    while True:
        data = reader.read(64 * 1024)
        buf += data
        i = buf.find(marker)
        if i >= 0:
            if dst:
                dst.write(buf[:i])
            reader.unread(buf[i + len(marker) :])
            return True
        if not data:
            return False
        if len(buf) > keep:
            if dst:
                dst.write(buf[:-keep])
            buf = buf[-keep:]


class SimpleHTTPVerboseReqeustHandler(common.CoreHttpServer):

    server_version = "CoreHttpServer (Content Serving)"

    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

    # Set per request by parse_header_range() and serve_*().
    ranges = []
    clip = None

    def __init__(self, request, client_address, server):
        if sys.version_info.major < 3:
            super(SimpleHTTPVerboseReqeustHandler, self).__init__(
                request, client_address, server
            )
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

        # The body is never read past Content-Length, so a missing header would
        #   otherwise mean an unbounded read that --max-length cannot police.
        raw_length = self.headers.get('content-length', '')
        if not raw_length:
            return self.serve_content('Content-Length required.', 411)
        try:
            l = int(raw_length)
            if l < 0:
                # Parsed properly, but some joker put in a negative number.
                raise ValueError()
        except ValueError:
            return self.serve_content(
                "Illegal Content-Length header value: %s" % escape(raw_length),
                400,
            )

        m = args[TITLE_MAX_LENGTH]
        if m and l > m:
            return self.serve_content('Maximum length: %d' % m, code=413)

        if not (os.path.isdir(self.file_path) and common.path_allowed(self.file_path)):
            return self.send_error(404)

        match = re.search(r'boundary="?([^";]+)"?', self.headers['Content-Type'])
        if not match:
            return self.serve_content('Expected multipart/form-data.', 400)

        reader = BoundedReader(self.rfile, l)
        delimiter = b'--' + match.group(1).strip().encode('latin-1')

        # Skip the preamble up to the first delimiter.
        line = reader.readline()
        while line and line.rstrip(b'\r\n') != delimiter:
            line = reader.readline()

        while line:
            part_headers = {}
            line = reader.readline()
            while line not in (b'\r\n', b'\n', b''):
                key, _, value = decode_part_header(line).partition(':')
                part_headers[key.strip().lower()] = value.strip()
                line = reader.readline()

            disposition = part_headers.get('content-disposition', '')
            name = re.search(r'(?:^|;)\s*name="([^"]*)"', disposition)
            if name and name.group(1) == 'file':
                filename = re.search(r'(?:^|;)\s*filename="([^"]*)"', disposition)
                return self.receive_file(
                    reader, delimiter, filename.group(1) if filename else None
                )

            # Not the file field, discard its content.
            if not copy_until(reader, None, b'\r\n' + delimiter):
                break
            line = reader.readline()
            if line.startswith(b'--'):
                # Closing delimiter
                break

        return self.serve_content('No file provided.', 400)

    def receive_file(self, reader, delimiter, filename):

        if not filename:
            # No FileName provided
            return self.serve_content('No file name.', 400)
        elif not re.match(r'^[^/\\\0\r\n]+\Z', filename) or filename in ['.', '..']:
            # Validate filename
            return self.serve_content('Invalid file name.', 400)

        # The temporary name is the longest name written, so check it up front.
        #   This keeps an over-long name a 400 instead of a 500 from open().
        #   The upload temp name adds 17 bytes, so the usable limit is that much
        #   lower than the filesystem's own.
        name_temp = '.%s%s%s' % (filename, UPLOAD_TEMP_SUFFIX, upload_temp_token())
        path_temp = os.path.join(self.file_path, name_temp)
        if fs_length(name_temp) > path_limit(
            self.file_path, 'PC_NAME_MAX', 255
        ) or fs_length(path_temp) >= path_limit(self.file_path, 'PC_PATH_MAX', 4096):
            return self.serve_content('File name too long.', 400)

        path_save = os.path.join(self.file_path, filename)

        if os.path.islink(path_save) or (
            os.path.exists(path_save) and not os.path.isfile(path_save)
        ):
            # Refuse to write through a symbolic link, wherever it points.
            return self.serve_content('Destination exists as a non-file', code=406)

        if args[TITLE_UPLOAD_NO_CLOBBER] and os.path.lexists(path_save):
            return self.serve_content('File already exists.', code=409)

        if os.path.exists(path_save) and not os.access(path_save, os.W_OK):
            return self.serve_content('Destination is not writable.', code=403)

        # Write to a temporary sibling and move it into place, so that a failed
        #   or truncated upload never damages an existing file.
        try:
            fd = os.open(path_temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            with os.fdopen(fd, 'wb') as output_file:
                complete = copy_until(reader, output_file, b'\r\n' + delimiter)
            if not complete:
                os.remove(path_temp)
                return self.serve_content('Upload was truncated.', code=400)
            if args[TITLE_UPLOAD_NO_CLOBBER]:
                self.publish_no_clobber(path_temp, path_save)
            else:
                replace_file(path_temp, path_save)
        except (IOError, OSError) as e:
            if os.path.lexists(path_temp):
                os.remove(path_temp)
            if getattr(e, 'errno', None) == errno.EEXIST:
                return self.serve_content('File already exists.', code=409)
            return self.serve_content('Failed to save file.', code=500)

        return self.serve_content(self.render_file_table(self.file_path), code=200)

    def publish_no_clobber(self, path_temp, path_save):
        """Move a finished upload into place only if the name is still free.

        Raises OSError with EEXIST if the name was claimed since it was checked."""
        try:
            # link() refuses an existing name, and the content is already complete.
            os.link(path_temp, path_save)
        except OSError as e:
            if e.errno not in LINK_UNSUPPORTED_ERRNOS:
                raise
            # No hard links here. Claim the name with an empty placeholder
            #   (O_EXCL is atomic everywhere), then move the upload over it.
            #   Only our own placeholder is ever replaced.
            os.close(os.open(path_save, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666))
            try:
                replace_file(path_temp, path_save)
            except (IOError, OSError):
                os.remove(path_save)
                raise
        else:
            os.remove(path_temp)

    def copyobj(self, src, dst, outgoing=True):
        if not src:
            return

        start, end, remaining = (0, 0, -1)
        if outgoing and getattr(self, 'clip', None):
            start, end = self.clip
            remaining = end - start + 1  # Account for zero-indexing
        if start:
            src.seek(start)

        while self.alive and remaining:
            buflen = 16 * 1024
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

        # Symbolic link judgement.
        # Paths with denied symbolic links will pretend to be 404 errors.
        if os.path.exists(path) and not common.path_allowed(path):
            return self.send_error(404, "File not found")

        f = None
        if os.path.isdir(path):

            if not getattr(self, common.ATTR_PATH, "").endswith("/"):
                # Quote so that the Location header is ASCII and cannot carry CR/LF,
                #   and keep the query so that sort order survives the redirect.
                target = quote_path("%s/" % getattr(self, common.ATTR_PATH, ""))
                query = self.raw_query()
                if query:
                    target += '?' + query
                return self.send_redirect(target)

            for index in ["index.html", "index.htm"]:
                index = os.path.join(path, index)
                if os.path.isfile(index) and common.path_allowed(index):
                    path = index
                    break
            if path == self.file_path:
                return self.list_directory(path)

        return self.serve_file(path)

    def do_HEAD(self):
        """Same headers as GET, no body."""
        f = self.do_GET()
        if f:
            f.close()
        return None

    def raw_query(self):
        """Query string exactly as the client sent it."""
        words = self.requestline.split()
        if len(words) < 2 or '?' not in words[1]:
            return ''
        return words[1].split('?', 1)[1].split('#', 1)[0]

    def humansize(self, nbytes):
        if nbytes == 0:
            return '0B'
        i = 0
        while nbytes >= 1000 and i < len(self.suffixes) - 1:
            nbytes /= 1000.0
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

        # self.path is already unquoted by parse_path().
        rawpath = getattr(self, common.ATTR_PATH, "/")
        displaypath = escape(display_name(rawpath))

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
      } else if(code == 409) {
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
""" % (
            displaypath,
            escape(self.base_directory),  # Title
            self.render_breadcrumbs(rawpath),
            uploadContent,
            table_content,
        )

        return self.serve_content(htmlContent)

    def render_file_table(self, path):

        try:
            fileNames = os.listdir(path)
        except os.error:
            return None

        items = []
        for name in fileNames:

            if UPLOAD_TEMP_PATTERN.search(name):
                # In-progress (or abandoned) upload
                continue

            fullname = os.path.join(path, name)
            displayname = display_name(name)
            linkname = name
            extrainfo = ''
            reachable = True
            size = 0
            size_display = '-'
            obj_type = 'File'
            mtime = 0.0
            is_file = False

            if os.path.islink(fullname):

                # Note: a link to a directory displays with @ and links with /
                displayname += "@"
                reachable = common.link_allowed(fullname)
                obj_type = 'Sym'

                if not reachable:
                    # Symbolic link is inaccessible. Override extra info to plainly say 'symlink'.
                    if args[common.TITLE_NO_LINKS]:
                        extrainfo = "(Symlink)"
                    else:
                        # Implies local links only, meaning an unreachable link is external.
                        extrainfo = "(External Symlink)"
                elif os.path.isdir(os.path.realpath(fullname)):
                    # Directory via Symlink
                    # Append / for directories or @ for symbolic links
                    displayname = display_name(name) + "/@"
                    linkname = name + "/"

                    extrainfo = (
                        "Symlink to directory <span class='path'>%s</span>"
                        % escape(display_name(os.path.realpath(fullname)))
                    )
                elif os.path.isfile(os.path.realpath(fullname)):
                    # File via Symlink
                    extrainfo = "Symlink to %s file <span class='path'>%s</span>" % (
                        self.humansize(os.stat(fullname).st_size),
                        escape(display_name(os.path.realpath(fullname))),
                    )
                    is_file = True
                else:
                    # Dead symlink
                    linkname = None
                    extrainfo = "Dead symlink to <span class='path'>%s</span>" % escape(
                        display_name(os.readlink(fullname))
                    )

            elif os.path.isdir(fullname):
                # Directory
                displayname += "/"
                linkname = name + "/"
                obj_type += 'Dir'
            else:
                # File
                is_file = True

            if reachable and is_file:
                try:
                    st = os.stat(fullname)
                    size = st.st_size
                    size_display = self.humansize(size)
                    mtime = st.st_mtime
                except OSError:
                    # Removed or made inaccessible since listdir().
                    pass

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

        category_label = next(
            iter(reversed(self.get.get(LABEL_GET_CATEGORY, []))), default_category_label
        ).upper()
        if category_label not in (
            LABEL_CATEGORY_NAME,
            LABEL_CATEGORY_MTIME,
            LABEL_CATEGORY_SIZE,
            LABEL_CATEGORY_TYPE,
        ):
            category_label = default_category_label

        order_label = next(
            iter(reversed(self.get.get(LABEL_GET_ORDER, []))), default_order_label
        ).upper()
        if order_label not in (LABEL_ORDER_ASCENDING, LABEL_ORDER_DESCENDING):
            order_label = default_order_label

        reverse = False
        if order_label == LABEL_ORDER_DESCENDING:
            reverse = True

        if category_label == LABEL_CATEGORY_MTIME:
            items.sort(
                key=lambda a: (a['mtime'], a['rawname'].lower()), reverse=reverse
            )
        elif category_label == LABEL_CATEGORY_SIZE:
            items.sort(key=lambda a: (a['size'], a['rawname'].lower()), reverse=reverse)
        elif category_label == LABEL_CATEGORY_TYPE:
            items.sort(key=lambda a: (a['type'], a['rawname'].lower()), reverse=reverse)
        else:
            items.sort(key=lambda a: a['rawname'].lower(), reverse=reverse)

        content = """<table>
        <tr><th class="c_name">%s</th><th class="c_size">%s</th><th class="c_mod">%s</th><th class="c_info">%s</th></tr>
        """ % (
            self.render_header(
                "Name", LABEL_CATEGORY_NAME, reverse, category_label, path
            ),
            self.render_header(
                "Size", LABEL_CATEGORY_SIZE, reverse, category_label, path
            ),
            self.render_header(
                "Last Modified", LABEL_CATEGORY_MTIME, reverse, category_label, path
            ),
            self.render_header(
                "Description", LABEL_CATEGORY_TYPE, reverse, category_label, path
            ),
        )

        if getattr(self, common.ATTR_PATH, "/") != "/":
            content += (
                '      <tr class="hover-row"><td class="c_name"><a href="..">%s</a></td><td class="c_size">-</td><td class="c_mod">&nbsp;</td><td class="c_info">&nbsp;</td></tr>\n'
                % escape("<UP ONE LEVEL>")
            )

        for item in items:

            mtime_display = '&nbsp;'
            if item.get('mtime'):
                mtime_display = datetime.datetime.fromtimestamp(
                    item.get('mtime')
                ).strftime('%Y-%m-%d %H:%M:%S')

            if item.get('linkname') and item.get('reachable', False):
                parts = (
                    quote_path(item.get('linkname')),
                    escape(item.get('displayname')),
                    item.get('size_display'),
                    mtime_display,
                    item.get('extrainfo'),
                )
                content += (
                    '      <tr class="hover-row"><td class="c_name"><a href="%s">%s</a></td><td class="c_size">%s</td><td class="c_mod">%s</td><td class="c_info">%s</td></tr>\n'
                    % parts
                )
            else:
                # Not reachable - dead symlink
                parts = (
                    escape(item.get('displayname')),
                    item.get('size_display'),
                    mtime_display,
                    item.get('extrainfo'),
                )
                content += (
                    '      <tr class="hover-row"><td class="c_name s_dead">%s</td><td class="c_size">%s</td><td class="c_mod">%s</td><td class="c_info">%s</td></tr>\n'
                    % parts
                )

        content += """
        <tr><td colspan="5"></td></table>
        """

        return content

    def parse_header_range(self):
        """Read a single byte range from the Range header into self.ranges.

        Entries are (first, last) with None for an omitted value, so that
        open-ended ("500-") and suffix ("-500") forms can be resolved against
        the content length later. Anything this script does not handle
        (other units, syntax errors, multiple ranges) is ignored, which
        RFC 9110 allows: the full content is served with a 200.
        """

        self.ranges = []
        self.clip = None

        header_range = self.headers['Range']
        if not header_range:
            # No range provided, no need to parse further
            return True

        unit, _, spec = header_range.partition('=')
        if unit.strip().lower() != 'bytes':
            return True

        specs = [s.strip() for s in spec.split(',') if s.strip()]
        if len(specs) != 1:
            # Multiple ranges are not supported, fall back to the full content.
            return True

        match = re.match(r'^(\d*)-(\d*)$', specs[0])
        if not match or not (match.group(1) or match.group(2)):
            return True

        first = int(match.group(1)) if match.group(1) else None
        last = int(match.group(2)) if match.group(2) else None
        if first is not None and last is not None and last < first:
            # Invalid range-spec, ignore the header.
            return True

        self.ranges = [(first, last)]
        return True

    def resolve_range(self, length):
        """Turn self.ranges[0] into absolute (start, end) for content of length bytes.

        Returns None when the range cannot be satisfied."""
        first, last = self.ranges[0]
        if first is None:
            # Suffix range: the final <last> bytes.
            if not last or not length:
                return None
            return (max(0, length - last), length - 1)
        if first >= length:
            return None
        if last is None or last >= length:
            last = length - 1
        return (first, last)

    def send_range_unsatisfiable(self, length):
        self.send_response(416)
        self.send_header('Content-Range', 'bytes */%d' % length)
        self.send_header('Content-Length', '0')
        self.end_headers()
        return None

    def render_header(self, label, target, reverse, current, path):

        get = '?%s=%s' % (LABEL_GET_CATEGORY, target)

        if target == current:
            flip_order = LABEL_ORDER_DESCENDING
            if reverse:
                flip_order = LABEL_ORDER_ASCENDING
            get = '%s&%s=%s' % (get, LABEL_GET_ORDER, flip_order)

        return '<a href="%s%s">%s</a>' % (
            quote_path(self.path),
            get,
            label,
        )

    def serve_content(self, content=None, code=200, mimetype="text/html"):

        f, length = self.serve_content_prepare(content)

        length_total = length
        if self.ranges and code == 200:
            # Clip 200 content, not error content
            self.clip = self.resolve_range(length)
            if not self.clip:
                return self.send_range_unsatisfiable(length)
            code = 206
            length = self.clip[1] - self.clip[0] + 1  # Account for zero-indexing

        self.send_response(code)
        self.send_common_headers(mimetype, length)
        self.send_header('Accept-Ranges', 'bytes')
        if self.clip:
            self.send_header(
                'Content-Range', 'bytes %d-%d/%d' % (self.clip + (length_total,))
            )

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
        except IOError:
            return self.send_error(404, 'Not Found')

        fs = os.fstat(f.fileno())
        length_total = length = fs.st_size
        code = 200
        if self.ranges:
            self.clip = self.resolve_range(length)
            if not self.clip:
                f.close()
                return self.send_range_unsatisfiable(length)
            code = 206
            length = self.clip[1] - self.clip[0] + 1  # Account for zero-indexing

        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header('Accept-Ranges', 'bytes')
        if self.clip:
            self.send_header(
                'Content-Range', 'bytes %d-%d/%d' % (self.clip + (length_total,))
            )
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f


if __name__ == '__main__':
    add_upload_arguments()
    args.process(sys.argv)

    common.announce_common_arguments("Serving files")
    common.announce_link_arguments()

    if args[TITLE_UPLOAD]:
        common.print_warning('Uploading is enabled.')

        if args[TITLE_MAX_LENGTH]:
            print_notice(
                'Maximum content length: %s'
                % common.colour_text('%sB' % args[TITLE_MAX_LENGTH])
            )

        if args[TITLE_UPLOAD_NO_CLOBBER]:
            print_notice(
                'Uploads will %s be able to overwrite each other.'
                % common.colour_text('NOT')
            )
            if supports_hard_links(common.get_target()) is False:
                common.print_warning(
                    'Shared directory does not support hard links. Uploads will '
                    'briefly show an empty placeholder file while being moved into place.'
                )
        else:
            common.print_warning('Uploads will be able to overwrite each other.')

    common.serve(SimpleHTTPVerboseReqeustHandler, True)
