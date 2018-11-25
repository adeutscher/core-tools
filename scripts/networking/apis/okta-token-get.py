#!/usr/bin/env python

# Script to create an Okta token.
# Useful when debugging an API that uses Okta for authentication/authorization.

import base64, getopt, json, os, sys, urllib2

error_count = 0

def __print_message(colour, header, message):
    print >> sys.stderr, "%s[%s]: %s" % (colour_text(colour, header), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

def colour_text(colour, text):
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def enable_colours(force = False):
    global COLOUR_PURPLE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_PURPLE = '\033[1;35m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_PURPLE = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_BLUE = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

def print_error(message):
    global error_count
    error_count += 1
    __print_message(COLOUR_RED, "Error", message)

def print_notice(message):
    __print_message(COLOUR_BLUE, "Notice", message)

def print_warning(message):
    __print_message(COLOUR_YELLOW, "Warning", message)

def print_usage(message):
    __print_message(COLOUR_PURPLE, "Usage", message)

#
# Script Functions
###

TITLE_CLIENT_SECRET = "client secret"
TITLE_CLIENT_ID = "client id"
TITLE_SCOPE = "requested scope"
TITLE_URL = "Token URL"

DEFAULTS = {
    TITLE_SCOPE: "access_token"
}

ENV_VARS = {
  TITLE_CLIENT_ID: "OKTA_CLIENT_ID",
  TITLE_CLIENT_SECRET: "OKTA_CLIENT_SECRET",
  TITLE_SCOPE: "OKTA_SCOPE",
  TITLE_URL: "OKTA_URL"
}

def get_okta_token():

    creds = "%s:%s" % (args.get(TITLE_CLIENT_ID), args.get(TITLE_CLIENT_SECRET))

    token = ""
    data = "grant_type=client_credentials&scope=%s" % args.get(TITLE_SCOPE)

    try:
        req = urllib2.Request(args.get(TITLE_URL))
        req.add_header("authorization", "Basic %s" % base64.b64encode(creds))
        req.add_header("accept", "application/json")
        req.add_header("cache-control", "no-cache")
        req.add_header("content-type", "application/x-www-form-urlencoded")
        response = urllib2.urlopen(req, data)
        r_obj = json.loads(response.read())
        token = r_obj["access_token"]
    except urllib2.HTTPError as e:
        print_error("Could not get Okta token: %s" % colour_text(COLOUR_BOLD, e))
        print_error(e.read())
    return token

def hexit(exit_code = 0):
    print_usage("%s -c okta_client_id -s okta_secret -u okta_url [-h]" % os.path.basename(sys.argv[0]))
    exit(exit_code)

def main():

    process_arguments()

    # Get an Okta Token
    token = get_okta_token()
    print "Authorization: Bearer %s" % token

def process_arguments():

    global args
    args = {}

    try:
        opts, operands = getopt.gnu_getopt(sys.argv[1:],"c:hs:S:u:")
    except getopt.GetoptError as e:
        print_error("GetoptError: %s" % e)
        hexit(1)
    for opt, optarg in opts:
        if opt in ("-c"):
            args[TITLE_CLIENT_ID] = optarg
        elif opt in ("-h"):
            hexit(0)
        elif opt in ("-s"):
            args[TITLE_CLIENT_SECRET] = optarg
        elif opt in ("-S"):
            args[TITLE_SCOPE] = optarg
        elif opt in ("-u"):
            args[TITLE_URL] = optarg

    # Check for required items.
    for item in [TITLE_CLIENT_ID, TITLE_CLIENT_SECRET, TITLE_URL, TITLE_SCOPE]:
        if item not in args and ENV_VARS.get(item):
            args[item] = os.environ.get(ENV_VARS.get(item), DEFAULTS.get(item))
        if not args[item]:
            print_error("No %s provided." % item)

    global error_count
    if error_count:
        hexit(1)

if __name__ == "__main__":
    main()
