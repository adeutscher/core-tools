#!/usr/bin/python

# Silly ping wrapper script.
# As opposed to using flat ping, this will give the user more live
#   statistics without having to Ctrl-C out and reset their counters
#   at the same time.
# In particular, I want to know my percentage of dropped pings per-ping.

from __future__ import print_function
import getopt, re, platform, socket, string, subprocess, sys, time

def colour_text(text, colour = None):
    colour = colour or COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def colour_green(text):
    # Lazy shorthand for the common habit of using green to highlight paths.
    return colour_text(text, COLOUR_GREEN)

def enable_colours(force = False):
    global COLOUR_BOLD
    global COLOUR_BLUE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_BOLD = '\033[1m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_BOLD = ''
        COLOUR_BLUE = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_OFF = ''
enable_colours()

MODE_NORMAL = 1
MODE_RELIABLE = 2
MODE_UNRELIABLE = 3

DEFAULT_STREAK_COUNT = 15

def hexit(exit_code):

    print("Usage: %s address [-c count] [-r] [-u] [streak_count]" % colour_green("./ping-stats.py"))
    print(" -r: Exit when a streak of successful pings reaches the streak count.")
    print(" -u: Exit when a streak of failed pings reaches the streak count.")
    print(" -c count: Limit the total number of packets sent.")
    print("           Will exit with a non-zero exit code if limit is reached")
    print("           while attempting a streak.")
    print(" -d: Debug mode. Print the raw output of ping command.")
    print(" -t: Tally mode. Always display a tally of successful pings.")
    print("Set streak count as an optional second argument. Default: %s" % colour_text(DEFAULT_STREAK_COUNT))

    exit(exit_code)

def main(cli_args):

    if cli_args == sys.argv:
        cli_args = cli_args[1:]

    mode = MODE_NORMAL
    reliable = unreliable = False
    count = 0
    count_raw = None
    count_have = False
    debug = False
    tally = False

    try:
        opts, operands = getopt.gnu_getopt(cli_args, "c:dhrtu")
    except Exception as e:
        print("Error parsing arguments: %s" % str(e))
        exit(1)

    for f, v in opts:
        if f == "-h":
            hexit(0)
        if f == '-r':
            reliable = True
            mode = MODE_RELIABLE
        elif f == '-u':
            unreliable = True
            mode = MODE_UNRELIABLE
        elif f == '-t':
            tally = True
        elif f == '-d':
            debug = True
        elif f == '-c':
            count_raw = v
            count_have = True

    # Error check
    error = False

    if reliable and unreliable:
        print("Cannot wait for reliable and unreliable pings at the same time.")
        error = True

    if not operands:
        print("No server specified.")
        error = True
    else:
        addr = operands[0]

        try:
            ip = socket.gethostbyname(addr)
        except socket.gaierror:
            print("Unable to resolve address: %s" % colour_text(addr, COLOUR_BLUE))
            error = True

    if count_have:
        try:
            count = int(count_raw)
            if count < 0:
                raise Exception()
        except:
            print("Bad number of packets to transmit. Must be a positive number (0 for unlimited)")
            count = 0
            error = True

    streak_count = DEFAULT_STREAK_COUNT
    if len(operands) > 1:
        try:
            streak_count = int(operands[1])
            if streak_count <= 0:
                # Without mods to getopts a negative operand actually can't even be used, but anyhow...
                print("Attempt number must be greater than zero. Provided: %s" % colour_text(streak_count))
                error = True
        except ValueError:
            print("Invalid attempt number: %s" % colour_text(operands[1]))
            error = True

    if (reliable or unreliable) and count and streak_count > count:

        if reliable:
            wording = "successful"
        else:
            wording = "unsuccessful"

        print("Ping limit of %s is less than desired streak of %s %s pings." % (colour_text(count), colour_text(streak_count), wording))
        error = True

    if error:
        hexit(1)

    return stats(addr, ip,
        mode=mode,
        streak=streak_count,
        limit=count,
        debug=debug,
        tally=tally
    )

def ping(server, debug = False):
    r = {}
    t = time.time()
    if platform.system() in ["Linux", "Darwin"]:
        # Unix platform
        # ToDo: Improve this check
        cmd=["ping", "-W1", "-c1", server]
    else:
        # Windows Environment (assumed)
        cmd=["ping", "-w", "1", "-n", "1", server]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    out = str(out).replace("\\n", "\n")

    # Calculate time lazily using python time rather than the time from ping.
    # This might result in some inaccurate numbers, but I think it's minor enough to let slide
    r["time"] = time.time() - t

    if debug:
        print(out)

    pattern="(Reply from [^:]+: bytes|\d+ bytes from)[^\n]+"
    l = re.search(pattern, str(out))
    if l and not p.returncode:
        r["success"] = True
        # Strip out the icmp_seq value because our implementation invokes a new
        #   ping process. icmp_seq will always be '1'.
        line = re.sub("((\d+ bytes|Reply) from [^:]+:|\s+(bytes|icmp_seq)=\d+)", "", l.group(0))
        line = line.replace("time=", "t=")
        r["line"] = re.sub("(\.[\d]{2})\d? ms", r"\1 ms", line)
    else:
        r["success"] = False

    return r

def stats(server, ip, **kwargs):

    mode = kwargs.get("mode", MODE_NORMAL)
    number = kwargs.get("streak", DEFAULT_STREAK_COUNT)
    limit = kwargs.get("limit", 0)
    debug = kwargs.get("debug", False)
    tally = kwargs.get("tally", False)

    total_pings = 0
    total_success = 0

    time_max = 0
    time_min = 0
    time_avg = 0

    recent_limit = 10

    # Draw a little "heartbeat" chart of how recent pinging is doing.
    chart = ''

    # Current time for final statistics
    t = time.time()

    # Track our streak of failed/succeeded pings
    streak_fail = 0
    streak_success = 0

    # Store desired exit code.
    exit_code = 0

    if server != ip:
        display_server = '%s (%s)' % (colour_text(server, COLOUR_BLUE), colour_text(ip, COLOUR_BLUE))
    else:
        display_server = colour_text(server, COLOUR_BLUE)


    # Announce
    reliability_check = mode in (MODE_RELIABLE, MODE_UNRELIABLE)
    if reliability_check:
        if mode == MODE_RELIABLE:
            word = colour_green("can")
        else:
            word = colour_text("cannot", COLOUR_RED)

        print("Waiting until %s %s be pinged %s times in a row." % (display_server, word, colour_text(number)))
        if limit:
            print("Will terminate unsuccessfully if we cannot do so after %s ping attempts." % colour_text(limit))
    elif limit:
        print("Ping count: %s" % colour_text(limit))

    try:
        continue_loop = True
        while continue_loop:
            r = ping(ip, debug)

            total_pings += 1
            if r.get("success", False):
                total_success += 1

            time_max = max(time_max, r["time"])
            time_min = min(time_min, r["time"])
            time_avg += ((r["time"] - time_avg) / total_pings)

            # Modify heartbeat chart
            if r["success"]:
                streak_fail = 0
                streak_success += 1

                chart += '^'
                colour = COLOUR_GREEN
                verb = 'reply'
                extra = '  %s' % r.get('line', '').strip()

                # Only bother announcing the number of successes in a row when testing for reliability.
                if mode == MODE_RELIABLE:
                    extra += ' (%s succeeded)' % colour_text("%d/%d" % (streak_success, number))
                elif mode == MODE_UNRELIABLE:
                    if tally:
                        extra += ' (%s failed, %s succeeded in a row)' % (colour_text("%d/%d" % (streak_fail, number)), colour_text(streak_success))
                    else:
                        extra += ' (%s failed)' % colour_text("%d/%d" % (streak_fail, number))
                elif tally:
                    extra += ' (%s succeeded in a row)' % colour_text(streak_success)

            else:
                streak_fail += 1
                streak_success = 0

                chart += '-'
                colour = COLOUR_RED
                verb = 'timeout'

                if mode == MODE_RELIABLE:
                    extra = ' (%s succeeded)' % colour_text("%d/%d" % (streak_success, number))
                elif mode == MODE_UNRELIABLE:
                    extra = ' (%s failed)' % colour_text("%d/%d" % (streak_fail, number))
                else:
                    extra = ' (%s failed in a row)' % colour_text(streak_fail)

            line = '%s  %s%s' % (colour_text(ip, COLOUR_BLUE), colour_text(verb, colour), extra)
            chart = chart[max(0, len(chart)-recent_limit):] # Trim chart

            display_chart = ''
            display_new = True
            for i in range(len(chart)):
                if not i or chart[i-1] != chart[i]:
                    display_chart += COLOUR_OFF
                if chart[i] == '^':
                    display_colour = COLOUR_GREEN
                elif chart[i] == '-':
                    display_colour = COLOUR_RED

                if display_colour:
                    display_chart += display_colour
                display_chart += chart[i]

            if len(chart):
                display_chart += COLOUR_OFF

            # Pad out the display
            for i in range(recent_limit - len(chart)):
                display_chart += '_'

            # Calculate percentage and colouring
            percentage = float(total_success) / total_pings * 100

            percentage_colour = COLOUR_GREEN
            if percentage <= 30:
                percentage_colour = COLOUR_RED
            elif percentage <= 60:
                percentage_colour = COLOUR_YELLOW
            percentage_text = "%6.02f%%" % percentage

            # Padding the count digits to avoid a bunch of relatively rapid format jumps.
            print("%03d/%03d %s  [%s]  %s" % (total_success, total_pings, colour_text(percentage_text, percentage_colour), display_chart, line))

            # This was originally one big assignment statement, but it was a pain to read.
            continue_loop = (not limit or total_pings < limit)
            if mode == MODE_RELIABLE and streak_success >= number:
                continue_loop = False
            elif mode == MODE_UNRELIABLE and streak_fail >= number:
                continue_loop = False

            if continue_loop:
                # If there is another loop upcoming, sleep for the remainder of a second that's left.
                time.sleep(max(0, 1-r["time"]))

    except KeyboardInterrupt:
        exit_code = 130

    if total_pings:

        if not exit_code and reliability_check and total_pings == limit and (
            (mode == MODE_RELIABLE and streak_success < number)
            or (mode == MODE_UNRELIABLE and streak_fail < number)
        ):
            # Set an exit code if we weren't able to get the required number of successful/failed pings within the limit.
            # (Do not override the exit code of a keyboard interrupt)
            exit_code = 1

        print("\n--- %s ping statistics ---" % display_server)
        # ping numbers in ping-like format
        print("%s packets transmitted, %d received, %.02f%% packet loss" % (total_pings, total_success, 100 - float(total_success) / total_pings * 100))
        # rtt stats. I don't worry about this as much as success percentage.
        print("rtt min/avg/max %.03f/%.03f/%.03f" % (time_min, time_avg, time_max))

    return exit_code

if __name__ == "__main__":
    exit_code = main(sys.argv)
    exit(exit_code)
