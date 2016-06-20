#!/usr/bin/python
 
import sys,re

def getValue(inString):
    if re.search(r'^0x',inString):
        # Hex value
        return int(inString,16)
    else:
        # Treat as base-10
        return int(inString)

def usage():
    print "Usage: %s number [mask]"
    exit(1)

power = 0
num = 0

value = getValue(sys.argv[1])
if not value or value < 0:
    print "Number value must be greater than zero."
    usage()

if len(sys.argv) == 3:
    mask = getValue(sys.argv[2])
    print "Testing a value of %d (%#08x) against a mask of %d (%#08x)." % tuple([value,value,mask,mask])

    print "Result: ",
    result = value & mask
    print "%d (" % result,
    if result:
        if (value & mask) == value:
            print "Yes, Full Match)"
        else:
            print "Yes, Partial Match)"
    else:
        print "No Match)"
    
elif len(sys.argv) == 2:

    print "Getting the bitmask flags stored in %d (%#08x)" % tuple([value,value])
    while True:
        num = pow(2,power)
     
        if num > value:
            break
     
        print "%10d (%#010x) ^ %03d :" % tuple([num,num,power]),
        if value & num:
            print "1 (Yes)"
        else:
            print "0 (No)"
     
        power = power + 1
else:
    usage()
