#!/usr/bin/python

# Silly ping wrapper script.
# As opposed to using flat ping, this will give the user more live
#   statistics without having to Ctrl-C out and reset their counters
#   at the same time.
# In particular, I want to know my percentage of dropped pings per-ping.

import getopt, re, socket, string, subprocess, sys, time

def colour_text(text, colour = None):
    colour = colour or COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def colour_green(text):
    return colour_text(text, COLOUR_GREEN)

def enable_colours(force = False):
    global COLOUR_BOLD
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_BOLD = '\033[1m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_BOLD = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_OFF = ''
enable_colours()

MODE_NORMAL = 1
MODE_RELIABLE = 2
MODE_UNRELIABLE = 3

def main(cli_args):

    if cli_args == sys.argv:
        cli_args = cli_args[1:]

    try:
        opts, operands = getopt.gnu_getopt(cli_args, "ru")
    except Exception as e:
        print "Error parsing arguments: %s" % str(e)
        exit(1)

    mode = MODE_NORMAL
    reliable = unreliable = False

    flags = [f for f,v in opts]
    if '-r' in flags:
        reliable = True
        mode = MODE_RELIABLE
    if '-u' in flags:
        unreliable = True
        mode = MODE_UNRELIABLE

    # Error check
    error = False

    if reliable and unreliable:
        print "Cannot wait for reliable and unreliable pings at the same time."
        error = True

    if not operands:
        print "No server specified."
        error = True
    else:
        addr = operands[0]

    number = 60
    if len(operands) > 1:
        try:
            number = int(operands[1])
            if number <= 0:
                # Without mods to getopts a negative operand actually can't even be used, but anyhow...
                print "Attempt number must be greater than zero. Provided: %s" % colour_text(number)
                error = True
        except ValueError:
            print "Invalid attempt number: %s" % colour_text(operands[1])
            error = True

    if error:
        exit(1)

    try:
        ip = socket.gethostbyname(addr)
    except socket.gaierror:
        print "Unable to resolve address: %s" % colour_green(addr)
        exit(2)

    stats(addr, ip, mode, number)

def ping(server):
    r = {}
    t = time.time()
    p = subprocess.Popen(["ping", "-W1", "-c1", server], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    # Calculate time lazily using python time rather than the time from ping.
    # This might result in some inaccurate numbers, but I think it's minor enough to let slide
    r["time"] = time.time() - t

    l = re.search("^\d+ bytes from.+$", out, re.MULTILINE)
    if l and not p.returncode:
        r["success"] = True
        # Strip out the icmp_seq value because our implementation invokes a new
        #   ping process. icmp_seq will always be '1'.
        r["line"] = re.sub("(\d+ bytes from [^:]+:|\s+icmp_seq=\d+)", "", l.group(0))
    else:
        r["success"] = False

    return r

def stats(server, ip, mode, number):

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

    # Announce
    if mode in (MODE_RELIABLE, MODE_UNRELIABLE):
        if mode == MODE_RELIABLE:
            word = colour_green("can")
        else:
            word = colour_text("cannot", COLOUR_RED)

        saddr = colour_green(server)
        if server != ip:
            saddr += ' (%s)' % colour_green(ip)

        print "Waiting until %s %s be pinged %s times in a row." % (saddr, word, colour_text(number))

    try:
        continue_loop = True
        while continue_loop:
            r = ping(ip)

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
                verb = 'response'
                extra = ': %s' % r.get('line', '').strip()

                # Only bother announcing the number of successes in a row when testing for reliability.
                if mode == MODE_RELIABLE:
                    extra += ' (%s succeeded)' % colour_text("%d/%d" % (streak_success, number))
                elif mode == MODE_UNRELIABLE:
                    extra += ' (%s failed)' % colour_text("%d/%d" % (streak_fail, number))

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
                    extra = ' (%s in a row)' % colour_text(streak_fail)

            line = '%s %s%s' % (colour_green(ip), colour_text(verb, colour), extra)
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
            print "[%03d/%03d %s][%s]: %s" % (total_success, total_pings, colour_text(percentage_text, percentage_colour), display_chart, line)

            continue_loop = mode == MODE_NORMAL or (
                (mode == MODE_RELIABLE and streak_success < number)
                or (mode == MODE_UNRELIABLE and streak_fail < number)
            )

            if continue_loop:
                # If there is another loop upcoming, sleep for the remainder of a second that's left.
                time.sleep(max(0, 1-r["time"]))

    except KeyboardInterrupt:
        pass

    if total_pings:
        if server != ip:
            display_server = "%s (%s)" % (server, ip)
        else:
            display_server = ip

        print "\n--- %s ping statistics ---" % display_server
        # ping numbers in ping-like format
        print "%s packets transmitted, %d received, %.02f%% packet loss" % (total_pings, total_success, 100 - float(total_success) / total_pings * 100)
        # rtt stats. I don't worry about this as much as success percentage.
        print "rtt min/avg/max %.03f/%.03f/%.03f" % (time_min, time_avg, time_max)

if __name__ == "__main__":
    main(sys.argv)
