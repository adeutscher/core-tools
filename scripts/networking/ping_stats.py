#!/usr/bin/python

# Ping wrapper script.
# As opposed to using flat ping, this will give the user more live
#   statistics without having to Ctrl-C out and reset their counters
#   at the same time.
# In particular, I want to know my percentage of dropped pings on a per-ping basis.
# This script has the capability to use TCP connections instead with the '-p' switch

from __future__ import print_function
import errno, getopt, re, platform, socket, string, subprocess, sys, time

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
    print(" -p port : Instead of using ICMP pings, scan on the specified TCP port.")
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
    port_raw = None
    port_have = False
    debug = False
    tally = False
    port = 0

    try:
        opts, operands = getopt.gnu_getopt(cli_args, "c:dhp:rtu")
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
        elif f == '-p':
            port_raw = v
            port_have = True
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
            print("Bad number of attempts to transmit. Must be a positive number (0 for unlimited)")
            count = 0
            error = True

    if port_have:
        try:
            port = int(port_raw)
            if port < 1 or port > 65535:
                raise Exception()
        except:
            print("Bad TCP port number. Must be an integer in the range of 1-65535")
            port = 0
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

    p = PingStatistics()
    p.server = addr
    p.ip = ip
    p.mode = mode
    p.streak = streak_count
    p.limit = count
    p.debug = debug
    p.tally = tally
    p.port = port

    p.run()

def translate_seconds(duration, add_and = False):
    modules = [("seconds", 60, None), ("minutes",60,None), ("hours",24,None), ("days",7,None), ("weeks",52,None), ("years",100,None), ("centuries",100,"century")]
    num = int(duration)
    i = -1
    c = -1

    times = []
    for i in range(len(modules)):

        noun = modules[i][0]
        value = modules[i][1]
        mod_value = num % value

        if mod_value == 1:
            if modules[i][2]:
                noun = modules[i][2]
            else:
                noun = re.sub("s$", "", noun)

        if mod_value:
            times.append("%s %s" % (mod_value, noun))

        num = int(num / modules[i][1])
        if not num:
            break # No more modules to process

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

class PingStatistics:

    def __get_debug(self):
        return self.__debug

    def __get_ip(self):
        return self.__ip

    def __get_mode(self):
        return self.__mode

    def __get_limit(self):
        return self.__limit

    def __get_port(self):
        return self.__port

    def __get_server(self):
        return self.__server

    def __get_streak(self):
        return self.__streak

    def __get_tally(self):
        return self.__tally

    def __init__(self):
        pass

    def __set_debug(self, value):
        self.__debug = value

    def __set_ip(self, value):
        self.__ip = value

    def __set_limit(self, value):
        self.__limit = value

    def __set_mode(self, value):
        self.__mode = value

    def __set_port(self, value):
        self.__port = value

    def __set_server(self, value):
        self.__server = value

    def __set_streak(self, value):
        self.__streak = value

    def __set_tally(self, value):
        self.__tally = value

    debug = property(__get_debug, __set_debug)
    ip = property(__get_ip, __set_ip)
    limit = property(__get_limit, __set_limit)
    port = property(__get_port, __set_port)
    server = property(__get_server, __set_server)
    streak = property(__get_streak, __set_streak)
    tally = property(__get_tally, __set_tally)

    def do_icmp(self):
        r = {}
        if platform.system() in ["Linux", "Darwin"]:
            # Unix platform
            # ToDo: Improve this check
            cmd=["ping", "-W1", "-c1", self.server]
        else:
            # Windows Environment (assumed)
            cmd=["ping", "-w", "1", "-n", "1", self.server]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        out = str(out).replace("\\n", "\n")

        if self.debug:
            print(out)

        pattern=r"(Reply from [^:]+: bytes|\d+ bytes from)[^\n]+"
        l = re.search(pattern, str(out))

        if not l or p.returncode:
            r['result'] = 'timeout'
            return r

        r['success'] = True
        r['result'] = 'reply'
        # Strip out the icmp_seq value because our implementation invokes a new
        #   ping process. icmp_seq will always be '1'.
        line = re.sub("((\d+ bytes|Reply) from [^:]+:|\s+(bytes|icmp_seq)=\d+)", "", l.group(0))
        line = line.replace("time=", "t=")
        r["line"] = re.sub("(\.[\d]{2})\d? ms", r"\1 ms", line)

        return r

    def do_tcp(self):

        r = {
            'line': 'TCP/%s' % self.port
        }

        time_start = time.time()
        while True:

            # Note: Python2 socket objects do not have an __exit__ method,
            #         so with/__exit__ cannot be used.
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            # https://www.tutorialspoint.com/python_penetration_testing/python_penetration_testing_network_scanner.htm
            conn_result = s.connect_ex((self.server, self.port))
            time_duration = time.time() - time_start

            if self.debug:
                print('Connection response (%.02f seconds): %s' % (time_duration, conn_result))

            # If connect_ex() returned 11 (EAGAIN), then continue the loop.
            # Give up after 10s. If the traffic is being dropped, then
            #   the loop will go on for too long (possibly endless?)
            # A value of 10s was chosen to distinguish between a connection that's
            #   taking a while to time out and something that's being intentionally dropped.
            # This was determined by comparing two addresses:
            #   * Unused IP on local and remote networks (3-6ss to get a 113/EHOSTUNREACH)
            #     * The 6s timeouts are less common than the 3s ones.
            #   * Local address with a DROP rule in effect against the pinging host would take much too long.
            if conn_result == errno.EAGAIN and time_duration < 10:
                continue

            r['success'] = conn_result == 0

            if r['success']:
                # Successfully established a connection.
                r['result'] = 'open'

                # Possible future improvement - could take a leaf from nmap here and do some basic operation well-known ports for information.
                # Probably won't implement this in any rush, though. The purpose of this script is on confirming the status of known hosts, not in exploring unknown hosts.
            elif conn_result == errno.ECONNREFUSED:
                # Server was not listening on the target port.

                # This response could also happen if iptables REJECTs the connection.
                #   nmap can't or doesn't distinguish between the two causes, so I'm not too worried distinguishing either
                r['result'] = 'closed'
            elif conn_result == errno.EHOSTUNREACH:
                # Socket gave up.
                r['result'] = 'unreachable'
            else:
                # Untracked error, or the script gave up.
                # This could happen if the ping gets hit by a DROP target in iptables
                r['result'] = 'timeout'

            s.close()
            break
        return r

    def ping(self):
        t = time.time()

        if self.port:
            method = self.do_tcp
        else:
            method = self.do_icmp

        r = method()
        # Calculate time lazily using python time rather than the time from ping.
        # This might result in some inaccurate numbers, but I think it's minor enough to let slide
        r["time"] = time.time() - t
        return r

    def run(self):

        start_time = time.time()

        total_pings = 0
        total_success = 0

        time_max = 0
        time_min = 0
        time_avg = 0

        # Draw a little "heartbeat" chart of how recent pinging is doing.
        chart = ''

        recent_limit = 10

        # Current time for final statistics
        t = time.time()

        # Track our streak of failed/succeeded pings
        streak_fail = 0
        streak_success = 0

        # Store desired exit code.
        exit_code = 0

        if self.server != self.ip:
            display_server = '%s (%s)' % (colour_text(self.server, COLOUR_BLUE), colour_text(self.ip, COLOUR_BLUE))
        else:
            display_server = colour_text(self.server, COLOUR_BLUE)

        # Announce

        if self.port:
            wording_method = 'reached over the TCP/%d port' % self.port
            wording_noun = 'TCP attempt'
        else:
            wording_noun = 'Ping'
            wording_method = 'pinged'

        reliability_check = self.mode in (MODE_RELIABLE, MODE_UNRELIABLE)
        if reliability_check:
            if self.mode == MODE_RELIABLE:
                word = colour_green("can")
            else:
                word = colour_text("cannot", COLOUR_RED)

            print("Waiting until %s %s be %s %s times in a row." % (display_server, word, wording_method, colour_text(self.streak)))
            if self.limit:
                print("Will terminate unsuccessfully if we cannot do so after %s %s attempts." % (colour_text(self.limit), wording_noun))
        elif self.limit:
            print("%s attempt count: %s" % (wording_noun, colour_text(self.limit)))

        try:
            continue_loop = True
            while continue_loop:
                r = self.ping()

                total_pings += 1
                if r.get("success", False):
                    total_success += 1

                time_max = max(time_max, r['time'])
                time_min = min(time_min, r['time'])
                time_avg += ((r['time'] - time_avg) / total_pings)

                verb = r.get('result', 'unknown')
                line = r.get('line', '').strip()
                extra = ''

                # Modify heartbeat chart
                if r.get('success'):
                    streak_fail = 0
                    streak_success += 1

                    chart += '^'
                    colour = COLOUR_GREEN

                    # Only bother announcing the number of successes in a row when testing for reliability.
                    if self.mode == MODE_RELIABLE:
                        extra = ' (%s succeeded)' % colour_text("%d/%d" % (streak_success, self.streak))
                    elif self.mode == MODE_UNRELIABLE:
                        if self.tally:
                            extra = '(%s failed, %s succeeded in a row)' % (colour_text('%d/%d' % (streak_fail, self.streak)), colour_text(streak_success))
                        else:
                            extra = '(%s failed)' % colour_text('%d/%d' % (streak_fail, self.streak))
                    elif self.tally:
                        extra = '(%s succeeded in a row)' % colour_text(streak_success)

                else:
                    streak_fail += 1
                    streak_success = 0

                    chart += '-'
                    colour = COLOUR_RED

                    if self.mode == MODE_RELIABLE:
                        extra = '(%s succeeded)' % colour_text('%d/%d' % (streak_success, self.streak))
                    elif self.mode == MODE_UNRELIABLE:
                        extra = '(%s failed)' % colour_text('%d/%d' % (streak_fail, self.streak))
                    else:
                        extra = '(%s failed in a row)' % colour_text(streak_fail)

                line_output = '%s  %s ' % (colour_text(self.ip, COLOUR_BLUE), colour_text(verb, colour))
                if line:
                    line_output += ' %s' % line
                if extra:
                    line_output += ' %s' % extra
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
                print("%03d/%03d %s  [%s]  %s" % (total_success, total_pings, colour_text(percentage_text, percentage_colour), display_chart, line_output))

                # This was originally one big assignment statement, but it was a pain to read.
                continue_loop = (not self.limit or total_pings < self.limit)
                if self.mode == MODE_RELIABLE and streak_success >= self.streak:
                    continue_loop = False
                elif self.mode == MODE_UNRELIABLE and streak_fail >= self.streak:
                    continue_loop = False

                if continue_loop:
                    # If there is another loop upcoming, sleep for the remainder of a second that's left.
                    time.sleep(max(0, 1-r["time"]))

        except KeyboardInterrupt:
            exit_code = 130

        if not total_pings:
            return exit_code

        end_time = time.time()

        if reliability_check:
            print("\nDuration:", translate_seconds(end_time - start_time))

        if not exit_code and reliability_check and total_pings == self.limit and (
            (self.mode == MODE_RELIABLE and streak_success < self.streak)
            or (self.mode == MODE_UNRELIABLE and streak_fail < self.streak)
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
