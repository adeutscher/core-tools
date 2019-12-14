#!/usr/bin/env python

from __future__ import print_function
from base64 import b64decode
import os.path, sys

#
# Common Colours and Message Functions
###

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

def enable_colours(force = False):
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stderr.isatty():
        # Colours for standard output.
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_BLUE = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, "Error", message, True)

def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ""
    if msg:
        sub_msg = " (%s)" % msg
    print_error("Unexpected %s%s: %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message, True)

# Script Functions

def assert_exit(condition, error_message, exit_code=1):
    if not condition:
        print_error(error_message)
        exit(exit_code)

def get_input(path):

    inputFile = None

    if path == '-':
        print_notice("Reading file data from standard input.")
        inputFile = sys.stdin
    # Encryption
    else:
        print_notice("Input file: %s" % colour_text(path, COLOUR_GREEN))
        try:
            inputFile = open(path,"r")
        except Exception as e:
            print_exception(e)
    return inputFile

def get_output(path):

    instaFlush = False
    outputFile = None
    if path == '-':
        print_notice("Writing file data to standard output.")
        outputFile = sys.stdout
        instaFlush = True
    else:
        print_notice("Writing file data to '%s'" % path)
        try:
            outputFile = open(path, "w")
        except Exception as e:
            print_exception(e)
    return outputFile, instaFlush

def get_public_key():

    publicKeyObj = None
    maxKeyBytes = 0

    # Hard-coded public key data.
    try:
        # PEM format. Reminder for conversion: cat key.pem | tr -d '\n' , then copy text
        publicKey64 = 'redacted-public-key'
        publicKey = b64decode(publicKey64)
        publicKeyObj = RSA.importKey(publicKey)
        # Reminder: size() returns maximum BITS
        maxKeyBytes = publicKeyObj.size()/8+1
    except ValueError as e:
        pass

    return (publicKeyObj, maxKeyBytes)

def run():
    inputFile = get_input(sys.argv[1])

    if not inputFile:
        return 1

    outputFile, instaFlush = get_output(sys.argv[2])

    if not outputFile:
        return 2

    publicKeyObj, maxKeyBytes = get_public_key()

    if not publicKeyObj:
        return 1

    length_in = 0
    length_out = 0

    while True:
        dataBlock = inputFile.read(maxKeyBytes)

        if len(dataBlock) == 0:
            # Done
            break
        else:
            # Still have data to process.
            cipherBlock = publicKeyObj.encrypt(dataBlock,'k')[0]

            length_in += len(dataBlock)
            length_out += len(cipherBlock)

            outputFile.write(cipherBlock)

            if instaFlush:
                outputFile.flush()

    print_notice("Converted %s of plaintext to %s of ciphertext" % (colour_text(length_in), colour_text(length_out)))

    return 0

try:
    from Crypto.PublicKey import RSA
    from Crypto.Util import asn1
except ImportError:
    assert_exit(False, "Could not find pycrypto. Try installing the python-crypto package!")

assert_exit(len(sys.argv) == 3, "Usage: %s 'input-file' 'output-file'" % os.path.basename(sys.argv[0]), 2)

if __name__ == "__main__":
    exit(run())
