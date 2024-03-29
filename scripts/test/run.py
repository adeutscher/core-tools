#!/usr/bin/env python

import os, re, sys, unittest

DIRNAME = 'tests.d'

DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), DIRNAME))
sys.path.append('.')
if not os.path.isdir(DIR):
    raise Exception("Class dir doesn't exist: %s/" % DIR) # pragma: no cover

modules = []
# Detect modules
for (dirname, subdirs, files) in os.walk(DIR):

    sys.path.append(dirname)

    for f in files:
        # ToDo: Regex could use some tightening maybe
        #       That said, should be good so long as no dev puts anything
        #       super-wacky in the classes directory
        m = re.search('^([a-z]+[_a-z]+)\.py$', f, re.IGNORECASE)

        if not m:
            continue # Skip, not a .py
        modules.append(m.group(1))

# Source: https://stackoverflow.com/questions/1732438/how-do-i-run-all-python-unit-tests-in-a-directory
suite = unittest.TestSuite()
filters = sys.argv[1:]

for t in modules:
    mod = __import__(t, globals(), locals(), [DIR])
    # TODO: Implement a better method than checking the end of the class name.
    #         Best approach would be to check if unittest.TestCase is an ancestor of the class.
    for test_class_name, test_class in [(tc, getattr(mod, tc)) for tc in dir(mod) if tc.lower().endswith('tests')]:
        for method in dir(test_class):
            if method.startswith('test_') and (not filters or [f for f in filters if f in method or f in test_class_name or f in t or f in '%s.%s' % (t, test_class_name)]):
                suite.addTest(test_class(method))

runner = unittest.TextTestRunner(verbosity = 2)
runner.run(suite)
