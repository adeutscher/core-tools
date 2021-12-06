#!/usr/bin/env python

'''

This is a rewrite of a past project to report potential ARP poisoning.
The original product was written in C.

Well-behaved ARP behavior requires both a request and a reply.
    With a conversation as an analogy, this could be said as:
        * Host A: I'm looking for someone at this address B
        * Host B: Hey Host A, I'm Host B, and I'm over here.

ARP poisoning involves a malicious host constandly sending out
    crafted ARP messages to interfere with the ARP tables of the victim.
    With a conversation as an analogy, this could be said as:
        * Host C: Hey Host A, I'm host B, and I'm over here (honest!)
        * Host C: Hey Host A, I'm host B, and I'm over here (honest!)

This script makes judgements based on imbalances of ARP replies to ARP requests.
  * An imbalance of requests for a particular address suggests a client trying to reach something on an unused address.
    This is unfortunate for the person making the request, but not harmful.
* An imbalance of replies for a particular address suggests that ARP poisoning is taking place.
'''

from __future__ import print_function
import argparse, getopt, getpass, os, pwd, re, struct, subprocess, sys, time
from scapy.all import sniff, conf, ARP, Ether
import logging

logging.getLogger('scapy.runtime').setLevel(logging.CRITICAL)

#
# Common Colours and Message Functions
###


def _print_message(header_colour, header_text, message, stderr=False):
    f = sys.stdout
    if stderr:
        f = sys.stderr
    print(
        '%s[%s]: %s'
        % (
            colour_text(header_text, header_colour),
            colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN),
            message,
        ),
        file=f,
    )


def colour_text(text, colour=None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)


def enable_colours(force=False):
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


def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ''
    if msg:
        sub_msg = ' (%s)' % msg
    print_error(
        'Unexpected %s%s: %s'
        % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e))
    )


def print_info(message):
    _print_message(COLOUR_GREEN, 'Info', message)


def print_notice(message):
    _print_message(COLOUR_BLUE, 'Notice', message)


def print_warning(message):
    _print_message(COLOUR_YELLOW, 'Warning', message)


#
# Script Functions
###

ARP_SPOOF_EVENT_HEAL = 'HEAL'
ARP_SPOOF_EVENT_SPOOF = 'SPOOF'

DEFAULT_EXPIRY = 300
DEFAULT_REPORT_THRESHOLD = 5
DEFAULT_SCRIPT_COOLDOWN = 300

PCAP_FILTER = 'arp'

# Classes


def demote(user_uid, user_gid):
    def result():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return result


'''
Translation layer between Scapy and script operations.
This script was originally written with pypcap and converted to scapy later.
This layer was written to avoid having to hunt down every single pypcap phrasing,
    and it will be useful again in case scapy also becomes obsolete.
'''


class ArpInstance:
    def __init__(self, pkt):

        self.ts = pkt.time

        eth = pkt[Ether]
        arp = pkt[ARP]

        # Ethernet hardware addresses
        self.esrc = eth.src
        self.edst = eth.dst

        # Arp Type
        self.opcode = arp.op
        # ARP hardware addresses
        self.asrc = arp.hwsrc
        self.adst = arp.hwdst
        # Network addresses
        self.ndst = arp.pdst
        self.nsrc = arp.psrc

        if self.opcode == 1:  # Request
            # Request
            self.id = '%s%s' % (self.asrc, self.ndst)
        elif self.opcode == 2:  # Reply
            self.id = '%s%s' % (self.adst, self.nsrc)


class ToxScreenSession:
    def __init__(self, wrapper):
        self.args = wrapper.args
        self.wrapper = wrapper

        self.last_script_run = 0

        self.arp_instances = {}
        self.last_script_run = {}
        self.time_start = 0
        self.time_span = 0
        self.time_recent = 0

    def attempt_script(self, event, arp):
        if event not in self.last_script_run:
            self.last_script_run[event] = {}

        if (
            not self.args.script
            or not (arp.ts - self.last_script_run[event].get(arp.id, arp.ts))
            > self.args.script_cooldown
        ):
            return  # No script defined or cooldown not exceeded.

        # Mark timestamp by starting time.
        self.last_script_run[event][arp.id] = arp.ts

        # Run script
        try:
            subprocess.Popen(
                [
                    self.args.script,
                    event,
                    arp.nsrc,
                    arp.asrc,
                    arp.ndst,
                    arp.adst,
                    arp.esrc,
                    arp.edst,
                ],
                preexec_fn=demote(userinfo.pw_uid, userinfo.pw_gid),
            )
        except OSError:
            print_error(
                'Problem executing script hook: %s'
                % colour_text(self.args.script, COLOUR_GREEN)
            )

    def do_pcap_callback(self, pkt):

        arp = ArpInstance(pkt)

        if arp.opcode == 1:  # ARP Request OpCode
            op = 'REPLY'
            if self.args.verbose:
                print_notice(
                    '%s: Who has %s? Tell %s (%s)'
                    % (
                        colour_text(op),
                        colour_text(arp.ndst, COLOUR_GREEN),
                        colour_text(arp.nsrc, COLOUR_GREEN),
                        colour_text(arp.asrc),
                    )
                )
        elif arp.opcode == 2:  # ARP Reply OpCode
            op = 'REPLY'
            if self.args.verbose:
                print_notice(
                    '%s: %s is at %s (To: %s at %s)'
                    % (
                        colour_text(op),
                        colour_text(arp.nsrc, COLOUR_GREEN),
                        colour_text(arp.asrc),
                        colour_text(arp.ndst, COLOUR_GREEN),
                        colour_text(arp.adst),
                    )
                )
        else:
            return  # Not a request or reply.

        self.time_recent = arp.ts
        if not self.time_start:
            self.time_start = arp.ts

        if arp.asrc != arp.esrc:
            self.wrapper.print_alert(
                '%s for IP %s claiming to be from MAC %s, but is actually from MAC %s. Likely a forged healing packet!'
                % (
                    colour_text(op),
                    colour_text(arp.nsrc, COLOUR_GREEN),
                    colour_text(arp.asrc),
                    colour_text(arp.esrc),
                )
            )
            self.list_ipv4_addresses_by_mac(arp.esrc)
            self.attempt_script(ARP_SPOOF_EVENT_HEAL, arp)

            # Immediately return.
            # The point in tracking events is that we normally cannot track poisoning by a single packet.
            # However, healing packets from ettercap/arpspoof/etc trying to cover its tracks
            # are blatant enough that they can be identified right away.
            # Do not track event to avoid false positives.
            return

        # Is an interaction of this ID currently stored in the dictionary?
        if arp.id not in self.arp_instances:
            self.arp_instances[arp.id] = [arp]  # Create list and add ARP packet
        else:
            self.arp_instances[arp.id].append(
                arp
            )  # Append ARP packet to existing chain.

        # Need to clear out old instances.
        # If we are reading from a PCAP file, then we can only really
        #   compare against the current timestamp.
        # If we are reading from a live capture, then we can use the current
        #   time as a reference (which should be pretty much be
        #   the provided timestamp anyways).
        for k in self.arp_instances.keys():
            # May as well clear through all instances.
            i = 0
            while i < len(self.arp_instances[k]):
                if (arp.ts - self.arp_instances[k][i].ts) > self.args.expiry:
                    del self.arp_instances[k][i]
                    # Do not increment, since i will now be the old i+1.
                else:
                    i += 1
            if not self.arp_instances[k]:
                # Delete empty lists, mostly for tidiness.
                del self.arp_instances[k]
                for key in self.last_script_run:
                    for subkey in self.last_script_run[key]:
                        if arp.id in self.last_script_run[key][subkey]:
                            del self.last_script_run[key][subkey][arp.id]

        # Sweep through non-expired instances of this ID to look for potential poisoning.
        score = 0
        i = 0
        while i < len(self.arp_instances[arp.id]):
            target = self.arp_instances[arp.id][i]
            if target.opcode == 1:  # Request
                # Machine sent out a request, behooving real machine to reply and countering poison attack.
                # Still under consideration, have a request simply decrement the score instead?
                score = 0
            else:  # Reply
                score += 1

                span_last = int(target.ts)
                if score == 1:
                    span_start = int(target.ts)

            i += 1

        if score >= self.args.script_report_threshold:
            #
            # TODO: Existing reporting currently has a bit of a flaw:
            #          - Does not account for one IP 'legitimately' being stepped on by two devices, creating an imbalance.
            #            This still impedes network performance, but it's more 'ARP high cholesterol' than 'ARP poisoning'.
            #            Still bad for your network, but not necessarily malicious.

            span_number = span_last - span_start
            self.wrapper.print_alert(
                '%s (%s) is likely being ARP poisoned by %s (spoofing %s, ARP imbalance of %s over %s seconds)'
                % (
                    colour_text(arp.ndst, COLOUR_GREEN),
                    colour_text(arp.adst),
                    colour_text(arp.esrc),
                    colour_text(arp.nsrc, COLOUR_GREEN),
                    colour_text(score),
                    colour_text(span_number),
                )
            )

            self.list_ipv4_addresses_by_mac(arp.esrc)
            self.attempt_script(ARP_SPOOF_EVENT_SPOOF, arp)

    def list_ipv4_addresses_by_mac(self, mac):

        if not self.args.resolve:
            return  # Listing is not enabled.

        try:
            with open('/proc/net/arp', 'r') as f:
                content = f.readlines()
                f.close()
        except OSError as e:
            # File error.
            print_error(e)
            return

        addresses = []

        for line in content:
            cols = re.sub('\s+', ' ', line).split(' ')
            if cols[3] == mac:
                addresses.append(colour_text(cols[0], COLOUR_GREEN))

        if addresses:
            print_info(
                'IPv4 entries for %s in current ARP table: %s'
                % (colour_text(mac), ', '.join(addresses))
            )

    def time_span_update(self):
        self.time_span = int(self.time_recent - self.time_start)


class ToxScreenWrapper:
    def __init__(self):

        self.alert_count = 0

    def do_pcap(self):

        self.session = ToxScreenSession(self)

        lfilter = lambda p: ARP in p
        try:
            if self.args.interface:
                conf.iface = self.args.interface
                sniff(
                    prn=self.session.do_pcap_callback,
                    store=0,
                    filter=PCAP_FILTER,
                    lfilter=lfilter,
                )
            elif self.args.file:
                try:
                    sniff(
                        prn=self.session.do_pcap_callback,
                        offline=self.args.file,
                        store=0,
                        filter=PCAP_FILTER,
                        lfilter=lfilter,
                    )
                except AttributeError as e:
                    if (
                        str(e)
                        != '\'PcapNgReader\' object has no attribute \'linktype\''
                    ):
                        raise

                    print(
                        f'Could not parse PCAPNG file. Convert with editcap: editcap -F libpcap \'{self.args.file}\' \'out.pcap\''
                    )
                    return False
        except KeyboardInterrupt:
            print('\n')

        if self.args.interface:
            # In the case of live captures, mark the current time.
            # This is in case there has been a fair bit of time
            # between cancellation time and the last packet.
            # This is unnecessary when reading a PCAP file.
            self.session.time_recent = time.time()

        self.session.time_span_update()

        return True

    def print_alert(self, message):
        self.alert_count += 1
        _print_message(COLOUR_RED, 'ALERT', message)

    def process_args(self, input_args):

        parser = argparse.ArgumentParser(description='ARP Poisoning Monitor')
        parser.add_argument(
            '-v', dest='verbose', action='store_true', help='Verbose output'
        )
        # Toxscreen Options
        t_options = parser.add_argument_group('screening options')
        t_options.add_argument(
            '-e',
            dest='expiry',
            help='Time in seconds that it takes for an ARP event to fall off this script\'s radar',
            type=int,
            default=DEFAULT_EXPIRY,
        )
        t_options.add_argument(
            '-r',
            dest='resolve',
            action='store_true',
            help='Attempt to resolve offending MAC address to an IP address.',
        )

        # PCAP options
        p_options = parser.add_argument_group('pcap options')
        p_options.add_argument('-f', dest='file', help='PCAP file to load')
        p_options.add_argument(
            '-i', dest='interface', help='Network interface to listen on'
        )

        s_options = parser.add_argument_group('script options')
        s_options.add_argument(
            '-s',
            dest='script',
            help='Script to run when a suspicious event is detected.',
        )
        s_options.add_argument(
            '-c',
            dest='script_cooldown',
            help='Cooldown between script invocations',
            type=int,
            default=DEFAULT_SCRIPT_COOLDOWN,
        )
        s_options.add_argument(
            '-t',
            dest='script_report_threshold',
            help='Cooldown between script invocations',
            type=int,
            default=DEFAULT_REPORT_THRESHOLD,
        )
        s_options.add_argument(
            '-u',
            dest='script_user',
            help='User to run script as. Only effective if script is run as root.',
        )

        self.args = args = parser.parse_args(input_args)

        errors = []

        # Note: Intentionally checking for both PCAP and interface errors, even if we are about to complain about the user trying to do both.

        # Validate PCAP file
        ##
        if args.file and not os.path.isfile(args.file):
            errors.append(
                'PCAP file does not exist: %s' % colour_text(args.file, COLOUR_GREEN)
            )
        # Validate interface.
        if args.interface:
            if not os.path.isdir('/sys/class/net/%s' % args.interface):
                errors.append(
                    'Listening interface does not exist: %s'
                    % colour_text(args.interface, COLOUR_GREEN)
                )
            if os.geteuid():  # Check for whether the user is root or not
                errors.append(
                    'Must be %s to capture on a live interface.'
                    % colour_text('root', COLOUR_RED)
                )

        if args.file and args.interface:
            errors.append('Cannot specify both an input file and a capture interface.')
        elif not args.interface and not args.file:
            errors.append('No interface or PCAP file defined.')

        # Validate Script Options
        ##
        if args.script:
            if os.path.isdir(args.script):
                print_error(
                    'Processing script path is a directory: %s'
                    % colour_text(args.script, COLOUR_GREEN)
                )
            elif not os.path.isfile(args.script):
                errors.append(
                    'Processing script does not exist: %s'
                    % colour_text(args.script, COLOUR_GREEN)
                )
            elif not os.access(args.script, os.X_OK):
                errors.append(
                    'Processing script is not executable: %s'
                    % colour_text(args.script, COLOUR_GREEN)
                )

            target_user = args.script_user or getpass.getuser()
            try:
                global userinfo
                userinfo = pwd.getpwnam(target_user)
            except KeyError:
                print_error(
                    'Could not get information for %s: %s'
                    % (colour_text('script user'), colour_text(target_user))
                )
        else:
            # Check for arguments that work off of the processing script.
            # I am divided on whether or not these should be warnings or errors...
            for check in [
                c for c in ['script_cooldown', 'script_user'] if getattr(args, c)
            ]:
                print_warning(
                    'A value for %s was set, but no script is defined.'
                    % colour_text(check.replace('_', ' '))
                )

        # Validate integers
        ##
        for key, key_label in [
            ('script_cooldown', 'script cooldown'),
            ('expiry', 'event expiry'),
            ('script_report_threshold', 'script report threshold'),
        ]:
            value = getattr(args, key)
            if value <= 0:
                errors.append(
                    'Value of %s must be a positive integer.' % colour_text(key_label)
                )

        if args.script_report_threshold <= 2 and args.script_report_threshold > 0:
            # Also tack on a warning
            print_warning(
                'A low %s value of %s could generate a lot of false positives.'
                % (
                    colour_text('report threshold'),
                    colour_text(args.script_report_threshold),
                )
            )

        if args.script_cooldown > args.expiry:
            print_warning(
                'Value for %s (%s) is less than that of %s (%s). Script may run more often than expected.'
                % (
                    colour_text('script'),
                    colour_text(args.script_cooldown),
                    colour_text('expiry'),
                    colour_text(self.expiry),
                )
            )

        return errors

    def run(self, args_input):
        args_errors = self.process_args(args_input)
        if args_errors:
            for e in args_errors:
                print_error(e)
            return 1

        self.summarize_arguments()

        if not self.do_pcap():
            return 1

        colour = COLOUR_RED
        if not self.alert_count:
            colour = COLOUR_GREEN

        if self.args.file:
            print_notice(
                'Observed instances of ARP poisoning in PCAP file \'%s\' over %s seconds: %s'
                % (
                    colour_text(os.path.basename(self.args.file), COLOUR_GREEN),
                    colour_text(self.session.time_span),
                    colour_text(self.alert_count, colour),
                )
            )
        else:
            # Interface printing.
            print_notice(
                'Observed instances of ARP poisoning on \'%s\' interface over %s seconds: %s'
                % (
                    colour_text(COLOUR_GREEN, os.path.basename(self.args.interface)),
                    colour_text(self.session.time_span),
                    colour_text(self.alert_count, colour),
                )
            )
        return 0

    def summarize_arguments(self):
        if self.args.interface:
            on = ('Listening', 'on interface', colour_text(self.args.interface))
        else:
            on = ('Looking', 'in file', colour_text(self.args.file, COLOUR_GREEN))
        print_notice('%s for ARP poisoning cases %s: %s' % on)
        print_notice(
            'Poisoning threshold: %s imbalanced replies will imply poisoning.'
            % colour_text(self.args.script_report_threshold)
        )
        print_notice(
            'Poisoning expiry time: %s' % colour_text('%ds' % self.args.expiry)
        )
        if self.args.script:
            user_colour = COLOUR_BOLD
            if self.args.script_user == 'root':
                user_colour = COLOUR_RED
            print_notice(
                'Processing script: %s as %s (cooldown per instance: %s)'
                % (
                    colour_text(self.args.script, COLOUR_GREEN),
                    colour_text(self.args.script_user, user_colour),
                    colour_text('%ds' % self.args.script_cooldown),
                )
            )
        if self.args.resolve:
            print_notice(
                'Suspicious MAC addresses will be checked against our current ARP table for matches.'
            )


if __name__ == '__main__':

    screen = ToxScreenWrapper()
    exit(screen.run(sys.argv[1:]))
