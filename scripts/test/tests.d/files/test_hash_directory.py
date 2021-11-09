#!/usr/bin/env python

import common, unittest
import csv, os, re, tempfile, sys

mod = common.load('hash_directory', common.TOOLS_DIR + '/scripts/files/hash_directory.py')

class ExpectedCase:
    def __init__(self, dir, key, md5=None, sha1=None, sha256=None, sha512=None):
        self.dir = dir
        self.key = key
        self.md5 = md5
        self.sha1 = sha1
        self.sha256 = sha256
        self.sha512 = sha512

class DataRow:
    def __init__(self, md5, sha1, sha256, sha512):
        self.md5 = md5
        self.sha1 = sha1
        self.sha256 = sha256
        self.sha512 = sha512

class HashDirectoryTests(common.TestCase, metaclass=common.LoggableTestCase):

    def confirm_file(self, path, expected_cases):
        self.assertTrue(os.path.isfile(path))

        data = {}
        with open(path, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                data[row[0]] = DataRow(row[1], row[2], row[3], row[4])
        for case in expected_cases:
            item = data.get(os.path.join(case.dir, case.key))
            self.assertNotEqual(None, item)

            if case.md5 is not None:
                self.assertEqual(case.md5, item.md5)
            if case.sha1 is not None:
                self.assertEqual(case.sha1, item.sha1)
            if case.sha256 is not None:
                self.assertEqual(case.sha256, item.sha256)
            if case.sha512 is not None:
                self.assertEqual(case.sha512, item.sha512)

    def setUp(self):
        mod.logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

    def writeFile(self, dir, path, contents):
        with open(os.path.join(dir, path), 'w') as f:
            f.write(contents)

    '''
    Confirm behavior when no arguments are provided.
    '''
    def test_noargs(self):

        code = mod.main([])
        self.assertEqual(1, code)

    def test_nodir(self):
        with tempfile.TemporaryDirectory() as td:
            with tempfile.TemporaryDirectory() as td2:
                path = os.path.join(td2, 'out.csv')
                code = mod.main(['-o', path])
                self.assertFalse(os.path.isfile(path))
                self.assertEqual(1, code)

    def test_nooutput(self):
        with tempfile.TemporaryDirectory() as td:
            badfile = os.path.join(td, 'foo')
            code = mod.main([td])
        self.assertEqual(1, code)

    def test_nosuchdir(self):
        with tempfile.TemporaryDirectory() as td:
            badfile = os.path.join(td, 'foo')
            code = mod.main([badfile])
        self.assertEqual(1, code)

    def test_run_multi_thread(self):
        with tempfile.TemporaryDirectory() as td:

            self.writeFile(td, 'a', 'abc')
            self.writeFile(td, 'b', 'abcd')
            self.writeFile(td, 'c', 'abcde')

            with tempfile.TemporaryDirectory() as td2:
                path = os.path.join(td2, 'out.csv')
                code = mod.main(['-o', path, td, '-w', '2'])
                self.assertEqual(0, code)

                expected_a = ExpectedCase(td, 'a',
                    '900150983cd24fb0d6963f7d28e17f72',
                    'a9993e364706816aba3e25717850c26c9cd0d89d',
                    'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
                    'ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f'
                )

                expected_b = ExpectedCase(td, 'b', 'e2fc714c4727ee9395f324cd2e7f331f')
                expected_c = ExpectedCase(td, 'c', None, '03de6c570bfe24bfc328ccd7ca46b76eadaf4334')
                cases = [expected_a, expected_b, expected_c]
                self.confirm_file(path, cases)

    def test_run_single_thread(self):
        with tempfile.TemporaryDirectory() as td:

            self.writeFile(td, 'a', '123')
            self.writeFile(td, 'b', '1234')
            self.writeFile(td, 'c', '12345')

            with tempfile.TemporaryDirectory() as td2:
                path = os.path.join(td2, 'out.csv')
                code = mod.main(['-o', path, td])
                self.assertEqual(0, code)

                expected_a = ExpectedCase(td, 'a', '202cb962ac59075b964b07152d234b70')
                expected_b = ExpectedCase(td, 'b', '81dc9bdb52d04dc20036dbd8313ed055')
                expected_c = ExpectedCase(td, 'c', '827ccb0eea8a706c4c34a16891f84e7b')
                cases = [expected_a, expected_b, expected_c]
                self.confirm_file(path, cases)
