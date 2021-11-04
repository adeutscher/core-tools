#!/usr/bin/env python

'''
These classes contain plumbing for:

* Pulling workload from job queues, such as:
    queue.Queue
    queue.PriorityQueue
    boto3.SQS.Client
'''

# Queue mechanics
##
from queue import Empty as empty
from queue import PriorityQueue # For ThreadedRunnerPriorityQueue
from queue import Queue         # For ThreadedRunnerQueue
# _threading.start_new_thread needs fewer lines,
#   but code executed within a thread isn't
#   picked up by coverage.
from threading import Lock as lock, Thread
from time import sleep, time

class ThreadedRunnerBase:

    def __init__(self):
        self.__reset()

    def __reset(self):
        # 'is done loading jobs'
        # Default to True unless we are using a prep callback.
        self._is_done = True
        self.__is_monitored = False

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

        # count_workers, callback, prep_callback = None
        worker_count = kwargs.get('worker_count', 1)
        worker_callback = kwargs.get('worker_callback')
        callback_prep = kwargs.get('callback_prep')
        callback_monitor = kwargs.get('callback_monitor')
        self.__is_monitored = callback_monitor is not None

        # Init
        self._threads = []
        if callback_prep is not None:
            self._is_done = False
            t = ThreadedRunnerPrepWorker(self, callback_prep, kwargs.get('callback_prep_args'))
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

'''
Wrapper class for running a thread that is responsible
  for loading tasks to be handled by worker threads.
'''
class ThreadedRunnerPrepWorker(Thread):
    def __init__(self, runner, callback, callback_args=None):
        Thread.__init__(self)
        self.runner = runner
        self.callback = callback
        self.callback_args = callback_args

    def run(self):
        try:
            self.callback(self.runner, self.callback_args)
        except Exception as e:
            print('Prep callback error: %s' % str(e))
        self.runner._is_done = True

'''
ThreadedRunnerBase implementation for working with a queue.PriorityQueue.
'''
class ThreadedRunnerPriorityQueue(ThreadedRunnerBase):
    def __init__(self, queue = None):
        ThreadedRunnerBase.__init__(self)
        self.__queue = queue or PriorityQueue()

    def get_job(self):
        try:
            priority, task = self.__queue.get(False)
        except empty:
            task = None
        return {'params': task, 'done': self._is_done }

    def set_job(self, task, priority=1000):
        self.__queue.put((priority, task))

'''
ThreadedRunnerBase implementation for working with a queue.Queue.
'''
class ThreadedRunnerQueue(ThreadedRunnerBase):
    def __init__(self, queue = None):
        ThreadedRunnerBase.__init__(self)
        self.__queue = queue or Queue()

    def get_job(self):
        try:
            task = self.__queue.get(False)
        except empty:
            task = None
        return {'params': task, 'done': self._is_done }

    def set_job(self, task):
        self.__queue.put(task)

class ThreadedRunnerSQS(ThreadedRunnerBase):
    def __init__(self, **kwargs):
        ThreadedRunnerBase.__init__(self)
        self._is_done = False

        self.__quit_threshold = kwargs.get('quit_threshold', 0)

        self.__sqs_object = kwargs.get('sqs_object')
        self.__sqs_queue = kwargs.get('sqs_queue')
        self.__sqs_timeout = kwargs.get('sqs_timeout', 300)

    def get_job(self):

        task = None
        if not self._is_done:
            receive_params = {
                'MaxNumberOfMessages': 1,
                'QueueUrl': self.__sqs_queue,
                'VisibilityTimeout': self.__sqs_timeout
            }
            response = self.__sqs_object.receive_message(**receive_params)

            if response.get('Messages'):
                task = response['Messages'][0]
            elif self.__quit_threshold > 0:
                # No task, and all workers are awaiting jobs
                # Doing this in order to avoid a situation where the workers half-quit.
                if time() > self._last_state_change_time + self.__quit_threshold and len([1 for t in self._threads if t.state == ThreadedRunnerWorker.STATE_IDLE]) == len(self._threads):
                    self._is_done = True
                # No task, over quit threshold

        return {'params': task, 'done': self._is_done }

'''
Monitor layer to handle completed management of SQS jobs.
'''
class SQSMonitor:
    def __init__(self, **kwargs):
        self.__sqs_object = kwargs.get('sqs_object')
        self.__sqs_queue = kwargs.get('sqs_queue')
        self.__sqs_queue_fallback = kwargs.get('sqs_queue_fallback')
        self.__sqs_timeout = kwargs.get('sqs_timeout', 300)
        self.__quit_threshold = kwargs.get('quit_threshold', 0)
        self.__callback = kwargs.get('callback')

        self.__worker_count = kwargs.get('worker_count', 1)
        self.__worker_callback = kwargs.get('worker_callback')

    def __monitor(self, thread):
        if thread.state == ThreadedRunnerWorker.STATE_IDLE:
            # Worker is awaiting a job.
            return
        if thread.state == ThreadedRunnerWorker.STATE_DONE:
            # Worker finished its most recent job without an exception.

            setattr(thread, 'last_refresh', None) # Reset refresh time.
            self.__sqs_object.delete_message(QueueUrl=self.__sqs_queue, ReceiptHandle=thread.task['ReceiptHandle'])
            thread.set_state(ThreadedRunnerWorker.STATE_IDLE)
            return
        if thread.state == ThreadedRunnerWorker.STATE_ERROR:
            # Worker threw an error in its most recent job

            if self.__sqs_queue_fallback:
                self.__sqs_object.send_message(QueueUrl=self.__sqs_queue_fallback, MessageBody=thread.task['Body'])

            setattr(thread, 'last_refresh', None) # Reset refresh time.
            self.__sqs_object.delete_message(QueueUrl=self.__sqs_queue, ReceiptHandle=thread.task['ReceiptHandle'])
            thread.set_state(ThreadedRunnerWorker.STATE_IDLE)
            return
        if thread.state == ThreadedRunnerWorker.STATE_WORKING:
            # Worker is currently handling a job.

            last_refresh = getattr(thread, 'last_refresh', None)
            if last_refresh is None:
                # No attribute.
                # Consider the task to be freshly retrieved,
                #   so set last_refresh to right now.
                setattr(thread, 'last_refresh', time())
                return # Immediately abort.

            if time() - last_refresh > self.__sqs_timeout - self.__sqs_timeout / 3:
                print('Refreshing Task:', thread.task['MessageId'])
                self.__sqs_object.change_message_visibility(QueueUrl=self.__sqs_queue, ReceiptHandle=thread.task['ReceiptHandle'], VisibilityTimeout=self.__sqs_timeout)
                setattr(thread, 'last_refresh', time())

            return

    def run(self):
        runner_init_params = {
            'sqs_object': self.__sqs_object,
            'sqs_queue': self.__sqs_queue,
            'sqs_timeout': self.__sqs_timeout,
            'quit_threshold': self.__quit_threshold
        }
        runner = ThreadedRunnerSQS(**runner_init_params)

        runner_run_params = {
            'worker_count': self.__worker_count,
            'worker_callback': self.__worker_callback,
            'callback_monitor': self.__monitor
        }

        runner.run(**runner_run_params)

'''
Worker thread wrapper.

Handles pulling jobs from the runner and passing them to the callback.
'''
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
