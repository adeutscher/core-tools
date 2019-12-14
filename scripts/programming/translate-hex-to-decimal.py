#!/usr/bin/env python

# This is a quick little script to conveniently translate hex numbers
#  to decimal while showing each individual power.

from __future__ import print_function
import re, sys

def get_value(n):
    # Strip out leading 0x, we don't especially care if it's there or not.
    # Format of resulting hex value is all that matters.
    n = re.sub("^0x", "", n)
    if not re.match(r'^[0-9a-f]{1,}$', n):
        print("Invalid hex number: %s" % n, file=sys.stderr)
        return 0

    print("Translating \"0x%s\" from hex to decimal." % n)
    p = -1
    s = 0
    for i in reversed(n):
        p += 1
        v = int(i, 16) * pow(16, p)
        s += v
        print("\t16^%d * %02d: %d" % (p, int(i, 16), v))
    print("Translated \"0x%s\" in hex to %d in decimal." % (n, s))
    return s

if __name__ == "__main__":
    if not sys.argv[1:]:
        print("No hex numbers provided.", file=sys.stderr)
    for i in sys.argv[1:]:
        get_value(i)
