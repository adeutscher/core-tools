#!/usr/bin/env python

#####################################################
#
#  PROGRAM:        wol-manual.py
#
#  DATE:           December 24, 2016
#
#  REVISIONS:      See git log
#
#  NOTES:
#  Manually craft a WakeOnLAN magic packet.
#
#  Pretty much entirely redundant if a standard wol/wakeonlan
#    command is already installed.
#
#####################################################

from __future__ import print_function
import binascii, getopt, logging, os, re, socket, sys
from socket import socket as socket_object

# Static variables
####

# MAC Address
MAC_PATTERN = r'^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$'

# Basic syntax check for IPv4 CIDR range.
REGEX_INET4_CIDR = '^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

# Basic syntax check for IPv4 address.
REGEX_INET4 = '^(([0-9]){1,3}\.){3}([0-9]{1,3})$'


def build_logger(label, err=None, out=None):
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


logger = build_logger('wol_manual')

# Default variables
####

# wol command observed as sending out over UDP/40000
DEFAULT_WOL_PORT = 40000
# Broadcast will send out on default interface.
DEFAULT_TARGET_ADDRESS = "255.255.255.255"

## Configurable variables
# Target UDP port
WOL_PORT = DEFAULT_WOL_PORT
# IP address to send to.
TARGET_ADDRESS = DEFAULT_TARGET_ADDRESS


def hexit(exit_code=0):
    logger.info("./wol-manual.py [-a target_address] [-h] ... MAC-ADDRESS ...")
    logger.info("  -a target_address: Send to specific broadcast address")
    logger.info("                     This is necessary when waking up a device on")
    logger.info("                     a different collision domain than your default")
    logger.info("                     gateway interface.")
    logger.info("                     Example value: 192.168.100.0")
    logger.info("  -h: Display this help menu and exit.")
    logger.info("  -p port: Select UDP port")
    return exit_code


# Script Functions


def format_bytes(content):
    content_bytes = content
    if sys.version_info.major >= 3 and type(content) is not bytes:
        content_bytes = bytes(content_bytes, 'ascii')
    return binascii.unhexlify(content_bytes)


def send_packet(payload, address):
    sock = socket_object(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(payload, address)


def send_magic_packet(mac):

    global WOL_PORT
    global TARGET_ADDRESS

    logger.info("Sending WoL magic packet for %s" % mac)

    # From Wikipedia
    # The magic packet is a broadcast frame containing anywhere within
    #   its payload 6 bytes of all 255 (FF FF FF FF FF FF in hexadecimal),
    #   followed by sixteen repetitions of the target computer's
    #   48-bit MAC address, for a total of 102 bytes.

    payload = format_bytes('ffffffffffff')
    mac_plain = re.sub(':', '', mac)
    for i in range(16):
        payload += format_bytes(mac_plain)
    send_packet(payload, (TARGET_ADDRESS, WOL_PORT))


def run(args_raw):

    global WOL_PORT
    global TARGET_ADDRESS

    errors = []
    opts = []
    args = []

    server_address = None

    # TODO: Consider improving argument parsing
    try:
        # Note: Python will not throw a fit if you call for an invalid slice (will simply be empty).
        opts, args = getopt.gnu_getopt(args_raw, "ha:p:")
    except getopt.GetoptError as ge:
        errors.append("Error parsing arguments: %s" % str(ge))
    for opt, arg in opts:
        if opt == '-h':
            return hexit()
        elif opt == "-a":
            if re.match(REGEX_INET4_CIDR, arg):
                # Someone put in a CIDR range by accident.
                # Their heart is in the right place, so fix formatting with a small nudge for next time.
                logger.warning(
                    "Target address '%s' appears to be in CIDR format." % arg
                )
                arg = re.sub(r"\/.*$", "", arg)
                logger.warning("Trimming target address down to '%s'." % arg)
            elif not re.match(REGEX_INET4, arg):
                errors.append("Not a valid target address: %s" % arg)
                continue
            TARGET_ADDRESS = arg
        elif opt == "-p":
            try:
                if int(arg) > 0 and int(arg) < 65535:
                    WOL_PORT = int(arg)
                else:
                    raise ValueError("Invalid port")
            except ValueError:
                errors.append("Invalid port number: %s" % arg)

    if not len(errors) and len(args) == 0:
        errors.append("No MAC addresses provided.")

    if len(errors):
        for error in errors:
            logger.error(error)
        return hexit(1)

    logger.info(
        "Sending WoL magic packet(s) to %s on %s"
        % (TARGET_ADDRESS, "UDP/%d" % WOL_PORT)
    )

    for candidate in args:
        # May as well squash candidate MAC to lowercase immediately
        candidate_lower = candidate.lower()
        bad_format = 0
        if re.match(MAC_PATTERN, candidate_lower):
            send_magic_packet(candidate_lower)
        else:
            logger.error("Invalid MAC address: %s" % candidate)
            bad_format += 1
        if bad_format:
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        exit(run(sys.argv[1:]))
    except KeyboardInterrupt:
        exit(130)
