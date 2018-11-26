#!/usr/bin/env python

import CoreHttpServer as common
import cookielib, getopt, re, shutil, sys, urllib2, urlparse

TITLE_TARGET = "proxy target"

def process_arguments():

    # Verbose Sharing Arguments

    good = True
    errors = []

    try:
        opts, flat_args = getopt.gnu_getopt(sys.argv[1:],common.get_opts(), common.get_opts_long())
    except getopt.GetoptError as e:
        print "GetoptError: %s" % str(e)
        hexit(1)
    for opt, arg in opts:
        common_good, processed = common.handle_common_argument(opt, arg)
        good = common_good and good

        if processed:
            continue
    switch_arg = False

    if flat_args:
        common.args[TITLE_TARGET] = flat_args[len(flat_args)-1]

    if TITLE_TARGET not in common.args:
        errors.append("No %s defined." % common.colour_text(common.COLOUR_BOLD, TITLE_TARGET))
    elif not re.match("^https?:\/\/[a-z0-9]+([\-\.]{1}[a-z0-9]+)*(\.[a-z0-9]+([\-\.]{1}[a-z0-9]+)*)*(:[0-9]{1,5})?(\/.*)?$", common.args[TITLE_TARGET]):
        errors.append("Invalid target URL: %s" % common.colour_text(common.COLOUR_GREEN, common.args[TITLE_TARGET]))

    if len(common.access.errors):
        good = False
        errors.extend(common.access.errors)

    errors.extend(common.validate_common_arguments())

    if good and not errors:
        common.access.announce_filter_actions()
    else:
        good = False
        for e in errors:
            common.print_error(e)

    return good

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

    def do_GET(self):
        url = "%s%s" % (common.args[TITLE_TARGET], self.path)

        req_headers = dict(self.headers_dict)

        # The X-Forwarded-Host (XFH) header is a de-facto standard header for identifying the
        #   original host requested by the client in the Host HTTP request header.
        req_headers["X-Forwarded-Host"] = req_headers.get("Host", None)
        req_headers["X-Forwarded-Proto"] = "http" # Scheme of client to this server. This method only supports HTTP for the moment.

        forward_chain = req_headers.get("X-Forwarded-For", "")
        if forward_chain:
            forward_chain += ", "
        forward_chain += self.client_address[0]
        req_headers["X-Forwarded-For"] = forward_chain

        parsed = urlparse.urlsplit(common.args[TITLE_TARGET])
        req_headers["Host"] = "%s:%d" % (parsed.hostname, parsed.port)

        # Construct request
        req = urllib2.Request(url, headers=req_headers)
        try:
            resp = self.opener.open(req)

            # Get response headers to pass along from target server to client.
            resp_headers = self.get_header_dict(resp.info())
            code = str(resp.getcode())
        except urllib2.URLError as e:
            return self.send_error(500, "Error relaying request")

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

    def log_request(self, code='-', size='-'):
        """Log an accepted request.
        This is called by send_response().
        """

if __name__ == '__main__':
    if not process_arguments():
        exit(1)

    bind_address, bind_port, target = common.get_target_information()
    # Directory is moot here.
    # Overwrite with target to make the line afterwards slightly less monstrous.
    target = common.args[TITLE_TARGET]

    common.print_notice("Forwarding requests on %s to target: %s" % (common.colour_text(common.COLOUR_GREEN, "%s:%d" % (bind_address, bind_port)), common.colour_text(common.COLOUR_GREEN, target)))
    common.announce_common_arguments(None)

    common.serve(Proxy, True)
