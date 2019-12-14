#!/usr/bin/env python

# This is a quick little script to conveniently translate binary numbers
#  to decimal while showing each individual power.

from __future__ import print_function
import re, sys

def get_value(n):
    if not re.match(r'^[01]{1,}$', n):
        print("Invalid binary number: %s" % n,file=sys.stderr)
        return 0

    print("Translating \"%s\" from binary to decimal." % n)
    p = -1
    s = 0
    for i in reversed(n):
        p += 1
        if i == "0":
            continue
        v = pow(2, p)
        s += v
        print("\t2^%d: %d" % (p, v))
    print("Translated \"%s\" in binary to %d in decimal." % (n, s))
    return s

if __name__ == "__main__":
    if not sys.argv[1:]:
        print("No binary numbers provided.", file=sys.stderr)
    for i in sys.argv[1:]:
        get_value(i)
