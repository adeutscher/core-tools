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

## Static variables
MAC_PATTERN = r'^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$'

## Default variables
# wol command observed as sending out over UDP/40000
DEFAULT_WOL_PORT = 40000
DEFAULT_TARGET_ADDRESS="255.255.255.255"

## Configurable variables
# Target UDP port
WOL_PORT = DEFAULT_WOL_PORT
# IP address to send to.
TARGET_ADDRESS = DEFAULT_TARGET_ADDRESS

def help_exit(exit_code=0):
  print "./wol-manual.py [-h] [-i target_address] ... MAC-ADDRESS ..."
  print "  -h: Display this help menu."
  print "  -i target_address: Send to specific broadcast address"
  print "  -p port: Select UDP port"
  exit(exit_code)

def send_magic_packet(mac):

  global WOL_PORT
  global TARGET_ADDRESS

  print "Sending WoL magic packet for %s" % mac

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

def run(argv):

  global WOL_PORT
  global TARGET_ADDRESS

  errors = []
  opts = []
  args = []

  server_address = None

  # TODO: Consider improving argument parsing
  try:
    # Note: Python will not throw a fit if you call for an invalid slice (will simply be empty).
    opts, args = getopt.getopt(argv[1:],"hi:p:")
  except getopt.GetoptError:
    errors.append("Error parsing arguments")
  for opt, arg in opts:
    if opt == '-h':
      help_exit()
    elif opt =="-i":
      # TODO: Consider adding validation for the bind address.
      TARGET_ADDRESS = arg
    elif opt =="-p":
      # TODO: Consider adding validation for the bind address.
      try:
        if int(arg) > 0 and int(arg) < 65535:
          WOL_PORT = int(arg)
        else:
          raise ValueError("Invalid port")
      except ValueError:
        errors.append("Invalid port number: %s" % int(arg))

  if len(args) == 0:
    errors.append("No MAC addresses provided.")

  if len(errors):
    for error in errors:
      print >> sys.stderr, "Error: %s" % error
    help_exit(1)

  print "Sending WoL magic packets to %s on UDP/%d" % (TARGET_ADDRESS, WOL_PORT)

  for candidate in args:
    # May as well squash candidate MAC to lowercase immediately
    candidate_lower = candidate.lower()
    if re.match(MAC_PATTERN, candidate_lower):
      send_magic_packet(candidate_lower)
    else:
      print "Invalid MAC address: %s" % candidate

if __name__ == "__main__":
  run(sys.argv)
