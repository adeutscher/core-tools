#!/usr/bin/python

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

import getopt, re, socket, sys

# Static variables
####

# MAC Address
MAC_PATTERN = r'^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$'

# Basic syntax check for IPv4 CIDR range.
REGEX_INET4_CIDR='^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

# Basic syntax check for IPv4 address.
REGEX_INET4='^(([0-9]){1,3}\.){3}([0-9]{1,3})$'

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

# Default variables
####

# wol command observed as sending out over UDP/40000
DEFAULT_WOL_PORT = 40000
# Broadcast will send out on default interface.
DEFAULT_TARGET_ADDRESS="255.255.255.255"

## Configurable variables
# Target UDP port
WOL_PORT = DEFAULT_WOL_PORT
# IP address to send to.
TARGET_ADDRESS = DEFAULT_TARGET_ADDRESS

def hexit(exit_code=0):
  print "./wol-manual.py [-a target_address] [-h] ... MAC-ADDRESS ..."
  print "  -a target_address: Send to specific broadcast address"
  print "                     This is necessary when waking up a device on"
  print "                     a different collision domain than your default"
  print "                     gateway interface."
  print "                     Example value: 192.168.100.0"
  print "  -h: Display this help menu and exit."
  print "  -p port: Select UDP port"
  exit(exit_code)

def print_error(message):
    print "%sError%s: %s" % (COLOUR_RED, COLOUR_OFF, message)

def print_notice(message):
    print "%sNotice%s: %s" % (COLOUR_BLUE, COLOUR_OFF, message)

def print_warning(message):
    print "%sWarning%s: %s" % (COLOUR_YELLOW, COLOUR_OFF, message)

def send_magic_packet(mac):

  global WOL_PORT
  global TARGET_ADDRESS

  print_notice("Sending WoL magic packet for %s%s%s" % (COLOUR_BOLD, mac, COLOUR_OFF))

  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

  # From Wikipedia
  # The magic packet is a broadcast frame containing anywhere within
  #   its payload 6 bytes of all 255 (FF FF FF FF FF FF in hexadecimal),
  #   followed by sixteen repetitions of the target computer's
  #   48-bit MAC address, for a total of 102 bytes.

  payload='ffffffffffff'.decode("hex")
  mac_plain = re.sub(':','',mac)
  for i in range(16):
    payload+=mac_plain.decode("hex")
  sock.sendto(payload, (TARGET_ADDRESS, WOL_PORT))

def run():

  global WOL_PORT
  global TARGET_ADDRESS

  errors = []
  opts = []
  args = []

  server_address = None

  # TODO: Consider improving argument parsing
  try:
    # Note: Python will not throw a fit if you call for an invalid slice (will simply be empty).
    opts, args = getopt.gnu_getopt(sys.argv[1:],"ha:p:")
  except getopt.GetoptError as ge:
    errors.append("Error parsing arguments: %s" % str(ge))
  for opt, arg in opts:
    if opt == '-h':
      hexit()
    elif opt == "-a":
      if re.match(REGEX_INET4_CIDR, arg):
        # Someone put in a CIDR range by accident.
        # Their heart is in the right place, so fix formatting with a small nudge for next time.
        print_warning("Target address '%s%s%s' appears to be in CIDR format." % (COLOUR_GREEN, arg, COLOUR_OFF))
        arg = re.sub(r"\/.*$", "", arg)
        print_warning("Trimming target address down to '%s%s%s'." % (COLOUR_GREEN, arg, COLOUR_OFF))
      elif not re.match(REGEX_INET4, arg):
        errors.append("Not a valid target address: %s%s%s" % (COLOUR_BOLD, arg, COLOUR_OFF))
        continue
      TARGET_ADDRESS = arg
    elif opt =="-p":
      try:
        if int(arg) > 0 and int(arg) < 65535:
          WOL_PORT = int(arg)
        else:
          raise ValueError("Invalid port")
      except ValueError:
        errors.append("Invalid port number: %s%s%s" % (COLOUR_BOLD, arg, COLOUR_OFF))
    else:
      errors.append("Unhandled option: %s%s%s" % (COLOUR_BOLD, opt, COLOUR_OFF))

  if not len(errors) and len(args) == 0:
    errors.append("No MAC addresses provided.")

  if len(errors):
    for error in errors:
      print_error(error)
    hexit(1)

  print_notice("Sending WoL magic packet(s) to %s%s%s on %sUDP/%d%s" % (COLOUR_GREEN, TARGET_ADDRESS, COLOUR_OFF, COLOUR_GREEN, WOL_PORT, COLOUR_OFF))

  for candidate in args:
    # May as well squash candidate MAC to lowercase immediately
    candidate_lower = candidate.lower()
    bad_format = 0
    if re.match(MAC_PATTERN, candidate_lower):
      send_magic_packet(candidate_lower)
    else:
      print_error("Invalid MAC address: %s%s%s" % (COLOUR_BOLD, candidate, COLOUR_OFF))
      bad_format += 1
    if bad_format:
      exit(1)

if __name__ == "__main__":
  run()
