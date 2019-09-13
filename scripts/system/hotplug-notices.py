#!/usr/bin/env python

'''
Output desktop notifications when useful hotplug events happen.
'''

from __future__ import print_function # Python3 printing in Python2
import pyudev # For detecting events
# Basic includes
import getopt, os, socket, sys
from subprocess import Popen as popen

COMMAND_NOTIFY_SEND = 'notify-send'

DEFAULT_DEBUG = False
DEFAULT_GUI = False
DEFAULT_PORT = 1234
DEFAULT_UDP = False

TITLE_DEBUG = 'debug'
TITLE_GUI = 'gui'
TITLE_PORT = 'port'
TITLE_SERVER = 'server'
TITLE_SERVER_RESOLVED = 'server'
TITLE_UDP = 'UDP'

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message):
    print('%s[%s]: %s' % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message))

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)

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
    _print_message(COLOUR_RED, 'Error', message)

def print_debug(message):
    _print_message(COLOUR_YELLOW, 'DEBUG', message)

def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ''
    if msg:
        sub_msg = ' (%s)' % msg
    print_error('Unexpected %s%s: %s' % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, 'Notice', message)

def print_usage(message):
    _print_message(COLOUR_PURPLE, 'Usage', message)

# Script Functions
###

def colour_value(text):
    text = str(text)
    if not text:
        return text
    if text.startswith('/'):
        # I like to colour-code paths green
        return colour_text(text, COLOUR_GREEN)
    return colour_text(text)

def desktop_notice(contents, header = ''):

    if not args.get(TITLE_GUI, DEFAULT_GUI):
        return

    try:
        popen([COMMAND_NOTIFY_SEND, header, contents]).communicate()
    except OSError as e:
        # Handle notify-send going south (not installed?)
        # For this reddit post, just raise it.
        raise e

def hexit(exit_code = 0):
    print_usage('Usage: ./%s [-d] [-h] [-p port] [-s server] [-u] [--debug]' % os.path.basename(sys.argv[0]))
    print_usage('-d:        Print to GUI with %s' % COMMAND_NOTIFY_SEND)
    print_usage('-h:        Display this help menu and exit.')
    print_usage('-p port:   Port to send on over the network (default: %s)' % colour_text('TCP/%d' % DEFAULT_PORT))
    print_usage('-s server: Server to send notices over a network to.')
    print_usage('-u:        Send network notices over UDP')
    print_usage('--debug: Print a debug printout for any hotplug event. Useful for developing new features.')
    exit(exit_code)

def network_notice(contents):
    server = args.get(TITLE_SERVER_RESOLVED)
    port = args.get(TITLE_PORT)
    if not server:
        return
    try:
        if args.get(TITLE_UDP):
            # UDP
            s = socket.socket(type=socket.SOCK_DGRAM)
            s.sendto(contents, (server, port))
        else:
            # TCP
            s = socket.socket(type=socket.SOCK_STREAM)
            s.connect((server, port))
            s.settimeout(2)
            s.send(contents)
    except Exception as e:
        print_error('Error sending network notice to %s: %s' % (colour_text('%s:%d' % (server, port), COLOUR_GREEN), str(e)))

def process_args(raw_args):

    args = {}

    try:
        output_options, operands = getopt.gnu_getopt(raw_args, 'dhp:s:u', [TITLE_DEBUG])
    except Exception as e:
        print_error('Error parsing arguments: %s' % str(e))
        return None

    for option, value in output_options:
        if option == '--%s' % TITLE_DEBUG:
            args[TITLE_DEBUG] = True
        elif option == '-d':
            args[TITLE_GUI] = True
        elif option == '-h':
            hexit()
        elif option == '-p':
            args[TITLE_PORT] = value
        elif option == '-s':
            args[TITLE_SERVER] = value
        elif option == '-u':
            args[TITLE_UDP] = True

        try:
            raw_port = args.get(TITLE_PORT, DEFAULT_PORT)
            args[TITLE_PORT] = int(raw_port)
            if args[TITLE_PORT] < 0 or args[TITLE_PORT] > 65535:
                raise ValueError()
        except ValueError:
            print_error('Invalid port: %s' % colour_text(raw_port))

        if args.get(TITLE_SERVER):
            try:
                args[TITLE_SERVER_RESOLVED] = socket.gethostbyname(args[TITLE_SERVER])
            except:
                print_error('Unable to resolve server address: %s' % colour_text(args[TITLE_SERVER], COLOUR_GREEN))

    return args

def run():

    # Convenient shorthand
    debug = args.get(TITLE_DEBUG, DEFAULT_DEBUG)
    gui = args.get(TITLE_GUI, DEFAULT_GUI)
    server = args.get(TITLE_SERVER_RESOLVED)

    if debug:
        print_notice('Debug mode enabled. Every event will trigger a printout to standard output.')

    # Summarize arguments:
    if gui:
        print_notice('Printing notifications using %s.' % colour_text(COMMAND_NOTIFY_SEND, COLOUR_BLUE))

    if server:
        if args.get(TITLE_UDP):
            wording = 'datagrams'
        else:
            wording = 'connections'
        print_notice('Sending notices using %s to server: %s' % (wording, colour_text('%s:%s' % (server, args.get(TITLE_PORT)), COLOUR_GREEN)))

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)

    # Note: Though the phrasing in documentation worried me, these do stack (e.g. filtering by net doesn't override filtering by USB)
    if not debug:
        monitor.filter_by(subsystem='block') # Block devices (seems to just be storage disks and partitions?)
        monitor.filter_by(subsystem='net') # Display information if a network interface was added.
        monitor.filter_by(subsystem='tty') # Display information on TTY events.

    for device in iter(monitor.poll, None):

        if debug:
            # Store in advance for the sake of avoiding quite as bad of a monster line.
            raw_values = {
                'subsystem': device.subsystem,
                'action': device.action,
                'device_type': device.device_type,
                'driver': device.driver,
                'sys_name': device.sys_name,
                'sys_path': device.sys_path,
                'device_path': device.device_path,
                'device_node': device.device_node,
                'device_number': device.device_number
            }

            print_debug('EVENT: (%s)' % ', '.join(['%s: %s' % (k, colour_value(raw_values[k])) for k in raw_values.keys()]))

        # Compared to initial testing, instead grouping events by subsystem
        if device.subsystem == 'tty':
            # Terminal Event (probably a serial adapter or an Arduino device)

            if device.action == 'add':

                print_notice('New TTY device added: %s' % colour_value(device.device_node))
                desktop_notice('Path: %s' % device.device_node, 'New TTY')
                network_notice('New TTY device added: %s' % device.device_node)

            elif device.action == 'remove':

                print_notice('TTY device removed: %s' % colour_value(device.device_node))
                desktop_notice('Path: %s' % device.device_node, 'Removed TTY')
                network_notice('TTY device removed: %s' % device.device_node)

        elif device.subsystem == 'block':

            # Storage Event

            if device.action == 'add':

                if device.device_type == 'disk':
                    child_nodes = [d.device_node for d in device.children]
                    child_wording = 'Children'
                    if len(child_nodes) == 1:
                        child_wording = 'Child'

                    content_terminal = 'New disk added: %s' % colour_value(device.device_node)
                    if gui:
                        content_gui = 'New disk: %s' % device.device_node

                    if child_nodes:
                        content_terminal += ' (%s: %s)' % (child_wording, ', '.join([colour_value(c) for c in child_nodes]))
                        if gui:
                            content_gui += ' (%s: %s)' % (child_wording, ', '.join(child_nodes))
                    print_notice(content_terminal)
                    if gui:
                        desktop_notice(content_gui, 'Disk Added')

            elif device.action == 'remove':

                print_notice('Removed %s: %s' % (device.device_type, colour_value(device.device_node)))
                desktop_notice('Path: %s' % device.device_node, '%s removed' % device.device_type.capitalize())
                network_notice('Removed %s: %s' % (device.device_type, device.device_node))

        elif device.subsystem == 'net':

            # Network event.

            # Note: Adding/removing interfaces from a bridge does NOT trigger a hotplug event.

            if_name = device.sys_name # Shorthand
            wireless = device.device_type == 'wlan'
            if wireless:
                if_wording = 'wireless'
            else:
                if_wording = device.device_type or 'ethernet'

            if device.action == 'add':

                print_notice('New %s interface: %s' % (if_wording, colour_value(if_name)))
                desktop_notice('%s device name: %s' % (if_wording.capitalize(), if_name), 'New %s interface' % if_wording)
                network_notice('New %s interface: %s' % (if_wording, if_name))

            elif device.action == 'remove':

                print_notice('Removed %s interface: %s' % (if_wording, colour_value(if_name)))
                desktop_notice('%s device name: %s' % (if_wording.capitalize(), if_name), 'Removed %s interface' % if_wording)
                network_notice('Removed %s interface: %s' % (if_wording, if_name))

if __name__ == '__main__':
    # Globally set arguments
    args = process_args(sys.argv[1:])
    if args is None or error_count:
        hexit(1)
    try:
        run()
    except KeyboardInterrupt:
        print('') # Print new line so that prompt happens on fresh line.
        exit(130)

