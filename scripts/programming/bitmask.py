#!/usr/bin/env python

from __future__ import print_function
import os,sys,re

# Colour functions

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def enable_colours(force = False):
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

# Script Functions

def displayFlags(value):
    print("Getting the bitmask flags in value of %d (%#08x)" % (value,value))
    power = 0
    num = 0
    while True:
        num = pow(2,power)

        if num > value:
            break

        s = "2 ^ %s: (%s, %s): " % (colour_text("%03d" %  power), colour_text("%10d" %  num), colour_text("%#010x" %  num))
        if value & num:
            s+= "1 (%s)" % colour_text("True", COLOUR_GREEN)
        else:
            s += "0 (%s)" % colour_text("False", COLOUR_RED)
        print(s)

        power += 1

def getValue(args, index, label):
    ret = None
    err = None
    if len(args) <= index:
        print("No %s provided." % label)
        return None
    try:
        val = args[index]
        if re.search(r'^0x',val):
            # Hex value
            ret = int(val,16)
        else:
            # Treat as base-10
            ret = int(val)
    except Exception as e:
        err = str(e)

    if ret is None or ret <= 0:
        msg = 'Invalid %s: %s' % (label, val)
        if err:
            msg += ' (%s)' % err
        print(msg)
        return None
    return ret

def usage():
    print("Usage: %s number [mask]" % os.path.basename(__file__))
    exit(1)

def main(args):
    value = getValue(args, 1, "value")
    if value is None:
        print("Number value must be greater than zero.")
        usage()

    if len(args) >= 3:
        mask = getValue(args, 2, "mask")
        if mask is None:
            usage()
        print("Testing a value of %d (%#08x) against a mask of %d (%#08x)." % tuple([value,value,mask,mask]))

        result = value & mask
        s = "Result: %d & %d = %d (" % (value, mask, result)
        if result:
            if (value & mask) == value:
                s += "Yes, Full Match)"
            else:
                s += "Yes, Partial Match)"
        else:
            s += "No Match)"
        print(s)
        if result:
            displayFlags(result)
    else:
        displayFlags(value)

if __name__ == '__main__': main(sys.argv)
