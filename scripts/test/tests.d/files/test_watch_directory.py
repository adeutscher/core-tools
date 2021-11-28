#!/usr/bin/env python

import common, unittest
from os.path import isfile, join
from os import chmod, remove, stat as do_stat
from stat import S_IEXEC
from tempfile import TemporaryDirectory as tempdir

def get_fixtures(td):
        log_path = join(td, 'log.txt')
        script_path = join(td, 'script.sh')
        make_test_script(script_path, log_path)
        return script_path, log_path

def make_test_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

def make_test_script(script_path, log_path):
    with open(script_path, 'w') as f:
        content = '#!/bin/bash\n echo "${1}" >> "%s"' % log_path
        f.write(content)
    st = do_stat(script_path)
    chmod(script_path, st.st_mode | S_IEXEC)

class WatchDirectoryArgumentTests(common.TestCase, metaclass=common.LoggableTestCase):
    def setUp(self):
        self.mod = common.load('watch_directory', common.TOOLS_DIR + '/scripts/files/watch_directory.py')
        self.mod._enable_colours(False)
        self.mod._logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

    def check_error(self, prefix, content=None):
        errors = self.getLogs('error')
        self.assertEqual(2, len(errors))
        self.assertStartsWith('Usage:', errors[1])

        self.assertStartsWith(prefix, errors[0])
        if content:
            self.assertContains(content, errors[0])

    def run_fail(self, cmd):
        with self.assertRaises(SystemExit) as ex:
                self.mod._parse_args(cmd)
        self.assertEqual(1, ex.exception.code)
        self.assertEmpty(self.getLogs('info'))

    def test_main_error_bad_args(self):
        self.run_fail(['--bad-args'])
        self.check_error('Error parsing arguments:')

    def test_fail_bad_number(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            with tempdir() as file_dir:
                self.run_fail(['-s', script_path, file_dir, '-w', 'z'])
        self.check_error('Invalid number: ', 'z')

    def test_fail_no_script(self):
        with tempdir() as file_dir:
            script_path = join(file_dir, 'a')
            self.run_fail(['-s', script_path, file_dir])
        self.check_error('Invalid script path: ', script_path)

    def test_run_fail_no_dir_exist(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            with tempdir() as file_dir:
                bad_path = join(file_dir, 'a')
                self.run_fail(['-s', script_path, bad_path])
        self.check_error('Invalid target directory path: ', bad_path)

    def test_fail_no_arguments(self):

        self.run_fail([])
        self.assertEmpty(self.getLogs('info'))

        errors = self.getLogs('error')
        self.assertEqual(3, len(errors))
        self.assertStartsWith('Usage:', errors[-1])

        self.assertContains('No script provided.', errors)
        self.assertContains('No directory provided.', errors)

    def test_fail_no_dir_provided(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            self.run_fail(['-s', script_path])
        self.check_error('No directory provided.')

    def test_fail_no_script_provided(self):
        with tempdir() as file_dir:
            self.run_fail([file_dir])
        self.check_error('No script provided.')

    def test_fail_script_not_executable(self):
        with tempdir() as file_dir:
            script_path = join(file_dir, 'a')
            make_test_file(script_path, 'moot')
            self.run_fail(['-s', script_path, file_dir])
        self.check_error('Invalid script path: ', script_path)

    def test_hexit(self):
        with self.assertRaises(SystemExit) as ex:
                self.mod._parse_args(['-h'])
        self.assertEqual(0, ex.exception.code)
        msg = self.assertSingle(self.getLogs('error'))
        self.assertStartsWith('Usage: ', msg)

    def test_pass(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            with tempdir() as file_dir:
                data = self.mod._parse_args(['-s', script_path, file_dir])
        self.assertEmpty(self.getLogs('info'))
        self.assertEmpty(self.getLogs('error'))

        self.assertFalse(data.get('recursive', False))
        self.assertNone(data.get('workers'))

    def test_pass_recursive(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            with tempdir() as file_dir:
                data = self.mod._parse_args(['-s', script_path, file_dir, '-r'])
        self.assertEmpty(self.getLogs('info'))
        self.assertEmpty(self.getLogs('error'))

        self.assertTrue(data.get('recursive', False))
        self.assertNone(data.get('workers'))

    def test_pass_workers(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            with tempdir() as file_dir:
                data = self.mod._parse_args(['-s', script_path, file_dir, '-w', '5'])
        self.assertEmpty(self.getLogs('info'))
        self.assertEmpty(self.getLogs('error'))

        self.assertFalse(data.get('recursive', False))
        self.assertEqual(5, data.get('workers'))


class WatchDirectoryRunTests(common.TestCase, metaclass=common.LoggableTestCase):

    def setUp(self):
        self.mod = common.load('watch_directory', common.TOOLS_DIR + '/scripts/files/watch_directory.py')
        self.mod._enable_colours(False)
        self.mod._logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

    def run_cmd(self, cmd, execute_only=True):
        if execute_only:
            cmd.append('--execute-only')
        exit_code = self.mod._main(cmd)
        self.assertEqual(0, exit_code)

    def test_run_executeonly_content(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            with tempdir() as file_dir:

                file_1 = join(file_dir, 'a')
                file_2 = join(file_dir, 'b')
                file_3 = join(file_dir, 'c')

                make_test_file(file_1, 'abc')
                make_test_file(file_2, '123')
                # Make file_3 EMPTY, so that it should not be run.
                make_test_file(file_3, '')

                import time

                self.run_cmd(['-s', script_path, file_dir])
            # Expected to have run the script twice.
            self.assertTrue(isfile(log_path))

            with open(log_path) as f:
                lines = [l.strip() for l in f.readlines()]
            self.assertContains(file_1, lines)
            self.assertContains(file_2, lines)
            self.assertDoesNotContain(file_3, lines)

            info = self.getLogs('info')
            for path in [file_1, file_2]:
                self.assertContains(f'Handling file: {path}', info)
                self.assertContains(f'Finished with file: {path}', info)

    def test_run_executeonly_none(self):
        with tempdir() as management_dir:
            script_path, log_path = get_fixtures(management_dir)
            with tempdir() as file_dir:
                self.run_cmd(['-s', script_path, file_dir])
            # No files in this directory, so nothing got run.
            self.assertFalse(isfile(log_path))
