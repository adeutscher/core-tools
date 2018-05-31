#!/usr/bin/python

import getopt, getpass, os, re, subprocess, sys

# Defaults

DEFAULT_HEIGHT = 900
DEFAULT_WIDTH = 1600

# Colours

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

# Store argument titles as variables
TITLE_SERVER = "server"
TITLE_DOMAIN = "domain"
TITLE_USER = "user"
TITLE_PASSWORD = "password"
TITLE_HEIGHT = "height"
TITLE_WIDTH = "width"

def do_rdp(cli_args):
    env_status = validate_environment()

    args, good_args = process_args(cli_args)

    good_args = validate_args(args) and env_status and good_args

    if not good_args:
        print "Usage: ./rdp.py server [-d domain] [-D] [-g HxW] [-h height] [-p password] [-P] [-u user] [-U] [-w width]"
        exit(1)

    command = process_switches(args)

    print_summary(args)

    try:
        p = subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)
        p.communicate()
        exit(p.returncode)
    except KeyboardInterrupt:
        p.kill()
        exit(130)
    except OSError as e:
        print "OSError: %s" % e
        exit(1)

def print_error(message):
    print "%sError%s: %s" % (COLOUR_RED, COLOUR_OFF, message)

def print_summary(args):

    if TITLE_DOMAIN in args:
        user = "%s\\%s" % (args[TITLE_DOMAIN], args[TITLE_USER])
    else:
        user = args[TITLE_USER]

    message = "Connecting to %s%s%s (display: %s%dx%d%s) as %s%s%s" % (COLOUR_GREEN, args[TITLE_SERVER], COLOUR_OFF, COLOUR_BOLD, args[TITLE_WIDTH], args[TITLE_HEIGHT], COLOUR_OFF, COLOUR_BOLD, user, COLOUR_OFF)

    if TITLE_PASSWORD in args:
        message += " with a password"
    message += "."

    print message

def print_warning(message):
    print "%sWarning%s: %s" % (COLOUR_YELLOW, COLOUR_OFF, message)

def process_args(cli_args):
    values = {}

    # Errors that have not been resolved.
    good_args = True

    try:
        opts, operands = getopt.gnu_getopt(cli_args, "d:Dg:h:p:Pu:Uw:")
    except getopt.GetoptError as e:
        print_error(e)
        exit(1)

    for opt,optarg in opts:
        if opt == "-d":
            if validate_string(optarg, TITLE_DOMAIN):
                set_var(values, TITLE_DOMAIN, optarg)
            else:
                good_args = False
        if opt == "-D":
            # Manual domain input
            record_var(values, TITLE_DOMAIN, COLOUR_BOLD, False)
        if opt == "-g":
            # Single-arg geometry
            # Try a few different delimiters ('x', ',', and ' ')
            for delim in ["x", ",", " "]:
                split = optarg.split(delim)
                if len(split) > 1:
                    break
            if not len(split) > 1:
                print_error("Geometry requires to integers (accepted delimiters: 'x', ',', and ' ')")
                good_args = False
                continue

            w_check = validate_int(split[0], TITLE_WIDTH)
            h_check = validate_int(split[1], TITLE_HEIGHT)
            if w_check and h_check:
                set_var(values, TITLE_WIDTH, int(split[0]))
                set_var(values, TITLE_HEIGHT, int(split[1]))
            else:
                good_args = False

        if opt == "-h":
            if validate_int(optarg, TITLE_HEIGHT):
                set_var(values, TITLE_HEIGHT, int(optarg))
            else:
                good_args = False
        if opt == "-p":
            # Password has no validation, since an exotic password
            #   could have features that invalidate it.
            set_var(values, TITLE_PASSWORD, optarg, COLOUR_BOLD, False)
        if opt == "-P":
            # Manual password input
            record_var(values, TITLE_PASSWORD, COLOUR_BOLD, False)
        if opt == "-u":
            if validate_string(optarg, TITLE_USER):
                set_var(values, TITLE_USER, optarg)
            else:
                good_args = False
        if opt == "-U":
            # Manual user input
            record_var(values, TITLE_USER, COLOUR_BOLD, False)
        if opt == "-w":
            if validate_int(optarg, TITLE_WIDTH):
                set_var(values, TITLE_WIDTH, int(optarg))
            else:
                good_args = False

    for operand in operands[1:]:
        set_var(values, TITLE_SERVER, operand, COLOUR_GREEN)

    # If no values were set, load in defaults instead.
    # Doing this after loading because of the override notice.
    if TITLE_HEIGHT not in values:
        values[TITLE_HEIGHT] = int(os.environ.get("RDP_HEIGHT", DEFAULT_HEIGHT))
    if TITLE_WIDTH not in values:
        values[TITLE_WIDTH] = int(os.environ.get("RDP_WIDTH", DEFAULT_WIDTH))
    if TITLE_DOMAIN not in values and "RDP_DOMAIN" in os.environ:
        set_var(values, TITLE_DOMAIN, os.environ.get("RDP_DOMAIN"))
    if TITLE_PASSWORD not in values and "RDP_PASSWORD" in os.environ:
        set_var(values, TITLE_PASSWORD, os.environ.get("RDP_PASSWORD"))
    if TITLE_USER not in values:
        set_var(values, TITLE_USER, os.environ.get("RDP_USER", os.getlogin()))

    return values, good_args

def process_switches(args):
    # Read no-arg output to determine xfreerdp version

    new_switches=False

    try:
        p = subprocess.Popen(['xfreerdp'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Read the first 10 lines for the usage summary.
        # Not counting on it being on a specific line.
        i = 0
        for line in p.stdout.readlines():
            i += 1
            if i > 10:
                break
            if "[/v:<server>[:port]]" in line:
                new_switches=True
                break
    except OSError:
        # Since we are already checking for xfreerdp, this probably will not come up.
        # This is mostly here because I was doing some initial development on a machine without xfreerdp.
        pass

    if new_switches:
        # New switch scheme

        # Static switches
        switches = "xfreerdp +auto-reconnect /sec:rdp +clipboard +compression +heartbeat /compression-level:2".split(" ")
        # Display size
        switches.append("/h:%d" % args[TITLE_HEIGHT])
        switches.append("/w:%d" % args[TITLE_WIDTH])
        # Domain/Password/User
        if TITLE_DOMAIN in args:
            switches.append("/d:%s" % args[TITLE_DOMAIN])
        if TITLE_PASSWORD in args:
            switches.append("/p:%s" % args[TITLE_PASSWORD])
        if TITLE_USER in args:
            switches.append("/u:%s" % args[TITLE_USER])
        # Server address
        switches.append("/v:%s" % args[TITLE_SERVER])
    else:
        # Old switch scheme

        # Static switches
        switches = "xfreerdp --sec rdp --plugin cliprdr".split(" ")
        # Display size
        switches.extend(["-g", "%dx%d" % (args[TITLE_WIDTH], args[TITLE_HEIGHT])])
        # Domain/Password/User
        if TITLE_DOMAIN in args:
            switches.extend(["-d", args[TITLE_DOMAIN]])
        if TITLE_PASSWORD in args:
            switches.extend(["-p", args[TITLE_PASSWORD]])
        if TITLE_USER in args:
            switches.extend(["-u", args[TITLE_USER]])
        # Server address
        switches.append(args[TITLE_SERVER])
    return switches

def record_var(values, title, colour=COLOUR_BOLD, reportOverwrite=True):
    temp = ""
    while not temp:
        temp = getpass.getpass("Enter %s: " % title)
        if not temp:
            continue # Immediately loop again if empty.

        # Validation may or may not be required depending on title.
        if title == TITLE_PASSWORD:
            # Passwords need no validation
            continue
        elif title == TITLE_USER:
            # Check to see if the user provided their username in a format like 'DOMAIN\user'.
            split = temp.split("\\")
            if len(split) > 1:
                if validate_string(split[0], TITLE_DOMAIN) and validate_string(split[1], TITLE_USER):
                    set_var(values, TITLE_DOMAIN, split[0])
                    temp = split[1]
                else:
                    # Invalid string, reset for next loop
                    temp = ""
            elif not validate_string(temp, TITLE_USER):
                # Invalid string, reset for next loop
                temp = ""
        elif title == TITLE_DOMAIN:
            if not validate_string(temp, TITLE_DOMAIN):
                # Invalid string, reset for next loop
                temp = ""
    set_var(values, title, temp, colour, reportOverwrite)

def set_var(values, title, value, colour=COLOUR_BOLD, reportOverwrite=True):
    if title in values and value != values[title]:
        # Print a warning if a value is already set.
        # Don't bother raising a fuss if the same value has been specified twice.
        if reportOverwrite:
            print_warning("More than one %s specified in arguments: Replacing '%s%s%s' with '%s%s%s'" % (title, colour, value, COLOUR_OFF, colour, values[title], COLOUR_OFF))
        else:
            print_warning("More than one %s specified in arguments. Using latest value." % title)
    values[title] = value

def validate_args(args):
    all_clear = True
    if TITLE_SERVER not in args:
        print_error("No server specified.")
        all_clear = False
    return all_clear


def validate_environment():
    all_clear = True
    if not which("xfreerdp"):
        print_error("xfreerdp is not found in PATH.")
        all_clear = False

    if not "DISPLAY" in os.environ:
        print_error("No DISPLAY variable set.")
        all_clear = False
    return all_clear

def validate_int(candidate, title):
    try:
        t = int(candidate)
        return True
    except ValueError:
        print_error("Must express %s as an integer." % title)
        return False

def validate_string(candidate, title):
    if title in (TITLE_USER, TITLE_DOMAIN) and not re.match(r'^[^\s]+$', candidate):
        print_error("A %s may not contain any spaces." % title)
        return False
    return True

def which(program):
    # Credit: "Jay": https://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

if __name__ == "__main__":
    do_rdp(sys.argv)
