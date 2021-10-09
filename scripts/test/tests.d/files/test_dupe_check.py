#!/usr/bin/python

import common, os, tempfile, unittest

mod = common.load('dupe_check', common.TOOLS_DIR + '/scripts/files/dupe_check.py')

'''
Tests duplication checks.
'''
class DupeCheckTests(common.TestCase):

    def setUp(self):
        self.report = None

    def assertFail(self, args):
        self.assertEqual(1, mod.main(args))

    def assertSuccess(self, args):
        callback = lambda report: self.set_report(report)
        # callback =
        self.assertEqual(0, mod.main(args, callback))

    '''
    Raise a keyboard interrupt, for test_main_fail_keyboardinterrupt test.
    '''
    def raise_keyboardinterrupt(self, report):
        raise KeyboardInterrupt();

    def set_report(self, report):
        self.report = report

    def test_main_dupes(self):
        with tempfile.TemporaryDirectory() as td:
            self.write(td, 'a', 'contents')
            self.write(td, 'b', 'contents')
            self.write(td, 'b-c', 'contents-b')

            self.assertSuccess([td])
            self.assertNotEqual(None, self.report)

            self.assertEqual(td, self.assertSingle(self.report['paths']))
            dupes = self.assertSingle(self.report['dupes'])
            self.assertSingle(dupes.storage, lambda c: os.path.basename(c.path) == 'a')
            self.assertSingle(dupes.storage, lambda c: os.path.basename(c.path) == 'b')

    def test_main_fail_empty_args(self):
        self.assertFail([])

    def test_main_fail_keyboardinterrupt(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEquals(127, mod.main([td], self.raise_keyboardinterrupt))

    def test_report_dupes(self):
        with tempfile.TemporaryDirectory() as td:
            self.write(td, 'a', 'contents')
            self.write(td, 'b', 'contents')
            self.write(td, 'b-c', 'contents-b')

            report = mod.ReportWrapper().get_report(td)


            self.assertEqual(td, self.assertSingle(report['paths']))
            dupes = self.assertSingle(report['dupes'])
            self.assertSingle(dupes.storage, lambda c: os.path.basename(c.path) == 'a')
            self.assertSingle(dupes.storage, lambda c: os.path.basename(c.path) == 'b')

    def test_report_dupes_print(self):
        with tempfile.TemporaryDirectory() as td:
            self.write(td, 'a', 'contents')
            self.write(td, 'b', 'contents')
            self.write(td, 'b-c', 'contents-b')

            report = mod.ReportWrapper().get_report(td)


            self.assertEqual(td, self.assertSingle(report['paths']))
            dupes = self.assertSingle(report['dupes'])
            self.assertSingle(dupes.storage, lambda c: os.path.basename(c.path) == 'a')
            self.assertSingle(dupes.storage, lambda c: os.path.basename(c.path) == 'b')

            # Call the report method.
            # For the moment, I don't have any way verify output,
            #   but I can at least confirm that it doesn't throw an exception
            mod.print_report(report)

    def test_report_nodupes_1(self):
        with tempfile.TemporaryDirectory() as td:
            self.write(td, 'a', 'contents')
            self.write(td, 'b', 'contents-b')

            report = mod.ReportWrapper().get_report(td)

            self.assertEqual(td, self.assertSingle(report['paths']))
            self.assertEmpty(report['dupes'])

    def write(self, directory, fname, contents):
        path = os.path.join(directory, fname)
        with open(path, 'w') as f:
            f.write(contents)
        return path

'''
Tests the FileInstance class used to track file status.
'''
class FileInstanceTests(common.TestCase):

    def test_length(self):
        with tempfile.TemporaryDirectory() as td:
            for content in ['a', 'abc']:
                path = self.write(td, 'a', content)
                instance = mod.FileInstance(path)
                self.assertEqual(len(content), instance.length)

    def test_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            # Write a file of greater than 2MB, otherwise the short hash will be used.
            content = ''.ljust(2 * (2 ** 20) + 1, ' ')
            path = self.write(td, 'a', content)
            instance = mod.FileInstance(path)

            hash_short = instance.hash_short
            hash_long = instance.hash_long

            # Confirm that the short hash is an incomplete hash.
            self.assertNotEqual(hash_short, hash_long)

            # Make a second file instance with exactly 2MB.
            # This file's short-hash should be equal to it's long-hash
            path2 = self.write(td, 'b', content[:-1])
            instance2 = mod.FileInstance(path2)
            hash_short2 = instance2.hash_short
            hash_long2 = instance2.hash_long
            self.assertEqual(hash_short2, hash_long2)

    def test_str(self):
        # Test FileInstance's __str__ function

        # We will not be actually reading the file, so we can make up a path name.
        path = '/moot'
        instance = mod.FileInstance(path)
        self.assertEqual(path, str(instance))


    def write(self, directory, fname, contents):
        path = os.path.join(directory, fname)
        with open(path, 'w') as f:
            f.write(contents)
        return path

'''
Tests for standalone functions
'''
class FunctionTests(common.TestCase):

    def test_translate_digest(self):
        # Compressed form of hash.
        compressed = b'\xbf\x07.\x91\x19\x07{NvCz\x93\x98g\x87\xef'
        # Decompressed form of hash
        # This would be the content of hexdigest() from a hashing algorithm.
        expected = 'bf072e9119077b4e76437a93986787ef'
        self.assertEqual(expected, mod._translate_digest(compressed))
