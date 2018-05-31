
# Colours

import sys
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

#
# Common Message Functions
###

def print_error(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_RED, "Error", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_notice(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_BLUE, "Notice", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_warning(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_YELLOW, "Warning", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)
