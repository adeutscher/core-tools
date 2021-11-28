#!/usr/bin/env python

'''
Observe a directory, and then execute argument-provided script
when files within that directory settle down.
'''

# Imports for groundwork and directory-watching
from inotify.adapters import Inotify, InotifyTree
from getopt import gnu_getopt
import logging
from os.path import basename, getsize, isdir, isfile, join, realpath
from threading import Thread
from sys import argv, stderr, stdout
# Imports for file handling.
from dataclasses import dataclass
from subprocess import Popen as cmd, DEVNULL as devnull
from os import access, walk, X_OK
from queue import Empty as empty, PriorityQueue, Queue
from time import sleep, time

def _build_logger(label, err = None, out = None):
    obj = logging.getLogger(label)
    obj.setLevel(logging.DEBUG)
    # Err
    err_handler = logging.StreamHandler(err or stderr)
    err_filter = logging.Filter()
    err_filter.filter = lambda record: record.levelno >= logging.WARNING
    err_handler.addFilter(err_filter)
    obj.addHandler(err_handler)
    # Out
    out_handler = logging.StreamHandler(out or stdout)
    out_filter = logging.Filter()
    out_filter.filter = lambda record: record.levelno < logging.WARNING
    out_handler.addFilter(out_filter)
    obj.addHandler(out_handler)
    return obj
_logger = _build_logger('directory_watcher')

def _colour_path(path):
    return _colour_text(path, COLOUR_GREEN)

def _colour_text(text, colour = None):
    colour = colour or COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)

def _enable_colours(force = None):
    global COLOUR_BOLD
    global COLOUR_BLUE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_OFF
    if force == True or (force is None and stdout.isatty()):
        # Colours for standard output.
        COLOUR_BOLD = '\033[1m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_BOLD = ''
        COLOUR_BLUE = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_OFF = ''
_enable_colours()

def _is_executable(path):
    return access(path, X_OK)

def _parse_args(args_raw):

    error = False

    def check_number(value_raw):
        try:
            value = int(value_raw)
            if value > 0:
                return value, True
        except ValueError:
            pass
        _logger.error(f'Invalid number: {value_raw}')
        return None, False

    def check_path(value_raw, label, check):
        if not check(value_raw):
            _logger.error(f'Invalid {label} path: {_colour_path(value_raw)}')
            return None, False
        return realpath(value_raw), True

    def hexit(exit_code):
        _logger.error('Usage: %s dir -s script [-w workers] [--execute-only]' % basename(__file__))
        exit(exit_code)
    try:
        args, operands = gnu_getopt(args_raw, 'hrs:w:', ['execute-only'])
    except Exception as e:
        _logger.error(f'Error parsing arguments: {e}')
        hexit(1)

    data = {'dirs':[]}
    script = None
    workers_raw = None

    for arg, value_raw in args:
        if arg == '-h':
            hexit(0)
        if arg == '-r':
            data['recursive'] = True
        elif arg == '-s':
            script = value_raw
        elif arg == '-w':
            workers_raw = value_raw
        elif arg == '--execute-only':
            data['execute_only'] = True

    good = True

    if script:
        data['script'], good_arg = check_path(script, 'script', lambda s: isfile(s) and _is_executable(s))
        good = good and good_arg
    else:
        good = False
        _logger.error('No script provided.')

    if workers_raw:
        data['workers'], good_arg = check_number(workers_raw)
        good = good and good_arg

    if operands:
        for dir_path_raw in operands:
            dir_path, good_arg = check_path(dir_path_raw, 'target directory', lambda s: isdir(s))
            data['dirs'].append(dir_path)
            good = good and good_arg
    else:
        _logger.error('No directory provided.')
        good = False

    if not good:
        hexit(1)

    return data

def _main(args_raw):
    kwargs = _parse_args(args_raw)
    run(**kwargs)
    return 0

def run(**kwargs):

    # Parse arguments
    ##

    dirs = kwargs.get('dirs')
    execute_only = kwargs.get('execute_only', False)
    recursive = kwargs.get('recursive', False)
    rest_time = kwargs.get('rest_time', 2)
    script = kwargs.get('script')
    timeout = kwargs.get('timeout')
    workers = kwargs.get('workers', 1)

    if execute_only:
        rest_time = 0

    # Print Info
    ##

    _logger.info(f'Target directory: {_colour_path(dirs[-1])}')
    if recursive:
        _logger.info('Observing directory recursively.')
    _logger.info(f'Script: {_colour_path(script)}')
    _logger.info(f'Script runner threads: {_colour_text(workers)}')
    if rest_time:
        _logger.info(f'Files are at rest after {rest_time}s of inactivity.')

    # Initialize support threads
    ##

    queue_input = Queue()
    queue_output = PriorityQueue()

    # Create monitor thread.
    worker_monitor = MonitorThread(queue_input, queue_output, rest_time)
    worker_monitor.start()

    threads = [worker_monitor]

    # Create worker threads.
    for i in range(workers):
        t = WorkerThread(script, queue_output)
        t.start()
        threads.append(t)

    # Initialize watcher(s)
    ##

    if not execute_only:
        if recursive:
            watcher = InotifyTree(dirs[-1])
        else:
            watcher = Inotify()
            watcher.add_watch(dirs[-1])

    delete_events = [
        'IN_DELETE',
        'IN_MOVED_FROM'
    ]

    write_events = [
        'IN_CLOSE_WRITE',
        'IN_MOVED_TO'
    ]

    # Run watcher(s)
    ##

    if execute_only:
        for current_dir in dirs:
            for dirname, _, files in walk(current_dir):
                for filename in files:
                    queue_input.put((join(dirname, filename), True))
                worker_monitor.set_done()
                worker_monitor.join()
                for t in threads:
                    t.set_done()
    else:
        for event in watcher.event_gen(yield_nones = False):
            (_, type_names, dirname, filename) = event

            is_write = len([1 for event_type in type_names if event_type in write_events]) > 0
            is_delete = len([1 for event_type in type_names if event_type in delete_events]) > 0

            if not (is_write or is_delete):
                # Not a notable event
                continue

            queue_input.put((join(dirname, filename), is_write))

    for t in threads:
        t.join()

class MonitorThread(Thread):
    def __init__(self, queue_in: Queue, queue_out: PriorityQueue, rest_time: float):
        Thread.__init__(self)
        self.__done = False
        self.__queue_in = queue_in
        self.__queue_out = queue_out
        self.__rest_time = rest_time

    def set_done(self):
        self.__done = True

    def run(self):

        data = {}

        while True:
            # Load up new items
            while not self.__queue_in.empty():
                path, addition = self.__queue_in.get()

                if not addition:
                    # if not addition, then deletion
                    if path in data and not isfile(path):
                        del data[path]
                    continue

                if path in data:
                    # Already filed
                    data[path].time = time()
                else:
                    # Newly-observed
                    if not isfile(path):
                        # Not a file, vanished in between
                        continue

                    try:
                        data[path] = MonitorInstance(size=getsize(path), time=time())
                    except OSError as e:
                        # The file vanished since our last safety check
                        #   or is otherwise unobservable since it was queued.
                        _logger.error('Error starting to monitor instance: %s' % str(e))
                        pass # Decline to observe

            # Review monitored files
            for path in list(data.keys()):
                if not isfile(path):
                    del data[path]
                    continue
                instance = data.get(path) # Shorthand
                try:
                    size = getsize(path)
                    if size != instance.size:
                        # Update time.
                        instance.size = size
                        instance.time = time()
                        continue

                    if time() - instance.time >= self.__rest_time:
                        if instance.size:
                            # Only process the file if it has content.
                            _logger.info(f'File at rest: {_colour_path(path)}')
                            self.__queue_out.put((instance.size, path))
                        del data[path]

                except OSError as e:
                    _logger.error(f'Error monitoring instance: {e}')
                    del data[path]
                    continue

            # We do not want to do this in the loop-condition.
            if self.__done and not data:
                break

            sleep(0.1)

@dataclass
class MonitorInstance:
    size: int
    time: float

    def __eq__(self, other):
        return self.path == other.path

    def __ge__(self, other):
        return self.size >= other.size

    def __gt__(self, other):
        return self.size > other.size

    def __lt__(self, other):
        return self.size < other.size

class WorkerThread(Thread):
    def __init__(self, script: str, queue: PriorityQueue):
        Thread.__init__(self)
        self.__done = False
        self.__queue = queue
        self.__script = script

    def set_done(self):
        self.__done = True

    def run(self):
        while True:
            try:
                size, path = self.__queue.get(timeout=0.2)
            except empty:
                if self.__done:
                    break
                continue

            if not isfile(path):
                # One last isfile for safety.
                # The file could have been removed after it was added to the queue
                # For now, intentionally ignoring silently.
                continue

            if not isfile(self.__script):
                _logger.error(f'Script is no longer available: {_colour_path(self.__script)}')
                continue

            if not _is_executable(self.__script):
                _logger.error(f'Script is no longer executable: {_colour_path(self.__script)}')
                continue

            _logger.info(f'Handling file: {_colour_path(path)}')
            p = cmd([self.__script, path], stdout=devnull, stderr=devnull)
            p.communicate()
            if p.returncode:
                _logger.error(f'Error with file: {_colour_path(path)}')
            else:
                _logger.info(f'Finished with file: {_colour_path(path)}')

if __name__ == '__main__':
    exit(_main(argv[1:])) # pragma no cover
