import common, unittest
import os, re, tempfile, sys

mod = common.load('merge_directories', common.TOOLS_DIR + '/scripts/files/merge_directories.py')

class MergeDirectoriesTests(common.TestCase, metaclass=common.LoggableTestCase):

    def createFiles(self, directory, items):
        for i in items:
            path = os.path.join(directory, i)
            os.makedirs(os.path.dirname(path), exist_ok = True)
            with open(path, 'w') as f:
                f.write(items[i])

    def readFiles(self, directory):
        items = {}
        for (folder, core, files) in os.walk(directory):
            for f in files:
                path = os.path.join(directory, folder, f)
                with open(path, 'r') as fh:
                    items[re.sub('^/+', '', path.replace(directory, ''))] = fh.read()
        return items

    def setUp(self):
        mod.logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

    '''
    Confirm behavior when no arguments are provided.
    '''
    def test_noargs(self):

        code = mod.run(['script.py'])
        self.assertEqual(1, code)

        errors = self.getLogs('error')
        self.assertEqual(2, len(errors))
        self.assertContains('Insufficient input directories for merging.', errors)
        self.assertContains('No output directory specified.', errors)

    '''
    Confirm behavior when only the compile-mode flag is provided.
    Compared to test_noargs, should adjust phrasing of input directories.
    '''
    def test_noargs_compile(self):

        code = mod.run(['script.py', '-c'])
        self.assertEqual(1, code)

        errors = self.getLogs('error')
        self.assertEqual(2, len(errors))
        self.assertContains('Insufficient input directories for compile-mode merging.', errors)
        self.assertContains('No output directory specified.', errors)

    def test_nodir(self):

        with tempfile.TemporaryDirectory() as td:
            badfile = os.path.join(td, 'foo')
            code = mod.run(['script.py', '-i', badfile])
        self.assertEqual(1, code)

        errors = self.getLogs('error')
        self.assertEqual(2, len(errors))
        self.assertContains('No output directory specified.', errors)
        badfile_error = self.assertSingle(errors, lambda e: e.endswith('does not exist.'))

    def test_nodir_compile(self):

        with tempfile.TemporaryDirectory() as td:
            badfile = os.path.join(td, 'foo')
            code = mod.run(['script.py', '-c', '-i', badfile])
        self.assertEqual(1, code)

        errors = self.getLogs('error')
        self.assertEqual(3, len(errors))
        self.assertContains('No output directory specified.', errors)
        self.assertContains('Insufficient input directories for compile-mode merging.', errors)
        badfile_error = self.assertSingle(errors, lambda e: e.endswith('does not exist.'))

    def test_nodir_dst(self):
        with tempfile.TemporaryDirectory() as src1:
            with tempfile.TemporaryDirectory() as src2:
                dst = 'zoom/gloom/doom/bloom'
                code = mod.run(['script.py', '-i', src1, '-i', src2, '-o', dst], False)

        self.assertEqual(1, code)
        e = self.assertSingle(self.getLogs('error'))
        self.assertTrue(e.endswith('\' does not exist.'))
        self.assertTrue(e.startswith('Output directory \''))
        self.assertContains(dst, e)

    def test_nodir_dst_combine(self):
        with tempfile.TemporaryDirectory() as src1:
            with tempfile.TemporaryDirectory() as src2:
                with tempfile.TemporaryDirectory() as dst:
                    code = mod.run(['script.py', '-i', src1, '-i', src2, '-o', dst, '-c'], False)

        self.assertEqual(1, code)
        e = self.assertSingle(self.getLogs('error'))

        self.assertTrue(e.endswith('\' should not already exist.'))
        self.assertTrue(e.startswith('Output directory \''))
        self.assertContains(dst, e)

    def test_merge(self):

        files1 = {
            'a': 'a-contents',
            'b': 'b-contents'
        }

        files2 = {
            'c': 'c-contents',
            'dir/d': 'd-contents'
        }

        with tempfile.TemporaryDirectory() as src1:

            self.createFiles(src1, files1)

            with tempfile.TemporaryDirectory() as src2:

                self.createFiles(src2, files2)

                with tempfile.TemporaryDirectory() as dst:

                    code = mod.run(['script.py', '-i', src1, '-i', src2, '-o', dst], False)

                    self.assertEmpty(self.getLogs('error'))

                    self.assertEqual(0, code)

                    files_dst = self.readFiles(dst)

        self.assertEqual(4, len(files_dst))
        files_check = files1.copy()
        for i in files2:
            files_check[i] = files2[i]
        for i in files_dst:
            self.assertTrue(i in files_check)
            self.assertEqual(files_check[i], files_dst[i])

    def test_merge_combine_overlap(self):

        files1 = {
            'a.txt': 'a-contents',
            'b.txt': 'b-contents',
            'd.txt': 'd-contents'
        }

        files2 = {
            'a.txt': 'a-contents',
            'b.txt': 'b-contents-variant',
            'c': 'c-contents',
            'd.txt': 'd-contents.variant'
        }

        files3 = {
            'd.txt': 'd-contents.variant2'
        }

        with tempfile.TemporaryDirectory() as src1:

            self.createFiles(src1, files1)

            with tempfile.TemporaryDirectory() as src2:

                self.createFiles(src2, files2)

                with tempfile.TemporaryDirectory() as src3:

                    self.createFiles(src3, files3)

                    with tempfile.TemporaryDirectory() as dst_base:
                        dst = os.path.join(dst_base, 'out')

                        code = mod.run(['script.py', '-i', src1, '-i', src2, '-i', src3, '-o', dst, '-c'], False)

                        self.assertEqual(0, code)

                        files_dst = self.readFiles(dst)

        self.assertEmpty(self.getLogs('error'))

        self.assertEqual(7, len(files_dst))

        files_expected = files1.copy()
        files_expected['b.1.txt'] = files2['b.txt']
        files_expected['d.1.txt'] = files2['d.txt']
        files_expected['d.2.txt'] = files3['d.txt']
        files_expected['c'] = files2['c']

        for i in files_dst:
            self.assertTrue(i in files_expected)
            self.assertEqual(files_expected[i], files_dst[i])

        # Expecting one warning for the conflict
        warnings = self.getLogs('warning')
        self.assertEqual(3, len(warnings))
        for w in warnings:
            self.assertContains('Conflict', w)
        self.assertSingle(warnings, lambda w: 'b.1.txt' in w)
        self.assertSingle(warnings, lambda w: 'd.1.txt' in w)
        self.assertSingle(warnings, lambda w: 'd.2.txt' in w)

    def test_merge_overlap(self):

        files1 = {
            'a.txt': 'a-contents',
            'b.txt': 'b-contents',
            'd.txt': 'd-contents'
        }

        files2 = {
            'a.txt': 'a-contents',
            'b.txt': 'b-contents-variant',
            'c': 'c-contents',
            'd.txt': 'd-contents.variant'
        }

        files3 = {
            'd.txt': 'd-contents.variant2'
        }

        with tempfile.TemporaryDirectory() as src1:

            self.createFiles(src1, files1)

            with tempfile.TemporaryDirectory() as src2:

                self.createFiles(src2, files2)

                with tempfile.TemporaryDirectory() as src3:

                    self.createFiles(src3, files3)

                    with tempfile.TemporaryDirectory() as dst:

                        code = mod.run(['script.py', '-i', src1, '-i', src2, '-i', src3, '-o', dst], False)

                        self.assertEqual(0, code)

                        files_dst = self.readFiles(dst)

        self.assertEmpty(self.getLogs('error'))

        self.assertEqual(7, len(files_dst))

        files_expected = files1.copy()
        files_expected['b.1.txt'] = files2['b.txt']
        files_expected['d.1.txt'] = files2['d.txt']
        files_expected['d.2.txt'] = files3['d.txt']
        files_expected['c'] = files2['c']

        for i in files_dst:
            self.assertTrue(i in files_expected)
            self.assertEqual(files_expected[i], files_dst[i])

        # Expecting one warning for the conflict
        warnings = self.getLogs('warning')
        self.assertEqual(3, len(warnings))
        for w in warnings:
            self.assertContains('Conflict', w)
        self.assertSingle(warnings, lambda w: 'b.1.txt' in w)
        self.assertSingle(warnings, lambda w: 'd.1.txt' in w)
        self.assertSingle(warnings, lambda w: 'd.2.txt' in w)
