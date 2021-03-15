#!/usr/bin/python

import sys, unittest

def load(name, path):
    # https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    if sys.version_info.major >= 3:
        if sys.version_info.minor >= 5:
            import importlib.util
            spec = importlib.util.spec_from_file_location(name, path)
            foo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(foo)
            return foo
    raise Exception('Loading data not yet implemented in this testing structure for your version of python.')

class TestCase(unittest.TestCase):
    def assertEmpty(self, obj):
        self.assertEqual(0, len(obj))

    def assertSingle(self, obj):
        self.assertEqual(1, len(obj))
        if type(obj) is dict:
            return obj.items()[0]
        return obj[0]
