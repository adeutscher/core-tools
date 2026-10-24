#!/usr/bin/env python

import CoreHttpServer as common
import getopt, mmap, os, re, shutil, socket, sys
from socket import error as SocketError

if sys.version_info[0] == 2:
    from httplib import HTTPException
    from urllib2 import build_opener, HTTPErrorProcessor, quote, Request, URLError
    from urlparse import urlsplit
else:
    from http.client import HTTPException
    from urllib.request import build_opener, HTTPErrorProcessor, Request
    from urllib.error import URLError
    from urllib.parse import quote, urlsplit

TITLE_TARGET = "proxy target"
TITLE_MAX_LENGTH = "max-length"
common.local_files.append(os.path.realpath(__file__))

common.args.add_opt(
    common.OPT_TYPE_LONG,
    TITLE_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    converter=int,
    description="Maximum content length.",
)

# Headers that describe one connection rather than the message (RFC 9110 7.6.1),
#   so they are never relayed in either direction. Headers named in a
#   Connection header are dropped as well.
HOP_BY_HOP = (
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'proxy-connection',
    'te',
    'trailer',
    'transfer-encoding',
    'upgrade',
)

# Characters left as-is when re-quoting a path or query taken from the request
#   line. '%' keeps existing escapes intact, the rest are RFC 3986 reserved and
#   unreserved characters that carry meaning to the upstream.
SAFE_PATH = "/%:@!$&'()*+,;=-._~"
SAFE_QUERY = SAFE_PATH + "?"

# Request headers that only concern this hop's body handling. The body has
#   already been read in full before relaying, so the upstream gets a plain
#   Content-Length request instead.
REQUEST_ONLY = ('expect',)

# Bounds for reading a chunked request body.
CHUNK_SIZE_PATTERN = re.compile(b'^[0-9A-Fa-f]{1,15}$')
MAX_TRAILER_LINES = 100

# RFC 9110 method token. Python 3's http.client checks this itself, Python 2's does not.
METHOD_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


class NoRedirection(HTTPErrorProcessor):

    def http_response(self, request, response):
        # Immediately pass responses along. Let the client deal with
        # sending a second request in the case of redirects and such.
        return response

    https_response = http_response


def strip_hop_by_hop(items):
    """Drop hop-by-hop headers from a list of (name, value) pairs."""
    named = set()
    for key, value in items:
        if key.lower() == 'connection':
            named.update(v.strip().lower() for v in value.split(','))
    return [
        (key, value)
        for key, value in items
        if key.lower() not in HOP_BY_HOP and key.lower() not in named
    ]


def response_header_list(resp):
    """Response headers in order, repeated names (Set-Cookie) kept."""
    info = resp.info()
    if sys.version_info[0] == 2:
        # mimetools.Message.items() collapses repeats, the raw lines do not.
        return common.header_list_from_text("".join(info.headers))
    return list(info.items())


def relay_target(raw_target):
    """Path and query to request upstream, taken from the raw request target.

    The raw form is kept (rather than the decoded self.path) so that escapes
    such as %2F and reserved characters reach the upstream unchanged. Dot
    segments are still resolved, so a request cannot climb above the target's
    base path."""
    raw_target = raw_target.split('#', 1)[0]
    path, sep, query = raw_target.partition('?')
    if '://' in path:
        # Absolute-form (http://host/path), as sent to forward proxies.
        path = '/' + path.split('://', 1)[1].partition('/')[2]

    segments = []
    for segment in path.split('/')[1:]:
        decoded = segment.lower().replace('%2e', '.')
        if decoded == '.':
            continue
        if decoded == '..':
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    if path.endswith('/') or path.endswith('/.') or path.endswith('/..'):
        if segments and segments[-1] != '':
            segments.append('')

    relayed = quote('/' + '/'.join(segments), safe=SAFE_PATH)
    if sep:
        relayed += '?' + quote(query, safe=SAFE_QUERY)
    return relayed


class Proxy(common.CoreHttpServer):

    server_version = "CoreHttpServer (Quick Proxy)"

    opener = build_opener(NoRedirection)

    log_on_send_error = True

    def do_PROXY(self):

        if not METHOD_PATTERN.match(getattr(self, common.ATTR_COMMAND, "")):
            return self.send_error(400, "Bad request method")

        parsed = urlsplit(common.args[TITLE_TARGET])
        words = self.requestline.split()
        raw_target = words[1] if len(words) > 1 else '/'
        url = "%s://%s%s%s" % (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/'),
            relay_target(raw_target),
        )

        req_items = [
            (k, v)
            for k, v in strip_hop_by_hop(getattr(self, 'header_list', []))
            if k.lower() not in REQUEST_ONLY
        ]
        if common.authentication_stores:
            # The client's credentials were for this proxy, not the upstream.
            req_items = [(k, v) for k, v in req_items if k.lower() != 'authorization']

        # urllib takes a dictionary, so join repeated headers (RFC 9110 5.3).
        req_headers = common.CaselessDict()
        for key, value in req_items:
            if key in req_headers:
                joiner = '; ' if key.lower() == 'cookie' else ', '
                value = req_headers[key] + joiner + value
            req_headers[key] = value

        # The X-Forwarded-Host (XFH) header is a de-facto standard header for identifying the
        #   original host requested by the client in the Host HTTP request header.
        if req_headers["host"]:
            req_headers["X-Forwarded-Host"] = req_headers["host"]
        proto = "http"
        if common.args[common.TITLE_SSL_CERT] or common.args[common.TITLE_SSL_SELF_SIGNED]:
            proto = "https"
        req_headers["X-Forwarded-Proto"] = proto

        forward_chain = req_headers.get("X-Forwarded-For")
        if forward_chain:
            forward_chain += ", "
        forward_chain += self.client_address[0]
        req_headers["X-Forwarded-For"] = forward_chain

        req_headers["Host"] = parsed.netloc.rsplit('@', 1)[-1]

        data = None

        # Read from data to relay.
        # This requires trusting user data more than I'm comfortable with,
        #  but I think that I've taken enough precautions for a script
        #  that should only be used as a quick, dirty, and above all TEMPORARY solution
        m = common.args[TITLE_MAX_LENGTH]

        lengths = set(
            v for k, v in getattr(self, 'header_list', []) if k.lower() == 'content-length'
        )
        transfer_encoding = self.headers.get('transfer-encoding', '')
        if transfer_encoding:
            if lengths:
                # RFC 9112 says Transfer-Encoding wins, but a proxy and upstream that
                #   disagree on where a body ends is how requests get smuggled.
                return self.send_error(400, "Both Transfer-Encoding and Content-Length given")
            if transfer_encoding.strip().lower() != 'chunked':
                return self.send_error(501, "Unsupported Transfer-Encoding")
            # urllib cannot stream a chunked body onward, so decode and buffer it
            #   (as Content-Length bodies are), then relay it with a length.
            data, error = self.read_chunked_body(m)
            if error == 413:
                return self.send_error(413, 'Content-Length is too large. Max: %d' % m)
            if error:
                return self.send_error(400, "Malformed chunked body")
        else:
            if len(lengths) > 1:
                return self.send_error(400, "Conflicting Content-Length headers")

            # Use the content-length header, though being user-defined input it's not really trustworthy.
            # Someone fudging this data is the main reason for my worrying over a timeout value.
            try:
                l = int(self.headers.get('content-length', 0) or 0)
                if l < 0:
                    # Parsed properly, but some joker put in a negative number.
                    raise ValueError()
            except ValueError:
                return self.send_error(
                    400,
                    "Illegal content-length header value: %s"
                    % self.headers.get('content-length', 0),
                )

            if m and l > m:
                return self.send_error(413, 'Content-Length is too large. Max: %d' % m)

            if l:
                # Read from rfile into variable, for any method that declares a body.
                # urllib is SUPPOSED to be able to adapt to being
                # directly fed something with a read() method,
                # but in my testing this has resulted in infinite hangups and
                # trouble reading things on the target's side.
                # Will have to fix later, but for now this creates potential problems if large files are being uploaded.
                # This is a good part of the reason why the --max-length flag exists.
                data = self.rfile.read(l)
                # Intentionally not bothering to catch socket.timeout exception. Let it bubble up.

        # Construct request
        req = Request(url, data, headers=req_headers)
        req.get_method = lambda: getattr(self, common.ATTR_COMMAND, "GET")

        try:
            resp = self.opener.open(req, timeout=common.args[common.TITLE_TIMEOUT])
            if getattr(getattr(resp.fp, '_sock', None), 'version', None) == 9:
                # Python 2 httplib takes a reply without a status line to be
                #   HTTP/0.9, which is far likelier to be a broken upstream.
                resp.close()
                return self.send_error(502, "Error relaying request")

            # Get response headers to pass along from target server to client.
            resp_items = strip_hop_by_hop(response_header_list(resp))
            code = resp.getcode()
            # Python 3 has the reason phrase as .reason, Python 2 as .msg.
            reason = getattr(resp, 'reason', None) or getattr(resp, 'msg', '')
            if not isinstance(reason, str):
                reason = ''
        except ValueError as e:
            # urllib refused the request itself, for example a method with control characters.
            return self.send_error(400, "Request cannot be relayed")
        except socket.timeout:
            return self.send_error(504, "Upstream timed out")
        except URLError as e:
            if isinstance(getattr(e, 'reason', None), socket.timeout):
                return self.send_error(504, "Upstream timed out")
            return self.send_error(502, "Error relaying request")
        except (SocketError, HTTPException) as e:
            # HTTPException covers malformed upstream responses (BadStatusLine and such).
            return self.send_error(502, "Error relaying request")

        location_base = "%s://%s%s" % (parsed.scheme, parsed.netloc, parsed.path.rstrip('/'))

        self.log_message(
            '"%s" %s %s', getattr(self, common.ATTR_REQUEST_LINE, ""), code, None
        )
        if self.headers_enabled():
            self.buffer_header_line(
                "%s %d %s\r\n"
                % (self.protocol_version, code, re.sub(r'[\r\n]', '', reason))
            )
        for key, value in resp_items:
            if key.lower() == 'location' and (
                value == location_base or value.startswith(location_base + '/')
            ):
                # Keep redirects to the upstream pointing at this proxy instead.
                value = value[len(location_base) :] or '/'
            self.send_header(key, value)
        # urllib has already removed any chunked framing, and the body may have no
        #   length of its own, so the end of this connection marks its end.
        self.send_header('Connection', 'close')
        self.end_headers()

        # Returned rather than copied here, so that invoke() does not send an
        #   error response on top of a body that fails part way through.
        return resp

    def read_chunked_body(self, limit=None):
        """Decode a chunked request body (RFC 9112 7.1) from rfile.

        Returns (body, None) on success, or (None, code) with 413 when the body
        passes limit bytes and 400 when it is malformed. Chunk extensions and
        trailer fields are read and discarded. Read timeouts are left to bubble
        up, as with Content-Length bodies."""
        chunks = []
        total = 0
        while True:
            line = self.rfile.readline(65537)
            if not line.endswith(b'\n'):
                # Connection closed, or an absurdly long size line.
                return None, 400
            size_text = line.split(b';', 1)[0].strip()
            if not CHUNK_SIZE_PATTERN.match(size_text):
                return None, 400
            size = int(size_text, 16)
            if not size:
                break
            total += size
            if limit and total > limit:
                # Checked before reading, so an oversized body is never held.
                return None, 413
            data = self.rfile.read(size)
            if len(data) != size or self.rfile.read(2) != b'\r\n':
                return None, 400
            chunks.append(data)

        for i in range(MAX_TRAILER_LINES):
            line = self.rfile.readline(65537)
            if line in (b'\r\n', b'\n'):
                return b''.join(chunks), None
            if not line.endswith(b'\n'):
                return None, 400
        return None, 400

    def get_command(self):
        return "PROXY"

    def log_request(self, code='-', size='-'):
        """Log an accepted request.
        This is called by send_response().
        """


def validate_target(self):
    target = self.last_operand()
    if not target:
        return "No %s defined." % common.colour_text(TITLE_TARGET)
    try:
        parsed = urlsplit(target)
        port = parsed.port  # Raises ValueError when out of range or not a number
    except ValueError:
        parsed = None
    if (
        not parsed
        or parsed.scheme not in ('http', 'https')
        or not parsed.hostname
        or re.search(r'\s', target)
        or parsed.query
        or parsed.fragment
    ):
        return "Invalid target URL: %s" % common.colour_text(
            target, common.COLOUR_GREEN
        )
    self.args[TITLE_TARGET] = target


common.args.add_validator(validate_target)

if __name__ == '__main__':
    common.args.process(sys.argv)

    bind_address, bind_port, target = common.get_target_information()
    # Directory is moot here.
    # Overwrite with target to make the line afterwards slightly less monstrous.
    target = common.args[TITLE_TARGET]

    common.print_notice(
        "Forwarding requests on %s to target: %s"
        % (
            common.colour_text(
                "%s:%d" % (bind_address, bind_port), common.COLOUR_GREEN
            ),
            common.colour_text(target, common.COLOUR_GREEN),
        )
    )
    common.announce_common_arguments(None)

    common.serve(Proxy, False)
