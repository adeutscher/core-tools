#!/usr/bin/python

import os, re, sys, unittest

DIRNAME = 'tests.d'

DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), DIRNAME))
sys.path.append('.')
if not os.path.isdir(DIR):
    raise Exception("Class dir doesn't exist: %s/" % DIR)

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

for t in modules:
    mod = __import__(t, globals(), locals(), [DIR])
    # TODO: Implement a better method than checking the end of the class name.
    #         Best approach would be to check if unittest.TestCase is an ancestor of the class.
    for test_class in [getattr(mod, tc) for tc in dir(mod) if tc.lower().endswith('tests')]:
        for method in dir(test_class):
            if method.startswith('test_'):
                suite.addTest(test_class(method))

runner = unittest.TextTestRunner(verbosity = 2)
runner.run(suite)
