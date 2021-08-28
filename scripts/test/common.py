#!/usr/bin/python

import io, os, sys, logging, unittest

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

class LogFilter(logging.Filter):
    def __init__(self, focus):
        self.focus = focus

    def filter(self, record):

        if self.focus is None:
            return True
        return self.focus == record.levelno

class LoggableTestCase(type):
    def __new__(cls, name, bases, dct):

        # Logging courtesy of Tobias Kienzler and Fabio of StackOverflow
        # Source: https://stackoverflow.com/questions/7472863/pydev-unittesting-how-to-capture-text-logged-to-a-logging-logger-in-captured-o/15969985#15969985

        # To use, declare test case class like so:
        # ExampleTests(common.TestCase, metaclass=common.LoggableTestCase)
        # The logger of your target will have to be overridden with a logger
        #   that targets "unittests" (LABEL_TEST_LOGGER):
        # mod.logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

        # if the TestCase already provides setUp, wrap it
        setUp = dct.get('setUp', lambda self: None)
        def wrappedSetUp(self):
            self.logger = logging.getLogger(LABEL_TEST_LOGGER)
            self.logger.setLevel(logging.DEBUG)

            self.logStreams = {}
            self.logHandlers = {}

            methods = [
                (None, 'all'),
                (logging.DEBUG, 'debug'),
                (logging.INFO, 'info'),
                (logging.WARNING, 'warning'),
                (logging.ERROR, 'error'),
                (logging.CRITICAL, 'critical')
            ]
            for scope, label in methods:
                self.logStreams[label] = stream = io.StringIO()
                self.logHandlers[label] = handler = logging.StreamHandler(stream)
                handler.addFilter(LogFilter(scope))
                self.logger.addHandler(handler)
            setUp(self)
        dct['setUp'] = wrappedSetUp

        # Log Retrieval
        def getLogs(self, scope = 'all'):
            stream = self.logStreams[scope]
            stream.seek(0, 0)
            return [l.strip() for l in stream.readlines()]
        dct['getLogs'] = getLogs

        # same for tearDown
        tearDown = dct.get('tearDown', lambda self: None)
        def wrappedTearDown(self):
            tearDown(self)
            for key in self.logHandlers:
                self.logger.removeHandler(self.logHandlers[key])
        dct['tearDown'] = wrappedTearDown

        # return the class instance with the replaced setUp/tearDown
        return type.__new__(cls, name, bases, dct)

LABEL_TEST_LOGGER = "unittests"

class TestCase(unittest.TestCase):

    def assertContains(self, value, enumerable):
        self.assertTrue(type(enumerable) in (bytes, list, str))
        if type(enumerable) is list:
            # list
            self.assertTrue(value in enumerable)
        else:
            # bytes/str
            self.assertTrue(value in enumerable)

    def assertDoesNotContain(self, value, enumerable):
        self.assertTrue(type(enumerable) in (bytes, list, str))
        if type(enumerable) is list:
            # list
            self.assertFalse(value in enumerable)
        else:
            # bytes/str
            self.assertFalse(value in enumerable)

    def assertEmpty(self, obj):
        self.assertEqual(0, len(obj))

    def assertEndsWith(self, expected, val):
        self.assertTrue(val.endswith(expected))

    def assertNone(self, value):
        self.assertEqual(None, value)

    def assertNotEmpty(self, obj):
        self.assertNotEqual(0, len(obj))

    def assertSingle(self, obj, condition = None):
        if condition is None:
            self.assertEqual(1, len(obj))
            if type(obj) is dict:
                return obj.items()[0]
            return obj[0]

        # Specific condition
        matches = [i for i in obj if condition(i)]
        self.assertEqual(1, len(matches))
        return matches.pop()

    def assertStartsWith(self, expected, val):
        self.assertTrue(val.startswith(expected))
