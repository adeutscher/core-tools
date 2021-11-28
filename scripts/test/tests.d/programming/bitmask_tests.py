#!/usr/bin/env python

import common, unittest
from json import dump
from os.path import join
from tempfile import TemporaryDirectory as tempdir

class BitmaskTests(common.TestCase, metaclass=common.LoggableTestCase):

    def setUp(self):
        self.mod = common.load('bitmask', common.TOOLS_DIR + '/scripts/programming/bitmask.py')
        self.mod._enable_colours(False)
        self.mod.logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

    '''
    Confirm that the help menu was displayed.
    '''
    def assertUsage(self):
        errors = self.getLogs('error')
        self.assertStartsWith('Usage: bitmask.py', errors[-1])

    def run_cmd(self, args, should_exit=False, exit_code=None):

        if exit_code is None:
            if should_exit:
                exit_code = 1
            else:
                exit_code = 0

        if should_exit:
            with self.assertRaises(SystemExit) as ex:
                self.mod.main(args)
            self.assertEqual(exit_code, ex.exception.code)
            self.assertUsage()
        else:
            observed_exit_code = self.mod.main(args)
            self.assertEqual(exit_code, observed_exit_code)
        return self.getLogs('info')

    def test_main_error_bad_args(self):
        self.run_cmd(['--bad-args'], should_exit = True)
        errors = self.getLogs('error')
        self.assertStartsWith('Error parsing arguments:', errors[0])

    def test_main_error_bad_mask(self):
        self.run_cmd(['5', '-m', 'nope'], should_exit = True)
        errors = self.getLogs('error')
        self.assertEqual('Invalid mask: nope', errors[0])

    def test_main_error_guide_no_file(self):
        self.run_cmd(['5', '-g', 'nope'], should_exit = True)
        errors = self.getLogs('error')
        self.assertEqual('No such file: nope', errors[0])

    def test_main_error_guide_bad_json(self):
        with tempdir() as td:
            path = join(td, 'bad.json')
            with open(path, 'w') as f:
                f.write('{')
            self.run_cmd(['5', '-g', path], should_exit = True)
            errors = self.getLogs('error')
            self.assertStartsWith('Bad JSON content in %s:' % path, errors[0])

    def test_main_error_guide_bad_permissions(self):

        from os import chmod

        with tempdir() as td:
            path = join(td, 'bad.json')
            with open(path, 'w') as f:
                f.write('{')
            chmod(path, 0)
            self.run_cmd(['5', '-g', path], should_exit = True)
            errors = self.getLogs('error')
            self.assertStartsWith('Bad file permissions on %s:' % path, errors[0])

    def test_main_error_no_args(self):
        self.run_cmd([], should_exit = True)
        errors = self.getLogs('error')
        self.assertEqual('No values provided.', errors[0])

    def test_main_help(self):
        self.run_cmd(['-h'], should_exit = True, exit_code = 0)

    def test_main_KeyboardInterrupt(self):
        def explode(value, **kwargs):
            raise KeyboardInterrupt()

        self.mod.display = explode
        self.run_cmd(['5'], should_exit = False, exit_code = 130)

    def test_main_ok_basic(self):
        info = self.run_cmd(['12'])
        self.assertEqual(5, len(info))
        self.assertEqual('Getting the bitmask flags in value of 12 (0x00000c)', info[0])
        self.assertEqual('2 ^ 003: (         8, 0x00000008): 1 (True)', info[4])

    def test_main_ok_basic_hex(self):
        info = self.run_cmd(['0x05'])
        self.assertEqual(4, len(info))
        self.assertEqual('Getting the bitmask flags in value of 5 (0x000005)', info[0])
        self.assertEqual('2 ^ 002: (         4, 0x00000004): 1 (True)', info[3])

    def test_main_ok_guide(self):
        with tempdir() as td:
            guide = {2: 'Two', '0x04': 'Four'}
            path = join(td, 'g.json')
            with open(path, 'w') as f:
                dump(guide, f)
            info = self.run_cmd(['4', '-g', path])
            self.assertEqual(4, len(info))
            self.assertEndsWith(' Two', info[-2])
            self.assertEndsWith(' Four', info[-1])

    def test_main_ok_mask_full_match(self):
        info = self.run_cmd(['13', '-m', '12'])
        self.assertEqual(7, len(info))
        self.assertEqual('Filtering value of 13 (0x00000d) through a mask of 12 (0x00000c)', info[0])
        self.assertEqual('Result: 0x00000d & 0x00000c = 0x00000c (12) Full Match', info[1])
        self.assertEqual('Getting the bitmask flags in value of 12 (0x00000c)', info[2])
        self.assertEqual('2 ^ 003: (         8, 0x00000008): 1 (True)', info[6])

    def test_main_ok_mask_partial_match(self):
        info = self.run_cmd(['12', '-m', '5'])
        self.assertEqual(6, len(info))
        self.assertEqual('Filtering value of 12 (0x00000c) through a mask of 5 (0x000005)', info[0])
        self.assertEqual('Result: 0x00000c & 0x000005 = 0x000004 (4) Partial Match', info[1])
        self.assertEqual('Getting the bitmask flags in value of 4 (0x000004)', info[2])

    def test_main_ok_mask_no_match(self):
        info = self.run_cmd(['12', '-m', '3'])
        self.assertEqual(2, len(info))
        self.assertEqual('Filtering value of 12 (0x00000c) through a mask of 3 (0x000003)', info[0])
        self.assertEqual('Result: 0x00000c & 0x000003 = 0x000000 (0) No Match', info[1])

    def test_main_ok_only_true(self):
        info = self.run_cmd(['12', '-t'])
        self.assertEqual(3, len(info))
        self.assertEqual('Getting the bitmask flags in value of 12 (0x00000c)', info[0])
        self.assertEqual('2 ^ 003: (         8, 0x00000008): 1 (True)', info[2])
