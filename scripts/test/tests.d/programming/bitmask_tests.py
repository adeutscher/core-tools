#!/usr/bin/env python

import common, unittest

mod = common.load('bitmask', common.TOOLS_DIR + '/scripts/programming/bitmask.py')
mod.orig_usage = mod.usage
mod.orig_colour_text = mod.colour_text

class BitmaskTests(common.TestCase):

    def setUp(self):
        self.lines = []
        mod.colour_text = lambda l,c=None: l
        mod.print = lambda l: self.lines.append(l)

    def assertUsage(self, line):
        self.assertEqual('Usage: bitmask.py number [mask]', self.lines[-1])

    def assertFails(self, args):
        with self.assertRaises(SystemExit) as ex:
            mod.main(args)
        self.assertEqual(ex.exception.code, 1)
        self.assertUsage(self.lines[-1])

    def test_main_error_bad_first(self):
        self.assertFails(['0'])
        self.assertEqual(3, len(self.lines))
        self.assertEqual('Number value must be greater than zero.', self.lines[-2])

    def test_main_error_bad_second(self):
        self.assertFails(['1', '0'])

    def test_main_ok_compare_fullmatch_a(self):
        mod.main(['0x0f', '15'])
        self.assertEqual('Testing a value of 15 (0x00000f) against a mask of 15 (0x00000f).', self.lines[0])
        self.assertEqual('Result: 15 & 15 = 15 (Yes, Full Match)', self.lines[1])

    def test_main_ok_compare_partmatch_a(self):
        mod.main(['0x0f', '7'])
        self.assertEqual('Testing a value of 15 (0x00000f) against a mask of 7 (0x000007).', self.lines[0])
        self.assertEqual('Result: 15 & 7 = 7 (Yes, Partial Match)', self.lines[1])

    def test_main_ok_compare_nomatch_a(self):
        mod.main(['11', '4'])
        self.assertEqual('Result: 11 & 4 = 0 (No Match)', self.lines[-1])

    def test_main_ok_compare_nomatch_a(self):
        mod.main(['0x20', '0x10'])
        self.assertEqual('Result: 32 & 16 = 0 (No Match)', self.lines[-1])

    def test_main_ok_flags_a(self):
        mod.main(['11'])
        self.assertEqual('Getting the bitmask flags in value of 11 (0x00000b)', self.lines[0])
        self.assertEqual('2 ^ 000: (         1, 0x00000001): 1 (True)', self.lines[1])
        self.assertEqual('2 ^ 001: (         2, 0x00000002): 1 (True)', self.lines[2])
        self.assertEqual('2 ^ 002: (         4, 0x00000004): 0 (False)', self.lines[3])
        self.assertEqual('2 ^ 003: (         8, 0x00000008): 1 (True)', self.lines[4])

    def test_usage(self):
        with self.assertRaises(SystemExit) as ex:
            mod.usage()
        self.assertEqual(ex.exception.code, 1)
        line = self.assertSingle(self.lines)
        self.assertUsage(line)

class BitmaskValueTests(common.TestCase):

    def setUp(self):
        self.lines = []
        mod.colour_text = lambda l: l
        mod.print = lambda l: self.lines.append(l)

    def test_getValue_error_negative_a(self):

        value = mod.getValue(['-1'], 0, 'foo')
        line = self.assertSingle(self.lines)

        self.assertNone(value)
        self.assertEqual('Invalid foo: -1', line)

    def test_getValue_error_negative_b(self):

        value = mod.getValue(['0'], 0, 'foo')
        line = self.assertSingle(self.lines)

        self.assertNone(value)
        self.assertEqual('Invalid foo: 0', line)

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
