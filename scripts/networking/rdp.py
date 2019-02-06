#!/usr/bin/python

import getopt, getpass, os, re, subprocess, sys, time

# Defaults

DEFAULT_HEIGHT = 900
DEFAULT_WIDTH = 1600

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

def print_usage(message):
    __print_message(COLOUR_PURPLE, "Usage", message)

def print_warning(message):
    __print_message(COLOUR_YELLOW, "Warning", message)

# Script Variables and Functions
###

# Defaults
DEFAULT_RDP_SECURITY = True
DEFAULT_USER = os.getlogin()
DEFAULT_VERBOSE = False

# Environment Variables
ENV_DOMAIN = "RDP_DOMAIN"
ENV_PASSWORD = "RDP_PASSWORD"
ENV_USER = "RDP_USER"
ENV_HEIGHT = "RDP_HEIGHT"
ENV_WIDTH = "RDP_WIDTH"

# Store argument titles as variables
TITLE_SERVER = "server"
TITLE_RDP_SECURITY = "RDP Security"
TITLE_DOMAIN = "domain"
TITLE_USER = "user"
TITLE_PASSWORD = "password"
TITLE_HEIGHT = "height"
TITLE_WIDTH = "width"
TITLE_VERBOSE = "verbose"
TITLE_EC2_FILE = "EC2 Key File"

def get_user(display = False):

    if TITLE_EC2_FILE in args:
        user = "administrator" # Assume to always be 'administrator' for EC2 instances.
    elif display and TITLE_DOMAIN in args:
        user = "%s\\%s" % (args[TITLE_DOMAIN], get_user())
    else:
        user = args.get(TITLE_USER, os.environ.get(ENV_USER, DEFAULT_USER))

    return user

def print_summary():

    message = "Connecting to %s (display: %s) as %s" % (colour_text(COLOUR_GREEN, args[TITLE_SERVER]), colour_text(COLOUR_BOLD, "%sx%s" % (args[TITLE_WIDTH], args[TITLE_HEIGHT])), colour_text(COLOUR_BOLD, get_user(True)))

    if TITLE_PASSWORD in args:
        message += " with a password"
    message += "."

    print_notice(message)

    if TITLE_EC2_FILE in args:
        print_warning("'%s' user is assumed for connecting to an EC2 instance." % colour_text(COLOUR_BOLD, get_user()))

def get_ec2_cipher():
    cipher = None
    if not os.path.isfile(args[TITLE_EC2_FILE]):
        print_error("EC2 Keyfile not found: %s" % colour_text(COLOUR_GREEN, args[TITLE_EC2_FILE]))
    else:
        # File exists.
        try:
            input = open(args[TITLE_EC2_FILE])
            key = RSA.importKey(input.read())
            input.close()
            cipher = PKCS1_v1_5.new(key)
        except NameError as e:
            print_error("Could not load EC2 key file because required RSA module was not loaded from pycrypto.")
        except Exception as e:
            # Most likely: Path provided was not to a file with a proper RSA key.
            print_error("Encountered %s loading EC2 key file ('%s'): %s" % (colour_text(COLOUR_RED, type(e).__name__), colour_text(COLOUR_GREEN, args[TITLE_EC2_FILE]), str(e)))
    return cipher

def process_args():
    values = {}

    # Errors that have not been resolved.
    good_args = True

    try:
        opts, operands = getopt.gnu_getopt(sys.argv, "d:De:g:h:p:Psu:Uvw:")
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
        if opt in ('-e'):
            set_var(values, TITLE_EC2_FILE, optarg)
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
        elif opt == "-s":
            values[TITLE_RDP_SECURITY] = False
        if opt == "-u":
            if validate_string(optarg, TITLE_USER):
                set_var(values, TITLE_USER, optarg)
            else:
                good_args = False
        if opt == "-U":
            # Manual user input
            record_var(values, TITLE_USER, COLOUR_BOLD, False)
        if opt in ("-v"):
            values[TITLE_VERBOSE] = True
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
        values[TITLE_HEIGHT] = int(os.environ.get(ENV_HEIGHT, DEFAULT_HEIGHT))
    if TITLE_WIDTH not in values:
        values[TITLE_WIDTH] = int(os.environ.get(ENV_WIDTH, DEFAULT_WIDTH))
    if TITLE_DOMAIN not in values and ENV_DOMAIN in os.environ:
        set_var(values, TITLE_DOMAIN, os.environ.get(ENV_DOMAIN))
    if TITLE_PASSWORD not in values and ENV_PASSWORD in os.environ:
        set_var(values, TITLE_PASSWORD, os.environ.get(ENV_PASSWORD))

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
        switches = "xfreerdp +auto-reconnect +clipboard +compression +heartbeat /compression-level:2".split(" ")

        if args.get(TITLE_RDP_SECURITY, DEFAULT_RDP_SECURITY) and not TITLE_EC2_FILE in args:
            switches.append("/sec:rdp")

        # Display size
        switches.append("/h:%d" % args[TITLE_HEIGHT])
        switches.append("/w:%d" % args[TITLE_WIDTH])
        # Domain/Password/User
        if TITLE_DOMAIN in args:
            switches.append("/d:%s" % args[TITLE_DOMAIN])
        if TITLE_PASSWORD in args:
            switches.append("/p:%s" % args[TITLE_PASSWORD])
        switches.append("/u:%s" % get_user())
        # Server address
        switches.append("/v:%s" % args[TITLE_SERVER])
    else:
        # Old switch scheme

        # Static switches
        switches = "xfreerdp --plugin cliprdr".split(" ")

        # RDP Security Switch
        if args.get(TITLE_RDP_SECURITY, DEFAULT_RDP_SECURITY) and not TITLE_EC2_FILE in args:
            switches.extend("--sec rdp".split(" "))

        # Display size
        switches.extend(["-g", "%dx%d" % (args[TITLE_WIDTH], args[TITLE_HEIGHT])])
        # Domain/Password/User
        if TITLE_DOMAIN in args:
            switches.extend(["-d", args[TITLE_DOMAIN]])
        if TITLE_PASSWORD in args:
            switches.extend(["-p", args[TITLE_PASSWORD]])
        switches.extend(["-u", get_user()])
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

def set_ec2_info():
    good = False
    target = args.get(TITLE_SERVER)

    end = False

    try:
        ec2client = boto3.client('ec2')
        response = ec2client.describe_instances()

        tag_name = 'Name'
        label_instance_id = "instance ID"
        label_public_ip = "public IP"
        label_public_dns = "public DNS"
        label_tag_name = "'%s' tag" % tag_name

        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:

                state = instance.get('State')
                if not state or state.get('Name') != 'running':
                    # Immediately ignore anything that isn't running.
                    continue

                public_dns = instance.get('PublicDnsName')
                public_ip = instance.get('PublicIpAddress')
                instance_id = instance.get('InstanceId')
                platform = instance.get('Platform')

                # Attempt to match from InstanceId, public IP, public DNS name, or 'Name' tag.

                label = None
                name = ""
                if instance_id == target:
                    label = label_instance_id
                elif public_ip == target:
                    label = label_public_ip
                elif public_dns == target:
                    label = label_public_dns
                else:
                    tags = instance.get("Tags", [])
                    for tag in tags:
                        if tag.get("Key") == tag_name:
                            name = tag.get("Value", "")
                            if name == target:
                                label = label_tag_name
                            break

                if not label:
                    # Could not find a matching instance.
                    continue

                # After finding an instance, confirm that it is a Windows instance.
                # If a matching case is not Windows, then print a warning and try
                # the next entry.
                if not public_ip or instance.get('Platform') != 'windows':
                    print_warning("EC2 instance %s matches requested %s, but is not a Windows instance." % (instance_id, colour_text(COLOUR_BOLD, label)))
                    continue

                print_notice("Connecting to EC2 instance by %s matching target: %s" % (label, colour_text(COLOUR_BOLD, target)))

                # Found our target instance.
                # Whether or not we are able to get a password, we will be stopping with this item.
                end = True

                password_data =  ec2client.get_password_data(InstanceId = instance_id)
                raw_password = password_data.get("PasswordData", "").strip().decode('base64')

                if not raw_password:
                    print_error("Unable to get encrypted password data from instance '%s' matching %s: %s" % (colour_text(COLOUR_BOLD, instance_id), label, colour_text(COLOUR_BOLD, target)))
                    continue

                # Attempt to get password.
                cipher = get_ec2_cipher()
                plain_password = cipher.decrypt(raw_password, None)
                if not plain_password:
                    print_error("Unable to decode encrypted password data from instance '%s', decryption key is probably be incorrect. File: %s" % (colour_text(COLOUR_BOLD, instance_id), colour_text(COLOUR_GREEN, args[TITLE_EC2_FILE])))
                    continue

                # If we get past this point, then we have successfully obtained a password for the instance.

                args[TITLE_SERVER] = public_ip
                args[TITLE_PASSWORD] = plain_password
                # Note: Username is handled by get_user().
                # Assumed to always be 'administrator' for EC2 connections using a private key.
                if TITLE_DOMAIN in args:
                    del args[TITLE_DOMAIN]

                good = True
                break
            if end:
                break
    except Exception as e:
        print_error("Error resolving EC2 identifier (%s) to an active instance: %s" % (colour_text(COLOUR_BOLD, target), str(e)))
        good = False

    if not good:
        print_error("Unable to resolve target to a running EC2 instance secured with key file '%s'. Target: %s" % (colour_text(COLOUR_GREEN, args[TITLE_EC2_FILE]), colour_text(COLOUR_BOLD, target)))
        print_notice("The following properties are checked: %s, %s, %s, and %s" % (label_instance_id, label_public_ip, label_public_dns, label_tag_name))
    else:
        if label in (label_public_ip, label_public_dns):
            label_colour = COLOUR_GREEN
        else:
            label_colour = COLOUR_BOLD

        print_notice("Resolved target %s '%s' to EC2 instance '%s'." % (label, colour_text(label_colour, target), colour_text(COLOUR_BOLD, instance_id)))

    return good

def set_var(values, title, value, colour=COLOUR_BOLD, reportOverwrite=True):
    if title in values and value != values[title]:
        # Print a warning if a value is already set.
        # Don't bother raising a fuss if the same value has been specified twice.
        if reportOverwrite:
            print_warning("More than one %s specified in arguments: Replacing '%s' with '%s'" % (title, colour_text(colour, value), colour_text(colour, values[title])))
        else:
            print_warning("More than one %s specified in arguments. Using latest value." % colour_text(COLOUR_BOLD, title))
    values[title] = value

def translate_seconds(duration, add_and = False):
    modules = [("seconds", 60, None), ("minutes",60,None), ("hours",24,None), ("days",7,None), ("weeks",52,None), ("years",100,None), ("centuries",100,"century")]
    num = int(duration)
    i = -1
    c = -1

    times = []
    while i < len(modules) - 1:
        i += 1

        value = modules[i][1]
        mod_value = num % value
        num = num / modules[i][1]

        noun = modules[i][0]
        if mod_value == 1:
            if modules[i][2]:
                noun = modules[i][2]
            else:
                noun = re.sub("s$", "", noun)

        if mod_value:
            times.append("%s %s" % (mod_value, noun))

    if len(times) == 1:
        return " ".join(times)
    elif len(times) == 2:
        return ", ".join(reversed(times))
    else:
        # Oxford comma
        d = ", and "
        s = d.join(reversed(times))
        sl = s.split(d, len(times) - 2)
        return ", ".join(sl)

def validate_args(args):
    all_clear = True

    if TITLE_SERVER not in args:
        print_error("No server specified.")
        all_clear = False

    if TITLE_EC2_FILE in args and not get_ec2_cipher():
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
    good_env = validate_environment()

    args, good_args = process_args()

    if args.get(TITLE_EC2_FILE):
        # Must load modules outside of functions.
        try:
            import base64, boto3
            from Crypto.Cipher import PKCS1_v1_5
            from Crypto.PublicKey import RSA
        except ImportError as e:
            print_error("Error loading modules for EC2 password: %s" % str(e))
            good_args = False

    good_args = validate_args(args) and good_args

    if not good_args:
        print_usage("./rdp.py server [-d domain] [-D] [-e ec2-key-file] [-g HxW] [-h height] [-p password] [-P] [-u user] [-U] [-v] [-w width]")
        exit(1)

    if not good_env:
        exit(2)

    if TITLE_EC2_FILE in args and not set_ec2_info():
        # Unable to resolve EC2 name to an active instance.
        exit(3)

    command = process_switches(args)

    print_summary()

    if args.get(TITLE_VERBOSE, DEFAULT_VERBOSE):
        print_notice("Command: %s" % " ".join(command))

    time_start = time.time()

    try:
        p = subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)

        # Clean password from memory a bit.
        # It's not perfect, but it does axe at least a few instances of the password from a memory dump.
        # If you're really paranoid about password security, you should really be entering it yourself.
        # The password can't be found at the Python level if it's never entered there in the first place.
        if TITLE_PASSWORD in args:
            del args[TITLE_PASSWORD]
        if ENV_PASSWORD in os.environ:
            del os.environ[ENV_PASSWORD]
        del command

        # Run until the process ends.
        p.communicate()
        exit_code = p.returncode
    except KeyboardInterrupt:
        p.kill()
        exit_code = 130
    except OSError as e:
        print_error("OSError: %s" % e)
        exit_code = 1

    time_end = time.time()
    time_diff = time_end - time_start

    if (time_diff) > 60:
        # Print a summary of time for any session duration over a minute
        #  (this amount of time implies a connection that didn't just
        #   die with xfreerdp timing out when trying to connect)
        print_notice("RDP Session Duration: %s" % colour_text(COLOUR_BOLD, translate_seconds(time_diff)))

    exit(exit_code)
