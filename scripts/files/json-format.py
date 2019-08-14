#!/usr/bin/env python

# A quick and dirty 'format JSON' button.

import json, os, sys

def err(msg):
    print >> sys.stderr, msg

def printout(s):
    print json.dumps(json.load(s), indent=2)

if __name__ == "__main__":

    # Since it's just for one argument, make our own solution for detecting an inline request.
    inline = [i for i in sys.argv[1:] if i == "-i"]
    paths = [i for i in sys.argv[1:] if i != "-i"]

    if not paths:
        err("No path provided.\nUsage: ./json-format.py [-i] json-path ...")
        exit(1)

    code = 0

    # Strictly speaking you wouldn't often want to process multiple files
    #   with this script since the resulting file would
    #   not be JSON-parseable itself.
    # I use it for piping into less and eyeballing for what I'm looking for.
    # In the future, I might adjust the behavior to print to a list in the
    #   event of multiple.

    for path in paths:
        try:
            if path == "-":
                # Always print out standard input, since we can't exactly write back to the same object.
                printout(sys.stdin)
                continue

            with open(path, 'r') as f:
                if inline:
                    content = json.load(f)
                else:
                    printout(f)

        except Exception as e:
            err("Problem reading from '%s': %s" % (path, str(e)))
            code = 1
            continue

        if inline:
            try:
                with open(path, 'w') as f:
                    json.dump(content, f, indent=2)
                    f.write('\n')
            except Exception as e:
                err("Problem writing to '%s': %s" % (path, str(e)))
    exit(code)
