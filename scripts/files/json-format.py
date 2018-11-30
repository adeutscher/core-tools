#!/usr/bin/env python

# A quick and dirty 'format JSON' button.

import json, os, sys

def err(msg):
    print >> sys.stderr, msg
    exit(1)

try:
    path = sys.argv[1]
except IndexError:
    err("No path provided.\nUsage: ./json-format.py json-path")

try:
    with open(path, 'r') as f:
        print json.dumps(json.loads(f.read()), indent=4)
except Exception as e:
    err("Problem reading from '%s': %s" % (path, str(e)))
