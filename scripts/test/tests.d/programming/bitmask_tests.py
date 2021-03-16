#!/usr/bin/env python

import common, unittest

mod = common.load('bitmask', common.TOOLS_DIR + '/scripts/programming/bitmask.py')
mod.orig_usage = mod.usage
mod.orig_colour_text = mod.colour_text

class BitmaskTests(common.TestCase):

    def setUp(self):
        self.lines = []
        mod.colour_text = lambda l: l
        mod.print = lambda l: self.lines.append(l)

    def test_usage(self):
        with self.assertRaises(SystemExit) as ex:
            mod.usage()
        self.assertEqual(ex.exception.code, 1)

        line = self.assertSingle(self.lines)
        self.assertEqual('Usage: bitmask.py number [mask]', line)


class BitmaskValueTests(common.TestCase):

    def setUp(self):
        self.lines = []
        mod.colour_text = lambda l: l
        mod.print = lambda l: self.lines.append(l)

    def test_getValue_error_negative(self):

        value = mod.getValue(['-1'], 0, 'foo')
        line = self.assertSingle(self.lines)

        self.assertNone(value)
        self.assertEqual('Invalid foo: -1', line)

    def test_getValue_error_parse(self):

        value = mod.getValue(['bar'], 0, 'foo')
        line = self.assertSingle(self.lines)

        self.assertNone(value)
        self.assertStartsWith('Invalid foo: bar (', line)

    def test_getValue_error_out_of_bounds(self):

        value = mod.getValue([], 1, 'foo')
        line = self.assertSingle(self.lines)

        self.assertNone(value)
        self.assertEqual('No foo provided.', line)

    def test_getValue_ok_dec_a(self):
        value = mod.getValue(['foo', '16'], 1, 'label')
        self.assertEqual(16, value)

    def test_getValue_ok_dec_b(self):
        value = mod.getValue(['bar', 'foo', '52'], 2, 'label')
        self.assertEqual(52, value)

    def test_getValue_ok_hex_a(self):
        value = mod.getValue(['foo', '0x16'], 1, 'label')
        self.assertEqual(22, value)

    def test_getValue_ok_hex_b(self):
        value = mod.getValue(['bar', 'foo', '0x52'], 2, 'label')
        self.assertEqual(82, value)
