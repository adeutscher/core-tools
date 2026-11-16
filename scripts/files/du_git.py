#!/usr/bin/env python

'''
Summarize disk usage like `du -s`, but skip files that git repositories ignore.

Usage: ./du_git.py [-b] [-c] [path ...]

Sizes are printed in human readable units, like `du -h`. Use -b for an exact byte count.

Inside a git repository, untracked files matched by .gitignore (or the other
standard exclude files) are not counted. Tracked files, untracked files that
are not ignored, and the .git directory itself are all counted, so the result
is the size of the repository as it exists locally.

A .gitignore outside of a git repository has no effect, just as with git.

Like du, sizes are allocated disk usage and hard-linked files are counted once.
'''

import argparse, os, subprocess, sys
from math import ceil

HUMAN_UNITS = 'KMGTPEZY'

def format_human(size):
    '''
    Format a byte count the way `du -h` does: always round up, with one
    decimal place for values under 10.
    '''
    if size < 1024:
        return str(size)
    value = float(size)
    for i, unit in enumerate(HUMAN_UNITS):
        value /= 1024
        if value < 10:
            rounded = ceil(value * 10) / 10
            if rounded < 10:
                return '%.1f%s' % (rounded, unit)
            value = rounded
        rounded = ceil(value)
        if rounded < 1024 or i == len(HUMAN_UNITS) - 1:
            return '%d%s' % (rounded, unit)

def format_size(size, as_bytes):
    if as_bytes:
        return str(size)
    return format_human(size)

def get_disk_usage(st):
    # st_blocks is always in 512-byte units, regardless of the file system's block size.
    blocks = getattr(st, 'st_blocks', None)
    if blocks is None:
        return st.st_size # pragma: no cover
    return blocks * 512

def get_repo_root(path):
    '''
    Return the top level of the git work tree containing a directory, or None.
    '''
    try:
        proc = subprocess.run(['git', '-C', path, 'rev-parse', '--show-toplevel'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return None
    if proc.returncode:
        return None
    return os.path.realpath(proc.stdout.decode('utf-8', 'surrogateescape').rstrip('\n'))

def get_ignored_paths(path):
    '''
    Return the absolute paths of ignored, untracked entries under a directory.
    Ignored directories are listed once, instead of listing their contents.
    '''
    proc = subprocess.run(['git', '-C', path, 'ls-files', '-z', '--others', '--ignored', '--exclude-standard', '--directory'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        raise OSError(proc.stderr.decode('utf-8', 'replace').strip())
    paths = set()
    for entry in proc.stdout.decode('utf-8', 'surrogateescape').split('\0'):
        if entry:
            paths.add(os.path.normpath(os.path.join(path, entry)))
    return paths

def is_repo_root(path):
    if not os.path.exists(os.path.join(path, '.git')):
        return False
    # Confirm that the .git entry is a real repository, and not just a stray directory.
    return get_repo_root(path) == os.path.realpath(path)

class Counter:
    def __init__(self, error=None):
        self.error = error or (lambda message: print('du-git: %s' % message, file=sys.stderr))
        self.failed = False
        self.seen_inodes = set()

    def _add(self, st):
        if st.st_nlink > 1:
            key = (st.st_dev, st.st_ino)
            if key in self.seen_inodes:
                return 0
            self.seen_inodes.add(key)
        return get_disk_usage(st)

    def _fail(self, message):
        self.failed = True
        self.error(message)

    def _get_ignored(self, path):
        try:
            return get_ignored_paths(path)
        except OSError as e:
            self._fail('cannot list ignored files in %s: %s' % (path, e))
            return set()

    def measure(self, path):
        '''
        Return the disk usage of a path in bytes, or None if it could not be read.
        '''
        try:
            st = os.lstat(path)
        except OSError as e:
            self._fail("cannot access '%s': %s" % (path, e.strerror))
            return None

        if not os.path.isdir(path) or os.path.islink(path):
            # A single file only needs to be checked against its parent's repository.
            parent = os.path.dirname(os.path.abspath(path))
            if get_repo_root(parent) and os.path.normpath(os.path.abspath(path)) in self._get_ignored(parent):
                return 0
            return self._add(st)

        top = os.path.normpath(os.path.abspath(path))
        # A path inside a repository is subject to that repository's ignore rules.
        ignored = self._get_ignored(top) if get_repo_root(top) else set()
        if top in ignored:
            return 0

        total = self._add(st)
        on_error = lambda e: self._fail("cannot read directory '%s': %s" % (e.filename, e.strerror))
        for dirpath, dirnames, filenames in os.walk(top, onerror=on_error):
            if dirpath != top and '.git' in dirnames + filenames and is_repo_root(dirpath):
                # Nested repositories, such as submodules or clones within a
                # plain directory, apply their own ignore rules.
                ignored |= self._get_ignored(dirpath)

            kept = []
            for name in dirnames:
                child = os.path.join(dirpath, name)
                if child in ignored:
                    continue
                try:
                    total += self._add(os.lstat(child))
                except OSError as e:
                    self._fail("cannot access '%s': %s" % (child, e.strerror))
                    continue
                kept.append(name)
            dirnames[:] = kept

            for name in filenames:
                child = os.path.join(dirpath, name)
                if child in ignored:
                    continue
                try:
                    total += self._add(os.lstat(child))
                except OSError as e:
                    self._fail("cannot access '%s': %s" % (child, e.strerror))
        return total

def main(args_raw, out=None):
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog='du-git',
        description='Summarize disk usage like `du -s`, skipping files ignored by git repositories.')
    parser.add_argument('-b', '--bytes', dest='as_bytes', action='store_true', help='Print exact sizes in bytes, instead of human readable units (e.g. 1.5K, 234M, 2G).')
    parser.add_argument('-c', '--total', action='store_true', help='Produce a grand total.')
    parser.add_argument('paths', nargs='*', metavar='path', help='Paths to summarize (default: current directory).')
    try:
        args = parser.parse_args(args_raw)
    except SystemExit as e:
        return e.code

    counter = Counter()
    grand_total = 0
    try:
        for path in args.paths or ['.']:
            size = counter.measure(path)
            if size is None:
                continue
            grand_total += size
            out.write('%s\t%s\n' % (format_size(size, args.as_bytes), path))
        if args.total:
            out.write('%s\ttotal\n' % format_size(grand_total, args.as_bytes))
    except KeyboardInterrupt:
        print('')
        return 130
    return 1 if counter.failed else 0

if __name__ == '__main__':
    exit(main(sys.argv[1:])) # pragma: no cover
