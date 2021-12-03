#!/usr/bin/env python

# General
from getopt import gnu_getopt
import logging
import sys # Argument Parsing
# Note: Intentionally not using time.perf_counter to allow for Python2.
from time import sleep, time

# ICMP support
from platform import system as platform
from subprocess import Popen as cmd, PIPE as pipe
from re import search, sub

# TCP Support
import errno, socket

def _build_logger(label, err = None, out = None):
    obj = logging.getLogger(label)
    obj.setLevel(logging.DEBUG)
    # Err
    err_handler = logging.StreamHandler(err or sys.stderr)
    err_filter = logging.Filter()
    err_filter.filter = lambda record: record.levelno >= logging.WARNING
    err_handler.addFilter(err_filter)
    obj.addHandler(err_handler)
    # Out
    out_handler = logging.StreamHandler(out or sys.stdout)
    out_filter = logging.Filter()
    out_filter.filter = lambda record: record.levelno < logging.WARNING
    out_handler.addFilter(out_filter)
    obj.addHandler(out_handler)
    return obj

logger = _build_logger('ping_stats')

def _colour_green(text):
    # Lazy shorthand for the common habit of using green to highlight paths.
    return _colour_text(text, COLOUR_GREEN)

def _colour_text(text, colour = None):
    colour = colour or COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)

def _enable_colours(force = None):
    global COLOUR_BOLD
    global COLOUR_BLUE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_OFF
    if force == True or (force is None and sys.stdout.isatty()):
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
_enable_colours()

def _translate_result(result):
    if result == RESULT_SUCCESS:
        return 'success'
    if result == RESULT_TIMEOUT:
        return 'timeout'
    if result == RESULT_CLOSED:
        return 'closed'
    if result == RESULT_UNREACHABLE:
        return 'unreachable'

'''
Translate seconds to something more human-readable
'''
def _translate_seconds(duration):

    modules = [
        ('seconds', 60),
        ('minutes',60),
        ('hours',24),
        ('days',7),
        ('weeks',52),
        ('years',100)
    ]

    num = max(0, int(duration))

    if not num:
        # Handle empty
        return '0 %s' % modules[0][0]

    times = []
    for i in range(len(modules)):

        noun, value = modules[i]
        mod_value = num % value

        if mod_value == 1:
            noun = sub('s$', '', noun)

        if mod_value:
            times.append('%s %s' % (mod_value, noun))

        num = int(num / value)
        if not num:
            break # No more modules to process

    if len(times) == 1:
        return ' '.join(times)
    elif len(times) == 2:
        return ', '.join(reversed(times))
    else:
        # Oxford comma
        d = ', and '
        s = d.join(reversed(times))
        sl = s.split(d, len(times) - 2)
        return ', '.join(sl)
MODE_RELIABLE = 0x01
MODE_UNRELIABLE = 0x02

RESULT_SUCCESS = 1
RESULT_TIMEOUT = 2
RESULT_CLOSED = 3
RESULT_UNREACHABLE = 4

DEFAULT_STREAK_COUNT = 10

class PingContext:
    def __init__(self):
        # Count success tallies
        self.total = self.total_success = 0
        # Track our streak of failed/succeeded pings
        self.streak_fail = self.streak_success = 0
        # Track time stats
        self.time_max = self.time_min = self.time_avg = 0
        self.time_end = self.time_start = 0

def do_icmp(**kwargs):

    target = kwargs.get('ip')
    debug = kwargs.get('debug', False)

    if platform() in ['Linux', 'Darwin']:
        # Unix platform
        # ToDo: Improve this check
        cmd_args=['ping', '-W1', '-c1', target]
    else:
        # Windows Environment (assumed)
        cmd_args=['ping', '-w', '1', '-n', '1', target]
    p = cmd(cmd_args, stdout=pipe, stderr=pipe)
    out, err = p.communicate()
    out = str(out).replace('\\n', '\n')

    if debug:
        logger.debug(out)

    result = {}

    pattern=r'(Reply from [^:]+: bytes|\d+ bytes from)[^\n]+'
    l = search(pattern, str(out))

    if not l or p.returncode:
        # Not successful, immediately return
        result = RESULT_TIMEOUT
        return result, None, None

    # If we got past without an error, then the ping was successful.
    result = RESULT_SUCCESS
    display = 'reply'

    # Strip out the icmp_seq value because our implementation invokes a new
    #   ping process. icmp_seq will always be '1'.
    line = sub('((\d+ bytes|Reply) from [^:]+:|\s+(bytes|icmp_seq)=\d+)', '', l.group(0))
    line = line.replace('time=', 't=')
    line = sub('(\.[\d]{2})\d? ms', r'\1 ms', line)
    return result, display, line

def do_tcp(**kwargs):

    target = kwargs.get('ip')
    port = kwargs.get('port')
    debug = kwargs.get('debug', False)

    line = 'TCP/%s' % port
    display = None

    time_start = time()

    while True:
        # Note: Python2's socket objects do not have an __exit__ method,
        #         so with/__exit__ cannot be used if this script is to be
        #         usable on the older version.
        s = get_tcp_socket()
        try:
            # https://www.tutorialspoint.com/python_penetration_testing/python_penetration_testing_network_scanner.htm
            result_conn = s.connect_ex((target, port))
            time_duration = time() - time_start

            if debug:
                logger.debug('Connection result (%.02f seconds): %s' % (time_duration, result_conn))

            # If connect_ex() returned 11 (EAGAIN), then continue the loop.
            # Give up after 10s. If the traffic is being dropped, then
            #   the loop will go on for too long (possibly endless?)
            # A value of 10s was chosen to distinguish between a connection that's
            #   taking a while to time out and something that's being intentionally dropped.
            # This was determined by comparing two addresses:
            #   * Unused IP on local and remote networks (3-6ss to get a 113/EHOSTUNREACH)
            #     * The 6s timeouts are less common than the 3s ones.
            #   * Local address with a DROP rule in effect against the pinging host would take much too long.
            if result_conn == errno.EAGAIN and time_duration < 10:
                continue

            if result_conn == 0:
                # Successfully established a connection.
                result = RESULT_SUCCESS
                display = 'open'

                # Possible future improvement - could take a leaf from nmap here
                #   and do some basic operation well-known ports for information.
                # Probably won't implement this in any rush, though.
                # The purpose of this script is to confirm the basic status of known hosts.
                # It is not made for exploring unknown hosts.
            elif result_conn == errno.ECONNREFUSED:
                # Server was not listening on the target port.

                # This result could also happen if iptables REJECTs the connection.
                #   nmap can't or doesn't distinguish between the two causes, so I'm not too worried distinguishing either
                result = RESULT_CLOSED

            elif result_conn == errno.EHOSTUNREACH:
                # Socket gave up.
                # This can come about with a timeout on a resource on the
                #  same collision domain as the machine running this script.

                # Unreachable should be distinguished from
                #  an unreachable result from an ambiguous timeout
                result = RESULT_UNREACHABLE

            else:
                # Untracked error, or the script gave up.
                # This could happen if the ping gets hit by a DROP target in iptables
                result = RESULT_TIMEOUT
        finally:
            s.close()
        break
    return result, display, line

'''
Get display phrasing for target
'''
def get_target(**kwargs):

    # Shorthand
    addr = kwargs.get('addr')
    ip = kwargs.get('ip')

    if addr != ip:
        return '%s (%s)' % (_colour_text(addr, COLOUR_BLUE), _colour_text(ip, COLOUR_BLUE))
    else:
        return _colour_text(addr, COLOUR_BLUE)

def get_tcp_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    return s

def main(args_raw):
    valid, args = parse_args(args_raw)

    if not valid:
        return 1

    if 'port' in args:
        args['callback'] = do_tcp
    else:
        args['callback'] = do_icmp
    # If another developer wants to make their own callback, then they will have
    #  to edit main or provide their own callback to a direct call of run().

    # Track statistics in an object that will be passed
    ctx = PingContext()

    print_args(**args)

    exit_code = 0
    try:
        result = run(ctx, **args)
    except KeyboardInterrupt:
        # Unlike ping, always return exit code 130
        # Inner catch here in order to display results after cancelling
        exit_code = 130
    ctx.time_end = time()

    if not print_results(args, ctx, exit_code):
        return 1

    return exit_code

def parse_args(args_raw):

    def hexit(hexit_code):

        logger.info('Usage: %s address [-c count] [-r] [-u] [streak_count]' % _colour_green('./ping-stats.py'))
        logger.info(' -r: Exit when a streak of successful pings reaches the streak count.')
        logger.info(' -u: Exit when a streak of failed pings reaches the streak count.')
        logger.info(' -p port : Instead of using ICMP pings, scan on the specified TCP port.')
        logger.info(' -c count: Limit the total number of packets sent.')
        logger.info('           Will exit with a non-zero exit code if limit is reached')
        logger.info('           while attempting a streak.')
        logger.info(' -d: Debug mode. Print the raw output of ping command.')
        logger.info(' -t: Tally mode. Always display a tally of successful pings.')
        logger.info(' -i seconds: Interval time between pings (Default: 1)')
        logger.info('Set streak count as an optional second argument. Default: %s' % _colour_text(DEFAULT_STREAK_COUNT))

        exit(hexit_code)

    def validate_int(value_raw, label, expr = lambda i: i > 0, msg = None):
        try:
            value_parsed = int(value_raw)
            if not expr(value_parsed):
                raise ValueError()
            return True, value_parsed
        except ValueError:
            logger.error(msg or 'Invalid %s: %s' % (label, value_raw))
            return False, None

    # Value-tracking

    args = { 'mode': 0 }

    try:
        opts, operands = gnu_getopt(args_raw, 'c:dhi:p:rtu')
    except Exception as e:
        logger.error('Error parsing arguments: %s' % str(e))
        hexit(1)

    # Error check
    error = False

    for arg, value in opts:
        if arg == '-h':
            hexit(0)

        if arg == '-c':
            # Count
            valid, value = validate_int(value, 'count')
            error = error or not valid
            if valid:
                args['count'] = value
        elif arg == '-d':
            # Debug
            args['debug'] = True
        elif arg == '-i':
            # Interval
            valid, value = validate_int(value, 'interval')
            error = error or not valid
            if valid:
                args['interval'] = value
        elif arg == '-p':
            # Port
            valid, value = validate_int(value, 'port', lambda i: i > 0 and i <= 65535, 'Bad TCP port number. Must be an integer in the range of 1-65535')
            error = error or not valid
            if valid:
                args['port'] = value
        elif arg == '-r':
            # Reliable-mode
            args['mode'] |= MODE_RELIABLE
        elif arg == '-t':
            # Tally
            args['tally'] = True
        elif arg == '-u':
            # Unreliable-mode
            args['mode'] |= MODE_UNRELIABLE

    if args['mode'] == MODE_RELIABLE | MODE_UNRELIABLE:
        # Reliable-mode and unreliable-mode are mutually exclusive
        logger.error('Cannot wait for reliable and unreliable pings at the same time.')
        error = True

    if not operands:
        logger.error('No target server specified.')
        error = True
    else:
        args['addr'] = operands[0]

        try:
            args['ip'] = socket.gethostbyname(args['addr'])
        except socket.gaierror:
            logger.error('Unable to resolve address: %s' % _colour_text(args['addr'], COLOUR_BLUE))
            error = True

    if args['mode'] & (MODE_RELIABLE | MODE_UNRELIABLE):
        if len(operands) > 1:
            valid, streak = validate_int(operands[-1], 'attempt count', lambda i: i > 0)
            error = error or not valid
            if valid:
                args['streak'] = streak
        else:
            streak = DEFAULT_STREAK_COUNT

        count = args.get('count')

        if count and count < streak:
            logger.error('Can never reach streak goal of %s with a count limit of %s.' % (_colour_text(streak), _colour_text(count)))
            error = True

    return not error, args

'''
Print a summary of arguments.
'''
def print_args(**kwargs):
    port = kwargs.get('port')
    if port:
        wording_noun = 'TCP attempt'
        wording_method = 'reached over the TCP/%d port' % port
    else:
        wording_noun = 'Ping'
        wording_method = 'pinged'

    target = get_target(**kwargs)

    mode = kwargs['mode']
    count = kwargs.get('count')

    if mode & (MODE_RELIABLE | MODE_UNRELIABLE):
        # Using one of the specialty modes.
        if mode & MODE_RELIABLE > 0:
            word = _colour_green('can')
        else:
            # If not in reliable mode, must be in unreliable mode
            word = _colour_text('cannot', COLOUR_RED)

        streak = kwargs.get('streak', DEFAULT_STREAK_COUNT)

        logger.info('Waiting until %s %s be %s %s times in a row.' % (target, word, wording_method, _colour_text(streak)))

        if count:
            logger.info('Will terminate unsuccessfully if we cannot do so after %s %s attempts.' % (_colour_text(count), wording_noun))

    elif count:
        logger.info('%s attempt count: %s' % (wording_noun, _colour_text(count)))

    interval = kwargs.get('interval')
    if interval:
        logger.info('Time between attempts (seconds): %s' % _colour_text(interval))

def print_results(args, ctx, exit_code):

    if not ctx.total:
        # No pings, skip report
        return True

    error = False

    # Shorthand
    mode = args['mode']
    streak = args.get('streak', DEFAULT_STREAK_COUNT)
    streak_check = mode & (MODE_RELIABLE | MODE_UNRELIABLE)

    if streak_check:
        logger.info('\nDuration: %s', _translate_seconds(ctx.time_end - ctx.time_start))

    if not exit_code and streak_check and ctx.total == args.get('count') and (
        (mode & MODE_RELIABLE and ctx.streak_success < streak)
        or (mode & MODE_UNRELIABLE and ctx.streak_fail < streak)
    ):
        # Set an exit code if we weren't able to get the required number of successful/failed pings within the limit.
        # (Do not override the exit code of a keyboard interrupt)
        error = True

    logger.info('\n--- %s ping statistics ---' % get_target(**args))
    # ping numbers in ping-like format
    logger.info('%s packets transmitted, %d received, %.02f%% packet loss' % (ctx.total, ctx.total_success, 100 - float(ctx.total_success) / ctx.total * 100))
    # rtt stats. I don't worry about this as much as success percentage.
    logger.info('rtt min/avg/max %.03f/%.03f/%.03f' % (ctx.time_min, ctx.time_avg, ctx.time_max))

    return not error


def run(ctx, **kwargs):

    def get_symbol(result, is_success):
        if is_success:
            c = COLOUR_GREEN
        else:
            c = COLOUR_RED

        if result == RESULT_SUCCESS:
            s = '^'
        elif result == RESULT_CLOSED:
            # Same symbol as 'up' for closed.
            # A closed port is just as definitive as an open port.
            s = '^'
        elif result == RESULT_UNREACHABLE:
            # Distinguish unreachable result from an ambiguous timeout
            s = 'x'
        else:
            # Default result (timeout)
            s = '-'

        return s, c

    callback = kwargs.get('callback')
    count = kwargs.get('count')
    interval = kwargs.get('interval', 1)
    mode = kwargs.get('mode')
    streak = kwargs.get('streak', DEFAULT_STREAK_COUNT)
    tally = kwargs.get('tally', False)
    target = kwargs.get('ip')

    ctx.time_start = time()

    # 'heartbeat' chart of ping health.
    chart = ''
    colours = []
    chart_length = 10

    while True:
        start = time()
        result, display, line = callback(**kwargs)

        # Calculate time lazily using python time rather than
        #   parsing from callbacks.
        # This might result in some inaccurate numbers,
        #   but I think it's minor enough to let slide for now.
        diff = time() - start

        success = result == RESULT_SUCCESS

        ctx.total += 1
        if success:
            ctx.total_success += 1

        if ctx.total == 1:
            # First iteration
            ctx.time_min = ctx.time_max = diff
        else:
            # Second iteration
            ctx.time_max = max(ctx.time_max, diff)
            ctx.time_min = min(ctx.time_min, diff)
        ctx.time_avg += ((diff - ctx.time_avg) / ctx.total)

        line = (line or '').strip()
        extra = ''

        symbol, colour = get_symbol(result, success)
        chart += symbol
        colours.append(colour)

        # Modify heartbeat chart
        if success:
            ctx.streak_fail = 0
            ctx.streak_success += 1

            # Only bother announcing the number of successes in a row when testing for reliability.
            if mode & MODE_RELIABLE:
                extra = ' (%s succeeded)' % _colour_text('%d/%d' % (ctx.streak_success, streak))
            elif mode & MODE_UNRELIABLE:
                if tally:
                    extra = '(%s failed, %s succeeded in a row)' % (_colour_text('%d/%d' % (ctx.streak_fail, streak)), _colour_text(ctx.streak_success))
                else:
                    extra = '(%s failed)' % _colour_text('%d/%d' % (ctx.streak_fail, streak))
            elif tally:
                extra = '(%s succeeded in a row)' % _colour_text(ctx.streak_success)

        else:
            ctx.streak_fail += 1
            ctx.streak_success = 0

            if mode & MODE_RELIABLE:
                extra = '(%s succeeded)' % _colour_text('%d/%d' % (ctx.streak_success, streak))
            elif mode & MODE_UNRELIABLE:
                extra = '(%s failed)' % _colour_text('%d/%d' % (ctx.streak_fail, streak))
            else:
                extra = '(%s failed in a row)' % _colour_text(ctx.streak_fail)

        line_output = '%s  %s ' % (_colour_text(target, COLOUR_BLUE), _colour_text(display or _translate_result(result), colour))
        if line:
            line_output += ' %s' % line
        if extra:
            line_output += ' %s' % extra
        chart = chart[max(0, len(chart)-chart_length):] # Trim chart
        if len(colours) > chart_length:
            colours.pop(0)

        display_chart = ''
        for i in range(len(colours)):
            if not i or colours[i-1] != colours[i]:
                # Initial colours or switch colours
                display_chart += COLOUR_OFF
                display_chart += colours[i]
            display_chart += chart[i]

        if len(chart):
            display_chart += COLOUR_OFF

        # Pad out the display
        display_chart += ''.ljust(chart_length - len(chart), '_')

        # Calculate percentage and colouring
        percentage = float(ctx.total_success) / ctx.total * 100

        percentage_colour = COLOUR_GREEN
        if percentage <= 30:
            percentage_colour = COLOUR_RED
        elif percentage <= 60:
            percentage_colour = COLOUR_YELLOW
        percentage_text = '%6.02f%%' % percentage

        # Print update display.
        # Padding the count digits to avoid a bunch of relatively rapid format jumps.
        logger.info('%03d/%03d %s  [%s]  %s' % (ctx.total_success, ctx.total, _colour_text(percentage_text, percentage_colour), display_chart, line_output))

        # Perform checks to see if the loop should continue
        if count and ctx.total >= count:
            break
        if mode & MODE_RELIABLE and ctx.streak_success >= streak:
            break
        elif mode & MODE_UNRELIABLE and ctx.streak_fail >= streak:
            break

        # If there is another loop upcoming, sleep for the remainder of a second that's left.
        sleep(max(0, interval - diff))

if __name__ == '__main__': # pragma: no cover
    try:
        exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        exit(130)
