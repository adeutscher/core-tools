#!/usr/bin/env python

# A quick and dirty 'format JSON' button.

import json, os, sys

def err(msg):
    print >> sys.stderr, msg

if len(sys.argv) < 0:
    err("No path provided.\nUsage: ./json-format.py json-path")
    exit(1)

code = 0
for path in sys.argv[1:]:
    try:
        with open(path, 'r') as f:
            print json.dumps(json.loads(f.read()), indent=4)
    except Exception as e:
        err("Problem reading from '%s': %s" % (path, str(e)))
        code = 1
exit(code)
