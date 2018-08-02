
# Common variables for google API scripts.

import os, re, sys

#
# Common Colours and Message Functions
###

def __print_message(colour, header, message):
    print "%s[%s]: %s" % (colour_text(colour, header), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

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

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    __print_message(COLOUR_RED, "Error", message)

def print_notice(message):
    __print_message(COLOUR_BLUE, "Notice", message)

def print_warning(message):
    __print_message(COLOUR_YELLOW, "Warning", message)

#
# Script Functions and Variables
###

try:
    from oauth2client.file import Storage
    from oauth2client import client
    from oauth2client import tools
except ImportError:
    print_error("Problem importing oauth2client modules. To install: pip install --upgrade google-api-python-client")

APPLICATION_NAME = 'adeutscher Tool Scripts'

# If modifying these scopes, delete your previously saved client credentials.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

CLIENT_SECRET_PATH = os.environ.get("GOOGLE_SECRET", os.path.join(os.environ.get("HOME"), ".local/tools/google/client_secret.json"))
AUTHORIZATION_DIR = os.environ.get("GOOGLE_AUTH_DIR", os.path.join(os.environ.get("HOME"), ".local/tools/google/authorization"))

if not os.path.isfile(CLIENT_SECRET_PATH):
    print_error("Client secret file not found: %s" % colour_text(COLOUR_GREEN, CLIENT_SECRET_PATH))

try:
    import argparse
    flags = argparse.Namespace(auth_host_name='localhost', auth_host_port=[8080, 8090], logging_level='ERROR', noauth_local_webserver=False)
except ImportError:
    flags = None

def get_credentials(tag = None):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """

    if not os.path.exists(AUTHORIZATION_DIR):
      os.makedirs(AUTHORIZATION_DIR)

    if not tag:
        tag = "default"

    if not re.match(r"^[0-9\-\+_@-Za-z]+$", tag):
        print_error("Invalid tag: %s" % colour_text(COLOUR_BOLD, tag))
        return

    credential_path = os.path.join(AUTHORIZATION_DIR, "authorization.%s.json" % tag)
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_PATH, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print_notice('Storing credentials to %s' % colour_text(COLOUR_GREEN, credential_path))

    return credentials
