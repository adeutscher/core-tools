#!/usr/bin/env python

'''
File duplicate reporter.

Usage: ./dupe_check.py path

TODOs:

* Improve output, make testable with logging
* Add more argument-options:
  * Delete duplicates (with/without prompting)
  * Multi-threading (see below for more detail)
* Byte-for-byte safety check, to name sure that there are no files with identical sizes/hashes, yet different content.
  * See: https://shattered.io/ .
  * This is a feature used by fdupes (reference: https://en.wikipedia.org/wiki/Fdupes)
* Benchmark against other dupe-checking solutions (see below for more detail)

On multi-threading:
    Eventually, I'd like to try making this script optionally multi-threaded.

    According to the author of jdupes, multi-threading won't see improvement
    without enterprise-level hardware. This statement was made 2020-07-11, so it
    should be up-to-date for 2021-10-08.

    That being said:
        * I'm curious about how well the author's statement holds up against my own habit
            of using tmpfs for nonessential files. Is a memory-based file system faster,
            or will the single-threaded applications be able to take just as much
            advantage of the extra resources? Due to the practice of using lenths and
            partial hashes (in my case, taking the hash of the first 2MB of a file),
            I wouldn't be surprised if any performance gain is negligible.
        * Even if it doesn't yield a performance improvement, it will be a fun exercise
            with doing some sort of distributed workload in Python. I can then eventually
            apply the same code to other tasks that could take better advantage.

 On benchmark comparisons:

    I'd like to compare speed performance against the following dupe-checking programs:
        * fdupes, written in C
        * jclone, written in C
        * fclones, written in Rust

    I expect that these C/Rust programs will blow the performance of this Python script out of the water,
      but I'm curious about what the gap is.
'''

from hashlib import md5
import io, os, sys

class FileInstance:

    def __get_hash(self, single_iteration):
        with open(self.__path, 'rb') as stream:
            alg = md5()
            for chunk in self.__read_in_chunks(stream, single_iteration):
                alg.update(chunk)
            return alg.digest()

    def __get_hash_long(self):
        if self.length <= self.__chunk_size:
            # File is smaller than our chunk size,
            #   so short hash is equal to our long hash
            return self.hash_short

        if self.__hash_long is None:
            self.__hash_long = self.__get_hash(False)
        return self.__hash_long

    def __get_hash_short(self):
        if self.__hash_short is None:
            self.__hash_short = self.__get_hash(True)
        return self.__hash_short

    def __get_length(self):
        if self.__length is None:
            self.__length = os.stat(self.__path).st_size
        return self.__length

    def __init__(self, path):
        self.__path = path

        self.__length = None
        self.__hash_long = None
        self.__hash_short = None

        self.__chunk_size = 2 * (2 ** 20) # 2MB

    def __read_in_chunks(self, file_object, single_iteration):
        """Read a file in fixed-size chunks.

        Args:
            file_object: An opened file-like object supporting read().
            single_iteration: Set to True to only get a single chunk.

        Yields:
            File chunks, each 2MB in size
        """

        while True:
            chunk = file_object.read(self.__chunk_size)

            if chunk:
                yield chunk
                if single_iteration:
                    return # Quit out after first chunk
            else:
                return  # End of file.

    def __str__(self):
        return self.__path

    hash_long = property(__get_hash_long)
    hash_short = property(__get_hash_short)
    length = property(__get_length)
    path = property(lambda self: self.__path)

class Collection:

    def __init__(self, parent, level = 0):
        self.__parent = parent
        self.__level = level
        self.storage = {}
        self.__subcollection = None
        self.__count = 0

        if level == 0:
            self.__key_expression = lambda instance: instance.length
        elif level == 1:
            self.__key_expression = lambda instance: instance.hash_short
        elif level == 2:
            self.__key_expression = lambda instance: instance.hash_long
        else:
            # Bottom level
            self.storage = []
            self.store = self.__store_bottom

    def __store_bottom(self, file_instance):
        self.storage.append(file_instance)
        if len(self.storage) == 2:
            # Report on
            self.__parent.report_dupe(self)

    def store(self, file_instance):
        # If we have an item stored
        key = self.__key_expression(file_instance)
        previous_instance = self.storage.get(key)
        if previous_instance is None:
            self.storage[key] = file_instance
            return

        # If we are still here, then this instance is
        #   a duplicate as far as this level is concerned.
        if self.__subcollection is None:
            # Initialize sub-collection when it's needed.
            self.__subcollection = Collection(self.__parent, self.__level + 1)
            self.__subcollection.store(previous_instance)
        # Store current instance
        self.__subcollection.store(file_instance)

class ReportWrapper:
    def __init__(self):
        self.reset()

    def get_current_report(self):
        return {
            'paths': self.__paths,
            'dupes': self.__dupes,
            'count_files_total': self.__file_count,
            'count_files_redundant': sum([len(l.storage) for l in self.__dupes]) - len(self.__dupes)
        }

    def get_report(self, paths):
        if type(paths) is str:
            paths = [paths]
        self.__paths.extend(paths)
        for path in paths:
            print('Looking for duplicates in directory: %s' % path)
            for (root, dirs, files) in os.walk(path):
                for file_current in files:
                    self.__file_count += 1
                    file_instance = FileInstance(os.path.join(root, file_current))
                    self.__collection.store(file_instance)
        return self.get_current_report()

    def report_dupe(self, collection):
        self.__dupes.append(collection)

    def reset(self):
        self.__collection = Collection(self)
        self.__dupes = []
        self.__paths = []
        self.__file_count = 0

def _translate_digest(digest):
    t = '' # Translated
    for d in digest:
        t += (hex(d >> 4) + hex(d & 0xf)).replace('0x', '')
    return t

def main(args, report_function = None):
    try:
        if report_function is None:
            report_function = print_report

        if not args:
            print('No paths provided.')
            return 1
        report = ReportWrapper().get_report(args)
        report_function(report)
        return 0
    except KeyboardInterrupt:
        print('')
        return 127

def print_report(report):
    print('Found %d instances of files with duplicates amongst %d files.' % (len(report['dupes']), report['count_files_total']))
    c = 0
    for collection in report['dupes']:
        c += 1
        print('Duplicated file #%02d (Hash: %s) instances:' % (c, _translate_digest(collection.storage[0].hash_long)))
        for instance in collection.storage:
            print('\t* %s' % instance.path)

if __name__ == '__main__':
    exit(main(sys.argv[1:])) # pragma: no cover
