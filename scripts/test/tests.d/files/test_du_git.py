#!/usr/bin/env python

import common, unittest
import io, os, subprocess, tempfile

mod = common.load('du_git', common.TOOLS_DIR + '/scripts/files/du_git.py')

'''
Tests for measuring disk usage while skipping files ignored by git.
'''
class DuGitTests(common.TestCase):

    def setUp(self):
        self.errors = []
        self.counter = mod.Counter(self.errors.append)

    def git(self, path, *args):
        subprocess.run(['git', '-C', path] + list(args), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def init_repo(self, path):
        os.makedirs(path, exist_ok=True)
        self.git(path, 'init', '-q')

    def measure(self, path):
        return self.counter.measure(path)

    def run_main(self, args):
        out = io.StringIO()
        code = mod.main(args, out)
        return code, out.getvalue()

    '''
    Write a file of a given size, returning its disk usage in bytes.
    '''
    def write(self, path, size=50000, contents=None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(contents if contents is not None else os.urandom(size))
        return mod.get_disk_usage(os.lstat(path))

    def usage(self, path):
        return mod.get_disk_usage(os.lstat(path))

    def test_format_human(self):
        # Expected values confirmed against `du -h --apparent-size`.
        cases = [
            (0, '0'),
            (1023, '1023'),
            (1024, '1.0K'),
            (1025, '1.1K'),
            (10239, '10K'),
            (10241, '11K'),
            (1048063, '1.0M'),
            (1048575, '1.0M'),
            (1572864, '1.5M'),
            (1073741824, '1.0G'),
        ]
        for size, expected in cases:
            self.assertEqual(expected, mod.format_human(size))

    def test_format_size(self):
        self.assertEqual('0', mod.format_size(0, True))
        self.assertEqual('4097', mod.format_size(4097, True))
        self.assertEqual('1572864', mod.format_size(1572864, True))
        self.assertEqual('4.1K', mod.format_size(4097, False))
        self.assertEqual('1.5M', mod.format_size(1572864, False))

    def test_plain_directory_matches_du(self):
        with tempfile.TemporaryDirectory() as td:
            self.write(os.path.join(td, 'a'))
            self.write(os.path.join(td, 'sub', 'b'), 120000)
            os.symlink('a', os.path.join(td, 'link'))
            for du_args, args in [(['-s', '-h'], []), (['-s', '-B1'], ['-b'])]:
                proc = subprocess.run(['du'] + du_args + [td], stdout=subprocess.PIPE, check=True)
                expected = proc.stdout.decode().split('\t')[0]
                code, output = self.run_main(args + [td])
                self.assertEqual(0, code)
                self.assertEqual('%s\t%s\n' % (expected, td), output)

    def test_gitignore_without_repo(self):
        '''
        A .gitignore outside of a git repository is a red herring, and must not exclude anything.
        '''
        with tempfile.TemporaryDirectory() as td:
            herring = os.path.join(td, 'herring')
            self.write(os.path.join(herring, '.gitignore'), contents=b'*\n')
            data = self.write(os.path.join(herring, 'data'), 200000)
            self.write(os.path.join(herring, 'build', 'out'), 100000)
            self.assertEqual(None, mod.get_repo_root(herring))
            self.assertFalse(mod.is_repo_root(herring))
            self.assertEqual(None, mod.get_repo_root(td))

            size = self.measure(herring)
            self.assertTrue(size > 300000)
            self.assertTrue(size >= data)
            self.assertEqual([], self.errors)

    def test_fake_git_directory(self):
        '''
        An empty .git directory alongside a .gitignore does not make a repository.
        '''
        with tempfile.TemporaryDirectory() as td:
            os.mkdir(os.path.join(td, '.git'))
            self.write(os.path.join(td, '.gitignore'), contents=b'*.bin\n')
            self.write(os.path.join(td, 'data.bin'), 200000)
            self.assertFalse(mod.is_repo_root(td))
            self.assertTrue(self.measure(td) > 200000)
            self.assertEqual([], self.errors)

    def test_repo_ignored_files(self):
        with tempfile.TemporaryDirectory() as td:
            repo = os.path.join(td, 'repo')
            self.init_repo(repo)
            self.write(os.path.join(repo, '.gitignore'), contents=b'build/\n*.log\n')
            self.write(os.path.join(repo, 'src', 'main.c'), 1000)
            self.write(os.path.join(repo, 'untracked.txt'), 1000)
            self.git(repo, 'add', '.gitignore', 'src')
            self.git(repo, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'init')
            baseline = self.measure(repo)

            self.write(os.path.join(repo, 'build', 'deep', 'out.o'), 500000)
            self.write(os.path.join(repo, 'src', 'debug.log'), 300000)
            self.assertEqual(baseline, self.measure(repo))
            self.assertEqual(0, self.measure(os.path.join(repo, 'build')))
            self.assertEqual(0, self.measure(os.path.join(repo, 'src', 'debug.log')))

            # Untracked files that are not ignored still count.
            extra = self.write(os.path.join(repo, 'notes.txt'), 100000)
            self.assertEqual(baseline + extra, self.measure(repo))
            self.assertEqual([], self.errors)

    def test_tracked_file_matching_gitignore(self):
        '''
        Files that are tracked count, even if a .gitignore pattern matches them.
        '''
        with tempfile.TemporaryDirectory() as td:
            self.init_repo(td)
            size = self.write(os.path.join(td, 'keep.log'), 200000)
            self.git(td, 'add', 'keep.log')
            self.write(os.path.join(td, '.gitignore'), contents=b'*.log\n')
            self.assertEqual(size, self.measure(os.path.join(td, 'keep.log')))
            self.assertTrue(self.measure(td) > 200000)

    def test_subdirectory_of_repo(self):
        with tempfile.TemporaryDirectory() as td:
            self.init_repo(td)
            self.write(os.path.join(td, '.gitignore'), contents=b'*.tmp\n')
            sub = os.path.join(td, 'sub')
            kept = self.write(os.path.join(sub, 'kept'), 50000)
            self.write(os.path.join(sub, 'dropped.tmp'), 200000)
            self.assertEqual(self.usage(sub) + kept, self.measure(sub))

    def test_herring_inside_repo_applies(self):
        '''
        Inside of a repository, a nested .gitignore is real and does apply.
        '''
        with tempfile.TemporaryDirectory() as td:
            self.init_repo(td)
            sub = os.path.join(td, 'sub')
            self.write(os.path.join(sub, '.gitignore'), contents=b'*\n')
            self.write(os.path.join(sub, 'data'), 200000)
            self.assertEqual(self.usage(sub), self.measure(sub))

    def test_repos_inside_plain_directory(self):
        '''
        A plain directory holding a repository and a red herring directory.
        Only the repository's ignore rules apply.
        '''
        with tempfile.TemporaryDirectory() as td:
            repo = os.path.join(td, 'repo')
            self.init_repo(repo)
            self.write(os.path.join(repo, '.gitignore'), contents=b'*.bin\n')
            self.write(os.path.join(repo, 'ignored.bin'), 400000)

            herring = os.path.join(td, 'herring')
            self.write(os.path.join(herring, '.gitignore'), contents=b'*.bin\n')
            herring_data = self.write(os.path.join(herring, 'kept.bin'), 300000)

            repo_size = self.measure(repo)
            herring_size = self.measure(herring)
            self.assertEqual(self.usage(td) + repo_size + herring_size, self.measure(td))
            self.assertTrue(herring_size >= herring_data)
            self.assertTrue(repo_size < 400000)

    def test_nested_repo(self):
        '''
        A repository inside another repository applies its own rules.
        '''
        with tempfile.TemporaryDirectory() as td:
            self.init_repo(td)
            self.write(os.path.join(td, '.gitignore'), contents=b'*.outer\n')
            inner = os.path.join(td, 'inner')
            self.init_repo(inner)
            self.write(os.path.join(inner, '.gitignore'), contents=b'*.inner\n')
            self.write(os.path.join(inner, 'a.inner'), 300000)
            self.write(os.path.join(td, 'a.outer'), 300000)
            inner_size = self.measure(inner)
            self.assertTrue(inner_size < 300000)
            self.assertTrue(self.measure(td) < 300000)

    def test_hard_links_counted_once(self):
        with tempfile.TemporaryDirectory() as td:
            size = self.write(os.path.join(td, 'a'), 200000)
            os.link(os.path.join(td, 'a'), os.path.join(td, 'b'))
            self.assertEqual(self.usage(td) + size, self.measure(td))

    def test_main_human_and_total(self):
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, 'a')
            b = os.path.join(td, 'b')
            self.write(a, 2048 * 1024)
            self.write(b, 1024 * 1024)
            code, output = self.run_main(['-c', a, b])
            self.assertEqual(0, code)
            lines = output.splitlines()
            self.assertEqual(3, len(lines))
            self.assertEqual('2.0M\t%s' % a, lines[0])
            self.assertEqual('1.0M\t%s' % b, lines[1])
            self.assertEqual('3.0M\ttotal', lines[2])

    def test_main_bytes_and_total(self):
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, 'a')
            b = os.path.join(td, 'b')
            size_a = self.write(a, 200000)
            size_b = self.write(b, 100000)
            code, output = self.run_main(['-b', '-c', a, b])
            self.assertEqual(0, code)
            self.assertEqual('%d\t%s\n%d\t%s\n%d\ttotal\n' % (size_a, a, size_b, b, size_a + size_b), output)

    def test_main_default_path(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                code, output = self.run_main([])
            finally:
                os.chdir(cwd)
            self.assertEqual(0, code)
            self.assertTrue(output.endswith('\t.\n'))

    def test_main_missing_path(self):
        with tempfile.TemporaryDirectory() as td:
            missing = os.path.join(td, 'missing')
            self.write(os.path.join(td, 'a'), 1000)
            code, output = self.run_main([missing, td])
            self.assertEqual(1, code)
            self.assertEqual(1, len(output.splitlines()))
            self.assertTrue(output.endswith('\t%s\n' % td))

    def test_main_bad_args(self):
        self.assertEqual(2, self.run_main(['--no-such-option'])[0])
