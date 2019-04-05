#!/usr/bin/env python

# A quick and dirty 'minify JSON' button.

import json, os, sys

def err(msg):
    print >> sys.stderr, msg

def process(s):
    print json.dumps(json.loads(s.read()), separators=(',', ':'))

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        err("No path provided.\nUsage: ./json-format.py json-path")
        exit(1)

    code = 0

    # Strictly speaking you wouldn't often want to process multiple files
    #   with this script since the resulting file would
    #   not be JSON-parseable itself.
    # I use it for piping into less and eyeballing for what I'm looking for.
    # In the future, I might adjust the behavior to print to a list in the
    #   event of multiple.
    for path in sys.argv[1:]:
        try:
            if path == "-":
                process(sys.stdin)
            else:
                with open(path, 'r') as f:
                    process(f)
        except Exception as e:
            err("Problem reading from '%s': %s" % (path, str(e)))
            code = 1
    exit(code)
