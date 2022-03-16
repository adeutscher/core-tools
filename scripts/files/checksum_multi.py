#!/usr/bin/env python3

'''
Multithreaded file hashing.
'''

from hashlib import md5, sha1, sha256, sha512
from os.path import isfile, realpath
from queue import Queue
from sys import argv
from threading import Lock as lock, Thread

CONTROL_DONE = 0
CONTROL_BLOCK_NEW = 1
CONTROL_BLOCK = 2
CONTROL_REPORT = 3


def main(args_raw):

    # TODO: Add more argument-handling

    # Spawn workers
    queue_report = Queue()
    workers_queues = []
    workers = []
    count_algorithms = 0

    try:
        for label, alg in [
            ('md5sum', md5),
            ('sha1sum', sha1),
            ('sha256sum', sha256),
            ('sha512sum', sha512),
        ]:

            count_algorithms += 1

            queue_read = Queue(maxsize=50)
            workers_queues.append(queue_read)
            worker = Thread(
                target=worker_fn, args=(label, alg, queue_read, queue_report)
            )
            worker.start()
            workers.append(worker)

        count_missing_files = 0
        exit_code = 0

        for path in args_raw:

            path_full = realpath(path)

            if not isfile(path_full):
                print(f'File not found: {path_full}')
                exit_code = 1
                continue

            with open(path_full, 'rb') as file_object:
                control_code = CONTROL_BLOCK_NEW
                for chunk in read_in_chunks(file_object=file_object):
                    for queue in workers_queues:
                        queue.put((control_code, chunk))

                    control_code = CONTROL_BLOCK

            for queue in workers_queues:
                queue.put((CONTROL_REPORT, None))

            for report in sorted([queue_report.get() for i in range(count_algorithms)]):
                print(f'{path_full} {report}')

    finally:
        for i, worker in enumerate(workers):
            workers_queues[i].put((CONTROL_DONE, None))
            worker.join()

    return exit_code


def read_in_chunks(**kwargs):
    '''Read a file in fixed-size chunks (to minimize memory usage for large files).

    Args:
        file_object: An opened file-like object supporting read().
        max_length: Max amount of content to fetch from stream.
        chunk_size: Max size (in bytes) of each file chunk (default: 2097152).

    Yields:
        File chunks, each of size at most chunk_size.
    '''

    file_object = kwargs.get('file_object')
    chunk_size = kwargs.get('chunk_size', 2 * (2 ** 20))
    max_length = kwargs.get('max_length', -1)

    i = 0
    while max_length < 0 or i < max_length:

        if max_length > 0:
            chunk_size = min(chunk_size, max_length - i)

        chunk = file_object.read(chunk_size)
        i += len(chunk)

        if chunk:
            yield chunk
        else:
            return  # End of file.


def worker_fn(algorithm_label, algorithm_fn, queue_read, queue_report):

    label_display = algorithm_label.ljust(9)

    while True:
        control, chunk = queue_read.get()

        # Control operations
        if control == CONTROL_DONE:
            break
        if control == CONTROL_REPORT:
            queue_report.put(f'{label_display} {algorithm.hexdigest()}')
            continue
        if control == CONTROL_BLOCK_NEW:
            algorithm = algorithm_fn()
        algorithm.update(chunk)


if __name__ == '__main__':
    try:
        main(argv[1:])
    except KeyboardInterrupt:
        exit(130)
