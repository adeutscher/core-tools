#!/usr/bin/env

import common, unittest # General test requirements
# Specific test requirements
import queue, threading
from time import sleep, time

class BaseQueueTest(common.TestCase):
    def loadModule(self):
        self.mod = common.load('queued_workloads', common.TOOLS_DIR + '/scripts/clipboard/python/queued_workloads.py')

    def setUp(self):
        self.loadModule()

'''
This class provides the bare minimum to simulate a boto3.SQS.Client object for the sake of these tests.

It should be able to:

* Store messages.
    * For possible DLQ-processing, I'll implement send_message
* Simulate receive_message method.
    * Draw messages from a list.
    * Return a dict that contains the message in a list in the 'Messages' key.
      * The message itself must be a dict containing the following sections: Body, MessageId, ReceiptHandle
    * Relayed messages must be assigned a ReceiptHandle that will be referenced later.
    * Store message requests, or at least for the method invocations that resulted in messages being checked out.
* Simulate delete_message method.
    * Receipt handle must match an assigned ReceiptHandle for a message that hasn't been deleted.
    * Store delete requests
* Simulate change_message_visibility method:
    * Receipt handle must match an assigned ReceiptHandle for a message that hasn't been deleted.
    * Store requests

For more information on the real class, see: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sqs.html
'''
class MockSQS:

    class Queue:

        def get_checkout(self, receipt_handle, remove):
            i = 0
            while i < len(self.checkouts):

                checkout = self.checkouts[i] # Declare early as shorthand
                if checkout.get('ReceiptHandle') == receipt_handle:
                    # Found our item
                    if remove:
                        self.checkouts.pop(i) # Remove from list
                    break
                # Prep for next loop
                checkout = None
                i += 1
            return checkout

        def __init__(self):
            # Track Data
            self.messages = []
            self.checkouts = []
            self.deleted_messages = []

            # Track Messages
            self.send_requests = []
            self.receive_requests = []
            self.delete_requests = []
            self.visibility_requests = []

            self.message_id = 1

    def __get_queue(self, **kwargs):
        queue_url = kwargs.get('QueueUrl')
        if not queue_url:
            raise botocore.exceptions.ParamValidationError('No queue provided.')
        queue = self.queues.get(queue_url)
        if not queue:
            raise botocore.exceptions.QueueDoesNotExist('No such queue: %s' % queue_url)
        return queue

    def __init__(self, queue_url = None):

        self.lock = threading.Lock()
        self.queues = {}
        if queue_url:
            self.queues[queue_url] = MockSQS.Queue()

    def change_message_visibility(self, **kwargs):
        self.lock.acquire()
        try:
            queue = self.__get_queue(**kwargs)

            checkout = queue.get_checkout(kwargs.get('ReceiptHandle'), False)
            found = checkout is not None
            queue.visibility_requests.append((found, kwargs.copy()))

        finally:
            self.lock.release()

    def delete_message(self, **kwargs):

        self.lock.acquire()
        try:
            queue = self.__get_queue(**kwargs)

            checkout = queue.get_checkout(kwargs.get('ReceiptHandle'), True)
            found = checkout is not None
            queue.delete_requests.append((found, kwargs.copy()))

            if not found:
                # No such message found
                # TODO: Add some sort of exception?
                # Not really necessary so long as every other test passes.
                return
            queue.deleted_messages.append(checkout.copy())

            # No need to send any response for these tests
        finally:
            self.lock.release()

    def receive_message(self, **kwargs):

        self.lock.acquire()
        try:
            queue = self.__get_queue(**kwargs)
            response = {
                'Messages': []
            }
            if queue.messages:
                message = queue.messages.pop(0)
                # Add to response
                response['Messages'].append(message.copy())
                # Track checkout
                queue.checkouts.append(message.copy())
                # Track Request only if we got a message
                queue.receive_requests.append(kwargs.copy())

            return response
        finally:
            self.lock.release()

    def send_message(self, **kwargs):

        self.lock.acquire()
        try:
            queue = self.__get_queue(**kwargs)
            queue.send_requests.append(kwargs.copy())

            message = {
                'Body': kwargs.get('MessageBody'),
                # Set message ID
                'MessageId': 'm%03d' % queue.message_id,
                # May as well set the receipt handle right now
                'ReceiptHandle': 'r%03d' % queue.message_id
            }
            queue.messages.append(message)
            queue.message_id += 1

            # No need to send any response for these tests
        finally:
            self.lock.release()

'''
Recreate module structure without actually requiring an import of the botocore module.
'''
class botocore:
    class exceptions:
        class ParamValidationError(Exception):
            def __init__(self, msg):
                Exception.__init__(self, msg)

        class QueueDoesNotExist(Exception):
            def __init__(self, msg):
                Exception.__init__(self, msg)

'''
specifically test our MockSQS implementation.
'''
class MockSQSTests(common.TestCase):
    '''
    Test a failed delete.
    '''
    def test_failed_delete(self):

        queue_url = "queue"
        sqs = MockSQS(queue_url)
        url, queue = self.assertSingle(sqs.queues)
        self.assertEqual(queue_url, url)

        sqs.send_message(QueueUrl = queue_url, MessageBody = "a")
        response = sqs.receive_message(QueueUrl = queue_url)
        msg = self.assertSingle(response['Messages'])
        sqs.delete_message(QueueUrl = queue_url, ReceiptHandle='not-%s' % msg['ReceiptHandle'])
        self.assertEmpty(queue.deleted_messages)
        self.assertSingle(queue.checkouts)
        self.assertEmpty(queue.messages)

    '''
    When no queue is provided, then a parameter validation error is expected.
    '''
    def test_no_queue_error(self):

        sqs = MockSQS()
        self.assertEmpty(sqs.queues)

        self.assertRaises(botocore.exceptions.ParamValidationError, lambda: sqs.send_message())

    '''
    When we don't have a  provided, then a parameter validation error is expected.
    '''
    def test_no_such_queue_error(self):

        sqs = MockSQS()
        self.assertEmpty(sqs.queues)

        self.assertRaises(botocore.exceptions.QueueDoesNotExist, lambda: sqs.send_message(QueueUrl="abc"))

'''
Tests for working with a priority queue
'''
class PriorityQueueTests(BaseQueueTest):

    '''
    Basic run with a priority queue on one worker thread.
    '''
    def test_priority_queue(self):

        # Track invocations
        invocations = []
        def callback(task):
            invocations.append(task)

        runner = self.mod.ThreadedRunnerPriorityQueue()

        # Set first value. We expect this to not run first.
        runner.set_job('b', 20)

        # Deliberately NOT setting a high number here.
        # Should default to something high that puts it at the end of the list.
        runner.set_job('e')

        # Set other values
        runner.set_job('a', 10)
        runner.set_job('c', 30)
        runner.set_job('d', 40)

        runner_args = {
            'worker_callback': callback,
            'worker_count': 1
        }

        runner.run(**runner_args)
        self.assertEqual(5, len(invocations))
        self.assertEqual('a', invocations[0])
        self.assertEqual('b', invocations[1])
        self.assertEqual('c', invocations[2])
        self.assertEqual('d', invocations[3])
        self.assertEqual('e', invocations[4])

    '''
    Basic run with a priority queue on one worker thread.

    This instance of ThreadedRunnerPriorityQueue is loaded with
    a pre-existing Queue instance.
    '''
    def test_priority_queue_preloaded(self):

        # Track invocations
        invocations = []
        def callback(task):
            invocations.append(task)

        task_queue = queue.PriorityQueue()

        # Load queues directly, with the similar content to test_priority_queue.
        task_queue.put((20, 'b'))
        task_queue.put((1000, 'e'))
        task_queue.put((10, 'a'))
        task_queue.put((30, 'c'))
        task_queue.put((40, 'd'))

        runner = self.mod.ThreadedRunnerPriorityQueue(task_queue)

        runner_args = {
            'worker_callback': callback,
            'worker_count': 1
        }

        runner.run(**runner_args)
        self.assertEqual(5, len(invocations))
        self.assertEqual('a', invocations[0])
        self.assertEqual('b', invocations[1])
        self.assertEqual('c', invocations[2])
        self.assertEqual('d', invocations[3])
        self.assertEqual('e', invocations[4])

    '''
    Basic run with a priority queue on one worker thread.

    This instance gets its input from a callback 'prep' script.
    '''
    def test_priority_queue_prep(self):

        # Track invocations
        invocations = []
        def callback(task):
            invocations.append(task)


        callback_arg = "This is a test parameter passed into callback_prep for priority queue"

        # Define prep callback
        def callback_prep(c_runner, c_args):

            # Confirm that our argument was passed through.
            self.assertEqual(callback_arg, c_args)
            self.assertIs(runner, c_runner)

            # Set first value. We expect this to not run first.
            c_runner.set_job('b', 20)

            # Deliberately NOT setting a high number here.
            # Should default to something high that puts it at the end of the list.
            c_runner.set_job('e')

            # Set other values
            c_runner.set_job('a', 10)
            c_runner.set_job('c', 30)
            c_runner.set_job('d', 40)

        runner = self.mod.ThreadedRunnerPriorityQueue()
        runner_args = {
            'worker_callback': callback,
            'worker_count': 1,
            'callback_prep': callback_prep,
            'callback_prep_args': callback_arg
        }

        runner.run(**runner_args)
        self.assertEqual(5, len(invocations))
        self.assertEqual('a', invocations[0])
        self.assertEqual('b', invocations[1])
        self.assertEqual('c', invocations[2])
        self.assertEqual('d', invocations[3])
        self.assertEqual('e', invocations[4])

class QueueTests(BaseQueueTest):

    '''
    Basic run with a basic queue on one worker thread.
    '''
    def test_queue(self):

        # Track invocations
        invocations = []
        def callback(task):
            invocations.append(task)

        runner = self.mod.ThreadedRunnerQueue()

        # Set first value. We expect this to run first,
        #   as a queue.Queue is first-in-first-out (FIFO)
        runner.set_job('a')
        runner.set_job('b')
        runner.set_job('c')
        runner.set_job('d')
        runner.set_job('e')

        runner_args = {
            'worker_callback': callback,
            'worker_count': 1
        }

        runner.run(**runner_args)
        self.assertEqual(5, len(invocations))
        self.assertEqual('a', invocations[0])
        self.assertEqual('b', invocations[1])
        self.assertEqual('c', invocations[2])
        self.assertEqual('d', invocations[3])
        self.assertEqual('e', invocations[4])

    '''
    Basic run with a basic queue on one worker thread.

    The callback in this test shall suffer an exception.
    '''
    def test_queue_exception(self):

        # Track invocations
        obj = {'executed': False}
        def callback(task):
            obj['executed'] = True
            raise Exception('callback exception')

        runner = self.mod.ThreadedRunnerQueue()
        runner.set_job('a')
        runner_args = {
            'worker_callback': callback,
            'worker_count': 1
        }

        runner.run(**runner_args)
        self.assertTrue(obj['executed'])

    '''
    Basic run with a queue on one worker thread.

    This instance of ThreadedRunnerPriorityQueue is loaded with
    a pre-existing Queue instance.
    '''
    def test_queue_preloaded(self):

        # Track invocations
        invocations = []
        def callback(task):
            invocations.append(task)

        task_queue = queue.Queue()

        # Load queues directly, with the similar content to test_priority_queue.
        task_queue.put('a')
        task_queue.put('b')
        task_queue.put('c')
        task_queue.put('d')
        task_queue.put('e')

        runner = self.mod.ThreadedRunnerQueue(task_queue)

        runner_args = {
            'worker_callback': callback,
            'worker_count': 1
        }

        runner.run(**runner_args)
        self.assertEqual(5, len(invocations))
        self.assertEqual('a', invocations[0])
        self.assertEqual('b', invocations[1])
        self.assertEqual('c', invocations[2])
        self.assertEqual('d', invocations[3])
        self.assertEqual('e', invocations[4])

    '''
    Basic run with a basic queue on one worker thread.

    This instance gets its input from a callback 'prep' script.
    '''
    def test_queue_prep(self):

        # Track invocations
        invocations = []
        def callback(task):
            invocations.append(task)

        callback_arg = "This is a test parameter passed into callback_prep for queue"

        # Define prep callback
        def callback_prep(c_runner, c_args):

            # Confirm that our argument was passed through.
            self.assertEqual(callback_arg, c_args)
            self.assertIs(runner, c_runner)

            # Set first value. We expect this to not run first.
            c_runner.set_job('a')
            c_runner.set_job('b')
            c_runner.set_job('c')
            c_runner.set_job('d')
            c_runner.set_job('e')

        runner = self.mod.ThreadedRunnerQueue()
        runner_args = {
            'worker_callback': callback,
            'worker_count': 1,
            'callback_prep': callback_prep,
            'callback_prep_args': callback_arg
        }

        runner.run(**runner_args)
        self.assertEqual(5, len(invocations))
        self.assertEqual('a', invocations[0])
        self.assertEqual('b', invocations[1])
        self.assertEqual('c', invocations[2])
        self.assertEqual('d', invocations[3])
        self.assertEqual('e', invocations[4])

    '''
    Basic run with a basic queue on one worker thread.

    This instance gets its input from a callback 'prep' script,
      but that callback script will suffer an Exception
    '''
    def test_queue_prep_exception(self):

        # Track invocations
        invocations = []
        def callback(task):
            # This callback should never be executed.
            invocations.append(task) # pragma: no cover

        # Define prep callback
        obj = {'executed': False}
        def callback_prep(c_runner, c_args):
            obj['executed'] = True
            raise Exception('prep exception')

        runner = self.mod.ThreadedRunnerQueue()
        runner_args = {
            'worker_callback': callback,
            'worker_count': 1,
            'callback_prep': callback_prep
        }

        runner.run(**runner_args)
        self.assertTrue(obj['executed'])
        self.assertEmpty(invocations)

'''
Tests and demonstrations of how to use my workload-running system with
  a job source that behaves like the boto3 SQS client.
'''
class SQSWorkloadTests(BaseQueueTest):
    '''
    Basic test of SQS-based pulling using a single thread.

    The worker should complete the jobs in the queue,
      then wait for more jobs for between 2-2.5 seconds.
    '''
    def test_sqs_basic(self):

        # Track invocations
        invocations = []
        def callback(task):
            invocations.append(task['Body'])

        queue_url = 'WorkerQueue'
        sqs = MockSQS(queue_url)
        sqs_timeout = 60
        quit_threshold = 2

        sqs.send_message(QueueUrl = queue_url, MessageBody='a')
        sqs.send_message(QueueUrl = queue_url, MessageBody='b')

        # Confirm the messages that we just sent.
        url, queue = self.assertSingle(sqs.queues)
        self.assertEqual(queue_url, url)
        self.assertEqual(2, len(queue.send_requests))
        self.assertEqual(2, len(queue.messages))
        self.assertEqual(3, queue.message_id)

        # Invoke the monitor.
        # This is what a real instance would do
        monitor_params = {
            # If the monitor runs idle for this many seconds, then exit the script.
            # Set to 0 to run indefinitely.
            'quit_threshold': quit_threshold,
            # SQS client object
            'sqs_object': sqs, # If this weren't a unit test, use boto3.client('sqs') instead.
            # Queue URL
            # For this example, read from arguments
            'sqs_queue': queue_url,
            # Message Timeout (default 300)
            # Once 2/3 of this duration has passed, the monitor
            #   will refresh the visibility timeout of the SQS
            #   message so that it does not become available for
            #   another worker while this instance is still active.
            'sqs_timeout': sqs_timeout,
            # Set callback, which shall receive one 'task' argument,
            #   as read directly out of the queue.
            'worker_callback': callback,
            # Number of worker threads to run
            # The script will spawn up this many worker threads,
            #   which shall continue to attempt to get/execute jobs
            'worker_count': 1
        }

        monitor = self.mod.SQSMonitor(**monitor_params)
        time_start = time()
        monitor.run()
        time_end = time()
        # Finished running the monitor.

        time_diff = time_end - time_start

        # Execution took between 2-2.5 seconds.
        self.assertTrue(time_diff > quit_threshold)
        self.assertTrue(time_diff < quit_threshold + .5)

        url, queue = self.assertSingle(sqs.queues)
        self.assertEqual(queue_url, url)
        self.assertEmpty(queue.checkouts)
        self.assertEmpty(queue.messages)
        self.assertEqual(2, len(queue.delete_requests))
        self.assertEqual(2, len(queue.receive_requests))

        # Check our callback invocation log
        self.assertEqual(2, len(invocations))
        self.assertEqual('a', invocations[0])
        self.assertEqual('b', invocations[1])

    '''
    Test of SQS-based pulling using a single thread.

    A fallback queue has been set, so failed messages will by submitted there.
    '''
    def test_sqs_error_fallback(self):

        # Track invocations
        tracking = {}
        def callback(task):
            tracking['executed'] = True
            raise Exception('Callback Exception')

        queue_url = 'WorkerQueue'
        queue_url_fallback = 'WorkerQueue-Fallback'
        sqs = MockSQS(queue_url)
        sqs.queues[queue_url_fallback] = MockSQS.Queue()
        sqs_timeout = 60
        quit_threshold = 0.5

        sqs.send_message(QueueUrl = queue_url, MessageBody='a')

        # Confirm the messages that we just sent.
        queue = sqs.queues[queue_url]
        self.assertSingle(queue.send_requests)
        self.assertSingle(queue.messages)
        self.assertEqual(2, queue.message_id)

        queue_fallback = sqs.queues[queue_url_fallback]
        self.assertEmpty(queue_fallback.send_requests)
        self.assertEmpty(queue_fallback.messages)

        # Invoke the monitor.
        # This is what a real instance would do
        monitor_params = {
            # If the monitor runs idle for this many seconds, then exit the script.
            # Set to 0 to run indefinitely.
            'quit_threshold': quit_threshold,
            # SQS client object
            'sqs_object': sqs, # If this weren't a unit test, use boto3.client('sqs') instead.
            # Queue URL
            # For this example, read from arguments
            'sqs_queue': queue_url,
            # Fallback Queue URL
            # If set, then submit messages here when a job throws an exception.
            'sqs_queue_fallback': queue_url_fallback,
            # Message Timeout (default 300)
            # Once 2/3 of this duration has passed, the monitor
            #   will refresh the visibility timeout of the SQS
            #   message so that it does not become available for
            #   another worker while this instance is still active.
            'sqs_timeout': sqs_timeout,
            # Set callback, which shall receive one 'task' argument,
            #   as read directly out of the queue.
            'worker_callback': callback,
            # Number of worker threads to run
            # The script will spawn up this many worker threads,
            #   which shall continue to attempt to get/execute jobs
            'worker_count': 1
        }

        monitor = self.mod.SQSMonitor(**monitor_params)
        time_start = time()
        monitor.run()
        time_end = time()
        # Finished running the monitor.

        time_diff = time_end - time_start

        # Execution took about as long as our quit threshold,
        #   give or take half a second.
        self.assertTrue(time_diff > quit_threshold)
        self.assertTrue(time_diff < quit_threshold + .5)

        self.assertSingle(queue.delete_requests)
        self.assertSingle(queue.receive_requests)

        # Check that we've sent something to the fallback queue
        self.assertSingle(queue_fallback.send_requests)
        msg = self.assertSingle(queue_fallback.messages)
        # The content of our failed task should be in the message's body.
        self.assertEqual('a', msg['Body'])

        # Check our callback invocation log
        self.assertTrue(tracking.get('executed'))

    '''
    Test of SQS-based pulling using a single thread.

    A fallback queue has been set, so failed messages will by submitted there.
    '''
    def test_sqs_error_fallback_absent(self):

        # Track invocations
        tracking = {}
        def callback(task):
            tracking['executed'] = True
            raise Exception('Callback Exception')

        queue_url = 'WorkerQueue'
        queue_url_fallback = 'WorkerQueue-Fallback'
        sqs = MockSQS(queue_url)
        sqs.queues[queue_url_fallback] = MockSQS.Queue()
        sqs_timeout = 60
        quit_threshold = 0.5

        sqs.send_message(QueueUrl = queue_url, MessageBody='a')

        # Confirm the messages that we just sent.
        queue = sqs.queues[queue_url]
        self.assertSingle(queue.send_requests)
        self.assertSingle(queue.messages)
        self.assertEqual(2, queue.message_id)

        queue_fallback = sqs.queues[queue_url_fallback]
        self.assertEmpty(queue_fallback.send_requests)
        self.assertEmpty(queue_fallback.messages)

        # Invoke the monitor.
        # This is what a real instance would do
        monitor_params = {
            # If the monitor runs idle for this many seconds, then exit the script.
            # Set to 0 to run indefinitely.
            'quit_threshold': quit_threshold,
            # SQS client object
            'sqs_object': sqs, # If this weren't a unit test, use boto3.client('sqs') instead.
            # Queue URL
            # For this example, read from arguments
            'sqs_queue': queue_url,
            # Fallback Queue URL
            # If set, then submit messages here when a job throws an exception.
            #'sqs_queue_fallback': queue_url_fallback, # For this test, deliberately NOT setting it.
            # Message Timeout (default 300)
            # Once 2/3 of this duration has passed, the monitor
            #   will refresh the visibility timeout of the SQS
            #   message so that it does not become available for
            #   another worker while this instance is still active.
            'sqs_timeout': sqs_timeout,
            # Set callback, which shall receive one 'task' argument,
            #   as read directly out of the queue.
            'worker_callback': callback,
            # Number of worker threads to run
            # The script will spawn up this many worker threads,
            #   which shall continue to attempt to get/execute jobs
            'worker_count': 1
        }

        monitor = self.mod.SQSMonitor(**monitor_params)
        time_start = time()
        monitor.run()
        time_end = time()
        # Finished running the monitor.

        time_diff = time_end - time_start

        # Execution took about as long as our quit threshold,
        #   give or take half a second.
        self.assertTrue(time_diff > quit_threshold)
        self.assertTrue(time_diff < quit_threshold + .5)

        self.assertSingle(queue.delete_requests)
        self.assertSingle(queue.receive_requests)
        self.assertEmpty(queue.checkouts)
        self.assertEmpty(queue.messages)

        # Because we declined to specify the fallback queue,
        #    it should be completely empty.
        self.assertEmpty(queue_fallback.send_requests)
        self.assertEmpty(queue_fallback.messages)

        # Check our callback invocation log
        self.assertTrue(tracking.get('executed'))

    '''
    Test of SQS-based pulling using a two threads.

    The workers will receive tasks to sleep for the given number of seconds,
    and one of the tasks shall exceed 2/3 of our SQS timeout.

    When the dust clears, there should be one visibility extension request
    for our timeout duration
    '''
    def test_sqs_extension(self):

        # Track invocations
        invocations = []
        def callback(task):
            rest_time = int(task['Body'])
            sleep(rest_time)
            invocations.append(rest_time)

        queue_url = 'WorkerQueue'
        sqs = MockSQS(queue_url)
        sqs_timeout = 6
        quit_threshold = 2

        sqs.send_message(QueueUrl = queue_url, MessageBody='2')
        sqs.send_message(QueueUrl = queue_url, MessageBody='5')
        sqs.send_message(QueueUrl = queue_url, MessageBody='1')

        # Confirm the messages that we just sent.
        url, queue = self.assertSingle(sqs.queues)
        self.assertEqual(queue_url, url)
        self.assertEqual(3, len(queue.send_requests))
        self.assertEqual(3, len(queue.messages))
        self.assertEqual(4, queue.message_id)

        # Invoke the monitor.
        # This is what a real instance would do
        monitor_params = {
            # If the monitor runs idle for this many seconds, then exit the script.
            # Set to 0 to run indefinitely.
            'quit_threshold': quit_threshold,
            # SQS client object
            'sqs_object': sqs, # If this weren't a unit test, use boto3.client('sqs') instead.
            # Queue URL
            # For this example, read from arguments
            'sqs_queue': queue_url,
            # Message Timeout (default 300)
            # Once 2/3 of this duration has passed, the monitor
            #   will refresh the visibility timeout of the SQS
            #   message so that it does not become available for
            #   another worker while this instance is still active.
            'sqs_timeout': sqs_timeout,
            # Set callback, which shall receive one 'task' argument,
            #   as read directly out of the queue.
            'worker_callback': callback,
            # Number of worker threads to run
            # The script will spawn up this many worker threads,
            #   which shall continue to attempt to get/execute jobs
            'worker_count': 2
        }

        monitor = self.mod.SQSMonitor(**monitor_params)
        time_start = time()
        monitor.run()
        time_end = time()
        # Finished running the monitor.

        # Check execution time
        time_diff = time_end - time_start
        # Set '5' for our longest task.
        expected_runtime = 5 + quit_threshold

        self.assertTrue(time_diff > expected_runtime)
        self.assertTrue(time_diff < expected_runtime + .5)

        url, queue = self.assertSingle(sqs.queues)
        self.assertEqual(queue_url, url)
        self.assertEmpty(queue.checkouts)
        self.assertEmpty(queue.messages)
        self.assertEqual(3, len(queue.delete_requests))
        self.assertEqual(3, len(queue.receive_requests))

        visibility_req_success, visibility_req = self.assertSingle(queue.visibility_requests)
        self.assertTrue(visibility_req_success)
        self.assertEqual(sqs_timeout, visibility_req['VisibilityTimeout'])

        # Check our callback invocation log
        self.assertEqual(3, len(invocations))
        # Note, this test logs the invocation AFTER sleeping.
        self.assertEqual(2, invocations[0])
        self.assertEqual(1, invocations[1])
        self.assertEqual(5, invocations[2])
