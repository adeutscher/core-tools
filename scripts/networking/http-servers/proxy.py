#!/usr/bin/env python

import CoreHttpServer as common
import cookielib, getopt, os, re, shutil, sys, urllib2, urlparse

TITLE_TARGET = "proxy target"
common.local_files.append(os.path.realpath(__file__))

# Remove unused arguments
del common.args.opts[common.OPT_TYPE_FLAG]["-P"]

class NoRedirection(urllib2.HTTPErrorProcessor):

    def http_response(self, request, response):
        # Immediately pass responses along. Let the client deal with
        # sending a second request in the case of redirects and such.
        return response

    https_response = http_response

class Proxy(common.CoreHttpServer):

    server_version = "CoreHttpServer (Quick Proxy)"

    opener = urllib2.build_opener(NoRedirection)

    log_on_send_error = True

    def do_PROXY(self):
        url = "%s%s" % (common.args[TITLE_TARGET], self.path)

        # Copy request headers.
        req_headers = dict(self.headers_dict)

        # The X-Forwarded-Host (XFH) header is a de-facto standard header for identifying the
        #   original host requested by the client in the Host HTTP request header.
        host = self.headers.getheader("host", None)
        if host:
            req_headers["X-Forwarded-Host"] = host
        proto = "http"
        if common.args.get(common.TITLE_SSL_CERT):
            proto = "https"
        req_headers["X-Forwarded-Proto"] = proto

        forward_chain = self.headers.getheader("X-Forwarded-For", "")
        if forward_chain:
            forward_chain += ", "
        forward_chain += self.client_address[0]
        req_headers["X-Forwarded-For"] = forward_chain

        parsed = urlparse.urlsplit(common.args[TITLE_TARGET])
        port = parsed.port
        if port is None:
            port = 80
            if parsed.scheme == "https":
                port = 443

        req_headers["Host"] = "%s:%s" % (parsed.hostname, port)

        # Construct request
        req = urllib2.Request(url, headers=req_headers)
        req.get_method = lambda: self.command

        data = None
        try:
            # Read from data to relay.
            # This requires trusting user data more than I'm comfortable with,
            #  but I think that I've taken enough precautions for a script
            #  that should only be used as a quick, dirty, and above all TEMPORARY solution
            if self.command.lower() in ("post", "put"):
                # For an extra layer of safety, only bother to try reading further data from
                # POST or PUT commands. Revise this if we discover an exception to the rule, of course.


                # Use the content-length header, though being user-defined input it's not really trustworthy.
                # Someone fudging this data is the main reason for my worrying over a timeout value.
                l = int(self.headers.getheader('content-length', 0))

                if l < 0:
                    # Parsed properly, but some joker put in a negative number.
                    raise ValueError()
                elif l:
                    data = self.rfile.read(l)
            # Intentionally not bothering to catch socket.timeout exception. Let it bubble up.
        except ValueError:
            return self.send_error(500, "Illegal content-length header value: %s" % self.headers.getheader('content-length'))

        if data:
            req.add_data(data)

        try:
            resp = self.opener.open(req)

            # Get response headers to pass along from target server to client.
            resp_headers = self.get_header_dict(resp.info())
            code = str(resp.getcode())
        except urllib2.URLError as e:
            return self.send_error(502, "Error relaying request.")

        # TODO: This is the place to modify headers before they're written.

        if self.request_version != 'HTTP/0.9':
            self.wfile.write("%s %s %s\r\n" % (self.protocol_version, code, self.path))
        for key in resp_headers:
            # Write response headers
            if resp_headers[key]:
                self.send_header(key, resp_headers[key])
        self.end_headers()

        self.log_message('"%s" %s %s', self.requestline, code, None)
        self.copyobj(resp, self.wfile)

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
    elif not re.match("^https?:\/\/[a-z0-9]+([\-\.]{1}[a-z0-9]+)*(\.[a-z0-9]+([\-\.]{1}[a-z0-9]+)*)*(:[0-9]{1,5})?(\/.*)?$", target):
        return "Invalid target URL: %s" % common.colour_text(target, common.COLOUR_GREEN)
    self.args[TITLE_TARGET] = target
common.args.add_validator(validate_target)

if __name__ == '__main__':
    common.args.process(sys.argv)

    bind_address, bind_port, target = common.get_target_information()
    # Directory is moot here.
    # Overwrite with target to make the line afterwards slightly less monstrous.
    target = common.args[TITLE_TARGET]

    common.print_notice("Forwarding requests on %s to target: %s" % (common.colour_text("%s:%d" % (bind_address, bind_port), common.COLOUR_GREEN), common.colour_text(target, common.COLOUR_GREEN)))
    common.announce_common_arguments(None)

    common.serve(Proxy, False)
