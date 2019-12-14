#!/usr/bin/env python

from __future__ import print_function
import getopt, getpass, os, re, subprocess, sys

# Defaults

DEFAULT_CHANNEL = 7

# Channel Limits
CHANNEL_MIN = 1
CHANNEL_MAX = 11

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
TITLE_BRIDGE = "bridge"
TITLE_CHANNEL = "channel"
TITLE_INTERFACE = "interface"
TITLE_PASSWORD = "password"
TITLE_SSID = "ssid"
TITLE_IS_WEP = "wep"
TITLE_IS_JOIN = "join"

def _print_message(header_colour, header_text, message, stderr=False):
    f=sys.stdout
    if stderr:
        f=sys.stderr
    print("%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message), file=f)

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def do_access_point(args):
    config_file = make_access_point_config(args)
    if error_count:
        print_error("Problem making config file at %s." % colour_text(config_file, COLOUR_GREEN))
        exit(1)

    run_command(["hostapd", config_file], True, False)

def do_join_wireless(args):
    config_file = make_join_wireless_config(args)
    if error_count:
        print_error("Problem making config file at %s" % colour_text(config_file, COLOUR_GREEN))
        exit(1)
    run_command(["wpa_supplicant", "-i", args.get(TITLE_INTERFACE), "-c", config_file], True, False)

def do_script(cli_args):

    args, good_args = process_args(cli_args)

    good_args = validate_args(args) and good_args

    if not good_args:
        print_usage("./access-point.py [-j] [-b bridge] [-B] [-c channel] [-i interface] [-I] [-p password] [-P] [-s SSID] [-S] [-w]")
        exit(1)

    print_summary(args)

    if args.get(TITLE_IS_WEP, False) and args.get(TITLE_PASSWORD, None):
        # A final warning or two about WEP, whether we are hosting or joining.
        print_warning(colour_text("!!! WEP IS HILARIOUSLY INSECURE !!!"))
        print_warning("This script should only be used as part of a demonstration of how easy it is is to break into a WEP network.")

    if args.get(TITLE_IS_JOIN, False):
        do_join_wireless(args)
    else:
        do_access_point(args)

def is_interface(candidate):
    return candidate in os.listdir('/sys/class/net')

def make_access_point_config(args):
    config = "/tmp/hostapd-%s-temp.conf" % args[TITLE_INTERFACE]
    error = False
    try:
        # We only want our current user to be able to see this.
        os.umask(077)
        with open(config, "w") as f:
            f.write("""
# Common values
ssid=%s
interface=%s
bridge=%s
channel=%d
hw_mode=g
driver=nl80211

logger_stdout=-1
logger_stdout_level=2
max_num_sta=5

ctrl_interface=/var/run/hostapd
ctrl_interface_group=wheel
""" % (args[TITLE_SSID], args[TITLE_INTERFACE], args[TITLE_BRIDGE], args[TITLE_CHANNEL]))
            if(args.get(TITLE_IS_WEP, False)):
                f.write("""
# WEP Options
# Reminder: WEP IS A BAD IDEA, FOR DEMO PURPOSES ONLY

wep_default_key=1
auth_algs=3
wep_key1="%s"
wep_key_len_broadcast="%d"
wep_key_len_unicast="%d"
wep_rekey_period=300

""" % (args[TITLE_PASSWORD], len(args[TITLE_PASSWORD]), len(args[TITLE_PASSWORD])))
            elif args.get(TITLE_PASSWORD, None):
                # WPA
                f.write("""
wpa=2
auth_algs=1
rsn_pairwise=CCMP
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP CCMP
wpa_passphrase=%s
""" % args[TITLE_PASSWORD])
            f.close()

    except OSError as e:
        print_error(e)
    return config

def make_join_wireless_config(args):
    config = "/tmp/wpa-supplicant-%s-temp.conf" % args[TITLE_INTERFACE]
    error = False
    try:
        # We only want our current user to be able to see this.
        os.umask(077)
        with open(config, "w") as f:
            f.write("""
ctrl_interface=/var/run/wpa_supplicant_%s
ctrl_interface_group=wheel""" % args.get(TITLE_INTERFACE))

            if not args.get(TITLE_PASSWORD, None):
                f.write("""
network={
  ssid="%s"
  key_mgmt=NONE
}
""" % args.get(TITLE_SSID))
            else:

                if re.match('^([a-f0-9]{2}[:|-]){5}[a-f0-9]{2}$', args.get(TITLE_SSID)):
                    ssid_string="bssid=%s" % args.get(TITLE_SSID)
                else:
                    # Regular SSID
                    ssid_string="ssid=\"%s\"" % args.get(TITLE_SSID)

                if args.get(TITLE_IS_WEP, False):
                    f.write("""
network={
  %s
  key_mgmt=NONE
  wep_key0="%s"
  wep_tx_keyidx=0
}
""" % (ssid_string, args.get(TITLE_PASSWORD)))
                else:
                    # WPA2
                    f.write("""
network={
  %s
  proto=WPA2
  psk="%s"
  priority=5
}
""" % (ssid_string, args.get(TITLE_PASSWORD)))

    except OSError as e:
        print_exception(e)
    return (config, error)

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, "Error", message)

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

def print_summary(args):

    print_notice("SSID: %s%s%s" % (COLOUR_BOLD, args[TITLE_SSID], COLOUR_OFF))
    if args.get(TITLE_IS_JOIN, False):
        verbword = "Joining"
        nounword = "network"
        closer = "."
    else:
        verbword = "Hosting"
        nounword = "access point"
        closer = " (Channel %s%d%s)." % (COLOUR_BOLD, args[TITLE_CHANNEL], COLOUR_OFF)

    if args.get(TITLE_PASSWORD, None):
        # An access point under this script will never by non-open, non-WEP, and non-WPA at the same time..
        if args.get(TITLE_IS_WEP, False):
            # Raise warning flags about WEP wherever possible.
            print_warning("%s a WEP-\"secured\" %s." % (verbword, nounword))
        else:
            print_notice("%s a WPA2 %s." % (verbword, nounword))
    else:
        print_notice("%s an open %s%s" % (verbword, nounword, closer))

    if args.get(TITLE_IS_JOIN, False):
        print_notice("Joining network using the %s%s%s interface." % (COLOUR_BLUE, args[TITLE_INTERFACE], COLOUR_OFF))
    else:
        print_notice("The %s%s%s interface will be attached to the %s%s%s bridge." % (COLOUR_BLUE, args[TITLE_INTERFACE], COLOUR_OFF, COLOUR_GREEN, args[TITLE_BRIDGE], COLOUR_OFF))

def print_usage(message):
    _print_message(COLOUR_PURPLE, "Usage", message)

def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message)

def process_args(cli_args):
    values = {}

    # Errors that have not been resolved.
    good_args = True

    try:
        opts, operands = getopt.gnu_getopt(cli_args, "b:Bc:i:Ijp:Ps:Sw")
    except getopt.GetoptError as e:
        print_error(e)
        exit(1)

    for opt,optarg in opts:
        if opt == "-b":
            if validate_bridge_interface(optarg, TITLE_BRIDGE):
                set_var(values, TITLE_BRIDGE, optarg)
            else:
                good_args = False
        elif opt == "-B":
            # Manual bridge input
            record_var(values, TITLE_BRIDGE, COLOUR_BOLD, validate_bridge_interface, False)
        elif opt == "-c":
            try:
                if int(optarg) >= CHANNEL_MIN and int(optarg) <= CHANNEL_MAX:
                    set_var(values, TITLE_CHANNEL, int(optarg))
                else:
                    print_error("Channel must be between %d and %d inclusive." % (CHANNEL_MIN, CHANNEL_MAX))
                    good_args = False
            except ValueError:
                print_error("Channel must be an integer. Given: %s" % optarg)
                good_args = False
        elif opt == "-i":
            if validate_wireless_interface(optarg, TITLE_INTERFACE):
                set_var(values, TITLE_INTERFACE, optarg)
            else:
                good_args = False
        elif opt == "-I":
            # Manual interface input
            record_var(values, TITLE_INTERFACE, COLOUR_BOLD, validate_wireless_interface, False)
        elif opt == "-j":
            values[TITLE_IS_JOIN] = True
        elif opt == "-p":
            # Password has no immediate validation,
            # as WEP and WPA have different accepted lengths.
            set_var(values, TITLE_PASSWORD, optarg, COLOUR_BOLD, False)
        elif opt == "-P":
            # Manual password input
            record_var(values, TITLE_PASSWORD, COLOUR_BOLD, False, False)
        elif opt == "-s":
            if validate_ssid(optarg, TITLE_SSID):
                set_var(values, TITLE_SSID, optarg)
            else:
                good_args = False
        elif opt == "-S":
            # Manual domain input
            record_var(values, TITLE_SSID, COLOUR_BOLD, validate_ssid, False)
        if opt == "-w":
            print_warning("Enabling WEP mode.")
            values[TITLE_IS_WEP] = 1

    # If no values were set, load in environment variables or defaults instead.
    # Doing this after loading because of the override notice.
    if TITLE_BRIDGE not in values:
        values[TITLE_BRIDGE] = os.environ.get("AP_BRIDGE")
    if TITLE_CHANNEL not in values:
        values[TITLE_CHANNEL] = os.environ.get("AP_CHANNEL", DEFAULT_CHANNEL)
    if TITLE_INTERFACE not in values:
        values[TITLE_INTERFACE] = os.environ.get("AP_INTERFACE")
    if TITLE_PASSWORD not in values:
        values[TITLE_PASSWORD] = os.environ.get("AP_PASSWORD")
    if TITLE_SSID not in values:
        values[TITLE_SSID] = os.environ.get("AP_SSID")

    return values, good_args

def record_var(values, title, colour=COLOUR_BOLD, validator=None, reportOverwrite=True):
    temp = ""
    while not temp:
        temp = getpass.getpass("Enter %s: " % title)
        if not temp:
            continue # Immediately loop again if empty.

        # Validation, if provided.
        if validator and not validator(temp, title):
            # Validator returned an error.
            temp=""
    set_var(values, title, temp, colour, reportOverwrite)

def run_command(command_list, sudo_required=False, ctrl_c_error=True):
    ret = 0
    try:
        if sudo_required and os.geteuid():
            print_notice("We are not %s, so %s will be run through %s." % (colour_text("root", COLOUR_RED), colour_text(command_list[0], COLOUR_BLUE), colour_text("sudo", COLOUR_BLUE)))
            command_list.insert(0, "sudo")

        p = subprocess.Popen(command_list, stdout=sys.stdout, stderr=sys.stderr)
        p.communicate()
        ret = p.returncode
        if ret < 0:
            ret = 1
    except KeyboardInterrupt:
        if ctrl_c_error:
            ret = 130
    except OSError as e:
        print_exception(e)
        ret = 1
    exit(ret)

def set_var(values, title, value, colour=COLOUR_BOLD, reportOverwrite=True):
    if title in values and value != values[title]:
        # Print a warning if a value is already set.
        # Don't bother raising a fuss if the same value has been specified twice.
        if reportOverwrite:
            print_warning("More than one %s specified in arguments: Replacing '%s' with '%s'" % (title, colour_text(value, colour), colour_text(values[title], colour)))
        else:
            print_warning("More than one %s specified in arguments. Using latest value." % title)
    values[title] = value

def validate_args(args):
    all_clear = True

    elements = [TITLE_SSID, TITLE_INTERFACE]
    command_needed = "hostapd"
    if args.get(TITLE_IS_JOIN, False):
        command_needed = "wpa_supplicant"
    else:
        # Only check for a bridge setting if we are hosting.
        elements.append(TITLE_BRIDGE)

    all_clear = all_clear and validate_command(command_needed)

    for t in elements:
        if not args.get(t, None):
            print_error("No %s specified." % t)
            all_clear = False
    if args.get(TITLE_PASSWORD, None):
        # An access point will never by non-open, non-WEP, and non-WPA.
        if args.get(TITLE_IS_WEP, False):
            # A WEP access point may have either 5 or 13 characters.
            if len(args[TITLE_PASSWORD]) != 5 and len(args[TITLE_PASSWORD]) != 13:
                print_error("WEP key must be 5 or 13 characters (given key was %s characters)." % colour_text(len(args[TITLE_PASSWORD])))
                all_clear = False
        else:
            # A WPA2 access point may have a passphrase between 8 and 63 characters (inclusive).
            if len(args[TITLE_PASSWORD]) < 8 or len(args[TITLE_PASSWORD]) > 63:
                print_error("A WPA2 access point may have a passphrase between 8 and 63 characters in length (given key was %s characters).)" % colour_text(len(args[TITLE_PASSWORD])))
                all_clear = False
    elif args.get(TITLE_IS_WEP, False):
        # Password is None, but WEP is enabled.
        # Rather than make the network entirely open, raise an error.
        print_error("WEP option was enabled, but password is empty.")
        all_clear = False
    return all_clear

def validate_bridge_interface(candidate, title):
    return validate_interface(candidate, title, "bridge")

def validate_command(command):
    all_clear = True
    if not which(command):
        print_error("%s%s%s is not found in PATH." % (COLOUR_BLUE, command, COLOUR_OFF))
        all_clear = False
    return all_clear

def validate_interface(candidate, title, subtype=None):
    if not is_interface(candidate):
        print_error("%s is not a network interface on this system." % candidate)
        return False
    if subtype and not os.path.isdir('/sys/class/net/%s/%s' % (candidate, subtype)):
        print_error("%s is not a %s interface." % (candidate, subtype))
        return False
    return True

def validate_wireless_interface(candidate, title):
    return validate_interface(candidate, title, "wireless")

def validate_ssid(candidate, title):
    if not candidate:
        print_error("Empty %s value." % title)
        return False
    max_len=32
    if len(candidate) > max_len:
        print_error("SSID cannot be more than %s characters long (requested SSID was %s characters)." % (colour_text(max_len), colour_text(len(candidate))))
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
        for path in os.environ.get("PATH", "").split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

if __name__ == "__main__":
    do_script(sys.argv)
