#!/usr/bin/env python

'''
Collect multiples hashes for files in a directory and write the output to a CSV file.

This script is also an experiment in using queues to delegate work between multiple threads,
    and phrasing it in a way that can be easily transferred to other scripts..
'''

# Queue mechanics
##
from queue import Empty as empty, PriorityQueue as queue
import queue as queueModule
# _threading.start_new_thread needs fewer lines,
#   but code executed within a thread isn't
#   picked up by coverage.
from threading import Lock as lock, Thread
from time import sleep, time
from typing import Any
# Script mechanics
##
import argparse, csv
from hashlib import md5,sha1,sha256,sha512
import os
from sys import argv

class ThreadedRunnerBase:

    def __init__(self):
        self.__reset()

    def __reset(self):
        self.__is_monitored = False
        self.__is_running = False

        self._last_state_change_time = time()

        self.__lock = lock()
        self.__workers_done = 0

    def get_job(self):
        # get_job should be implemented by a class that inherits from ThreadedRunnerBase.
        raise Exception('get_job not implemented') # pragma: no cover

    is_monitored = property(lambda self: self.__is_monitored)

    def report_worker_done(self, worker_id):
        self.__lock.acquire()
        self.__workers_done += 1
        self.__lock.release()

    def report_state_change(self, worker_id, state_old, state_new):
        self.__lock.acquire()
        self._last_state_change_time = time()
        self.__lock.release()

    def run(self, **kwargs):

        if self.__is_running:
            raise Exception('Already running.')
        self.__is_running = True

        # count_workers, callback, prep_callback = None
        worker_count = kwargs.get('worker_count')
        worker_callback = kwargs.get('worker_callback')
        callback_prep = kwargs.get('callback_prep')
        callback_monitor = kwargs.get('callback_monitor')
        self.__is_monitored = callback_monitor is not None

        # Init
        self._threads = []
        if callback_prep is not None:
            t = ThreadedRunnerPrepWorker(callback_prep, (self,))
            t.start()
            self._threads.append(t)

        i = 0

        while i < worker_count:
            i += 1
            t = ThreadedRunnerWorker(i, self, worker_callback)
            t.start()
            self._threads.append(t)

        # Wait for tasks to complete
        while self.__workers_done < worker_count:
            if self.is_monitored:
                for t in self._threads:
                    callback_monitor(t)
            sleep(0.1)

        # Re-join threads for the sake of coverage in testing
        for t in self._threads:
            t.join()

        self.__reset()

class ThreadedRunnerPrepWorker(Thread):
    def __init__(self, callback, callback_args=None):
        Thread.__init__(self)
        self.callback = callback
        self.callback_args = callback_args

    def run(self):
        self.callback(self.callback_args)

class ThreadedRunnerQueue(ThreadedRunnerBase):
    def __init__(self):
        ThreadedRunnerBase.__init__(self)
        self.done = False
        self.queue = queue()

    def get_job(self):
        try:
            priority, task = self.queue.get(False)
        except empty:
            task = None
        return {'params': task, 'done': self.done }

    def set_done(self):
        self.done = True

class ThreadedRunnerWorker(Thread):

    STATE_IDLE = 0
    STATE_WORKING = 1
    STATE_DONE = 2
    STATE_ERROR = 3

    def __init__(self, worker_id, instance, callback):
        Thread.__init__(self)

        self.__state = self.STATE_IDLE
        self.__lock = lock()

        self.__worker_id = worker_id
        self.__instance = instance
        self.__callback = callback

    def run(self):
        while True:

            if self.state != self.STATE_IDLE and self.__instance.is_monitored == True:
                # Waiting for monitor to reset job status
                sleep(0.1) # Sleep briefly and try again
                continue

                # If we were not in a monitored instance, then the state of
                #   the previous loop iteration would be irrelevant.

            job = self.__instance.get_job()
            job_params = job.get('params')

            if job_params is None:
                if job.get('done'):
                    break
                sleep(0.1) # Sleep briefly
                continue # Restart loop and try again
            try:
                self.set_state(self.STATE_WORKING)
                self.task = job_params
                self.__callback(job_params)
                self.set_state(self.STATE_DONE)
            except Exception as e:
                self.set_state(self.STATE_ERROR)
                print('Worker %d error: %s' % (self.__worker_id, str(e)))
        self.__instance.report_worker_done(self.__worker_id)

    state = property(lambda self: self.__state)

    def set_state(self, state):
        self.__lock.acquire()
        state_old = self.__state
        self.__state = state
        self.__instance.report_state_change(self.__worker_id, state_old, state)
        self.__lock.release()

def _read_in_chunks(**kwargs):
    """Read a file in fixed-size chunks (to minimize memory usage for large files).

    Args:
        file_object: An opened file-like object supporting read().
        max_length: Max amount of content to fetch from stream.
        chunk_size: Max size (in bytes) of each file chunk.

    Yields:
        File chunks, each of size at most chunk_size.
    """

    file_object = kwargs.get('file_object')
    chunk_size = kwargs.get('chunk_size', 2 * (2 ** 20))

    i = 0
    while True:

        chunk = file_object.read(chunk_size)
        i += len(chunk)

        if chunk:
            yield chunk
        else:
            return  # End of file.

def _translate_digest(digest):
    t = '' # Translated
    for d in digest:
        t += (hex(d >> 4) + hex(d & 0xf)).replace('0x', '')
    return t

class HashWorker:

    def __init__(self):
        self.__write_lock = lock()
        self.__data = {}

    def __set_data(self, path, data):
        self.__write_lock.acquire()
        self.__data[path] = data
        self.__write_lock.release()

    def action_load_queue(self, path, instance):
        if os.path.isfile(path):
            length = os.stat(path).st_size
        else:
            length = -1
        instance.queue.put((-length, path))

    def action_single_thread(self, path, arg):
        try:
            self.do_work(path)
        except Exception as e:
            print('Error with file: %s' % path)

    def completed(self):
        pass

    def do_work(self, path):

        if not os.path.isfile(path):
            return

        print('Getting hashes for file: %s' % path)
        hashes = [md5(), sha1(), sha256(), sha512()]
        with open(path, 'rb') as f:
            for chunk in _read_in_chunks(file_object = f):
                for h in hashes:
                    h.update(chunk)
        self.__set_data(path, (hashes[0].digest(), hashes[1].digest(), hashes[2].digest(), hashes[3].digest()))

    def load(self, action, action_arg=None):
        for directory in self.__directories:
            for (dirname, subdirs, files) in os.walk(directory):
                for file in files:
                    path = os.path.join(dirname, file)
                    action(path, action_arg)
        self.completed()

    def run_single_thread(self):
        self.load(self.action_single_thread)

    def set_directories(self, directories):
        # TODO: Add validation.
        self.__directories = directories

    def write_data(self, output):
        writer = csv.writer(output, delimiter=',')
        for key in sorted(self.__data.keys()):
            md5, sha1, sha256, sha512 = self.__data[key]
            writer.writerow([key, _translate_digest(md5), _translate_digest(sha1), _translate_digest(sha256), _translate_digest(sha512)])

def main(args, worker = None):

    parser = argparse.ArgumentParser(description='Hash all files in a directory.')
    parser.add_argument('-w', dest='workers', type=int, default=1, help='Number of worker threads (default: 1)')
    parser.add_argument('-o', dest='output', help='Output file to write to.')
    parser.add_argument('directory', nargs='*', help='Directories to hash files in.')
    args = parser.parse_args(args)

    errors = []
    if args.workers < 1:
        errors.append('Must have at least one worker thread.')

    if len(args.directory) == 0:
        errors.append('No directories specified')
    else:
        # Deduplicate list.
        directories = list(dict.fromkeys(args.directory))
        # ToDo: Avoid nested directories (e.g. skip /home/foo if /home is also specified)
        for directory in directories:
            if not os.path.isdir(directory):
                errors.append('No such directory: %s' % directory)

    if not args.output:
        errors.append('No output file defined.')

    if errors:
        for e in errors:
            print('Error: %s' % e)
        return 1

    if not worker:
        worker = HashWorker
    worker = worker()
    worker.set_directories(directories)

    with open(args.output, 'w') as output:
        if args.workers == 1:
            worker.run_single_thread()
        else:
            runner = ThreadedRunnerQueue()
            worker.instance = runner
            worker.completed = runner.set_done
            load_cb = lambda _: worker.load(worker.action_load_queue, runner)
            runner_args = {
                'worker_count': args.workers,
                'worker_callback': worker.do_work,
                'callback_prep': load_cb
            }
            runner.run(**runner_args)
        worker.write_data(output)
    return 0

if __name__ == '__main__':
    exit(main(argv[1:])) # pragma: no cover
