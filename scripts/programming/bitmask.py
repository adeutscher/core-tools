#!/usr/bin/python

import sys,re

def displayFlags(value):
    print "Getting the bitmask flags in value of %d (%#08x)" % tuple([value,value])
    power = 0
    num = 0
    while True:
        num = pow(2,power)

        if num > value:
            break

        print "%10d (%#010x) ^ %03d :" % tuple([num,num,power]),
        if value & num:
            print "1 (Yes)"
        else:
            print "0 (No)"

        power += 1

def getValue(index, label):
    ret = None
    if len(sys.argv) <= index:
        print "No %s provided." % label
        return None
    try:
        val = sys.argv[index]
        if re.search(r'^0x',val):
            # Hex value
            ret = int(val,16)
        else:
            # Treat as base-10
            ret = int(val)
    except Exception as e:
        pass

    if ret is None or ret <= 0:
        print "Invalid %s: %s (%s)" % (val, label, str(e))
        return None
    return ret

def usage():
    print "Usage: %s number [mask]"
    exit(1)


value = getValue(1, "value")
if value is None:
    print "Number value must be greater than zero."
    usage()

if len(sys.argv) >= 3:
    mask = getValue(2, "mask")
    if mask is None:
        usage()
    print "Testing a value of %d (%#08x) against a mask of %d (%#08x)." % tuple([value,value,mask,mask])

    result = value & mask
    s = "Result: %d & %d = %d (" % (value, mask, result)
    if result:
        if (value & mask) == value:
            s += "Yes, Full Match)"
        else:
            s += "Yes, Partial Match)"
    else:
        s += "No Match)"
    print s
    if result:
        displayFlags(result)

else:
    displayFlags(value)
