#!/usr/bin/python

import os, sys, unittest

TOOLS_DIR = os.path.realpath(os.path.dirname(__file__) + '/../..')

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
    def assertContains(self, value, enumerable):
        self.assertTrue(type(enumerable) is list)
        self.assertTrue(value in enumerable)

    def assertEmpty(self, obj):
        self.assertEqual(0, len(obj))

    def assertEndsWith(self, expected, val):
        self.assertTrue(val.endswith(expected))

    def assertNone(self, value):
        self.assertEqual(None, value)

    def assertNotEmpty(self, obj):
        self.assertNotEqual(0, len(obj))

    def assertSingle(self, obj):
        self.assertEqual(1, len(obj))
        if type(obj) is dict:
            return obj.items()[0]
        return obj[0]

    def assertStartsWith(self, expected, val):
        self.assertTrue(val.startswith(expected))
