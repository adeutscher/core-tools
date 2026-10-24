#!/usr/bin/env python

import common, unittest # General test requirements
from unittest import mock # Address resolution overrides
import errno, socket # TCP Tests/Mock Implementation
import os # Environment variable tests
import re # Time Display Tests

mod_static = common.load('ping_stats', common.TOOLS_DIR + '/scripts/networking/ping_stats.py')

def load_module(**kwargs):
    # Keep the caller's shell from changing address selection in tests.
    os.environ.pop('PING_PREFER_IPV6', None)

    mod = common.load('ping_stats', common.TOOLS_DIR + '/scripts/networking/ping_stats.py')
    mod._enable_colours(kwargs.get('colours', False))
    mod.logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

    ctx = MockContext()
    if kwargs.get('override', True):
        mod.sleep = ctx.do_sleep
        mod.cmd = ctx.do_cmd
        mod.get_tcp_socket = lambda family=socket.AF_INET: ctx.make_socket(family)
    return mod, ctx

class MockContext:

    class SafetyException(Exception):
        pass

    def __init__(self):
        # General
        self.sleep = []
        # Ping
        self.cmd = []
        self.output = []
        # TCP
        self.tcp_connect_replies = []
        self.tcp_closures = 0
        self.tcp = []
        self.tcp_families = []

    def arm_ping(self, exit_code = 0, line = None):
        if not line:
            if exit_code:
                line = 'From moot icmp_seq=1 Destination Host Unreachable'
            else:
                line='64 bytes from moot: icmp_seq=1 ttl=64 time=0.046 ms'

        self.output.append((exit_code, line))

    def arm_tcp(self, result):
        if result == mod_static.RESULT_SUCCESS:
            self.tcp_connect_replies.append(0)
        elif result == 'again':
            # Bit of a special handling case since handling is internal to do_tcp.
            self.tcp_connect_replies.append(errno.EAGAIN)
        elif result == mod_static.RESULT_TIMEOUT:
            self.tcp_connect_replies.append(errno.ETIMEDOUT)
        elif result == mod_static.RESULT_CLOSED:
            self.tcp_connect_replies.append(errno.ECONNREFUSED)
        elif result == mod_static.RESULT_UNREACHABLE:
            self.tcp_connect_replies.append(errno.EHOSTUNREACH)

    def connect_ex(self, target):

        if len(self.tcp) >= 100:
            # Safety check to avoid an infinite loop.
            raise MockContext.SafetyException('cmd')

        self.tcp.append(target)

        if not self.tcp_connect_replies:
            self.arm_tcp(mod_static.RESULT_SUCCESS)
        return self.tcp_connect_replies.pop(0)

    def close(self):
        self.tcp_closures += 1

    def make_socket(self, family):
        self.tcp_families.append(family)
        return self

    def do_cmd(self, args, **kwargs):

        if len(self.cmd) >= 100:
            # Safety check to avoid an infinite loop.

            raise MockContext.SafetyException('cmd')

        self.cmd.append((args.copy(), kwargs.copy()))
        if not self.output:
            self.arm_ping()
        exit_code, output = self.output.pop(0)
        return MockProcess(exit_code, output)
    def do_sleep(self, value):
        self.sleep.append(value)

class MockProcess:
    def __init__(self, exit_code, out):
        self.returncode = exit_code
        self.out = out
    def communicate(self):
        return self.out, None

'''
Tests at the argument-parsing stage.
'''
class CommandArgTests(common.TestCase, metaclass=common.LoggableTestCase):
    def setUp(self):
        self.mod, self.ctx = load_module()

    def test_error_bad_args(self):
        with self.assertRaises(SystemExit) as ctx:
            # Give an unknown argument
            self.mod.main(['--foo'])
        self.assertEqual(1, ctx.exception.code)

        error = self.assertSingle(self.getLogs('error'))
        self.assertStartsWith('Error parsing arguments: ', error)
        info = self.getLogs('info')
        # Assume that hexit was invoked if many info lines are present
        self.assertTrue(len(info) > 5)


    def test_error_invalid_count(self):
        exit_code = self.mod.main(['127.0.0.1', '-c', '0'])
        self.assertEqual(1, exit_code)

        self.assertEmpty(self.getLogs('info'))
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Invalid count: 0', error)

    def test_error_invalid_port_low(self):
        exit_code = self.mod.main(['127.0.0.1', '-p', '0'])
        self.assertEqual(1, exit_code)

        self.assertEmpty(self.getLogs('info'))
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Bad TCP port number. Must be an integer in the range of 1-65535', error)

    def test_error_invalid_port_high(self):
        exit_code = self.mod.main(['127.0.0.1', '-p', '65536'])
        self.assertEqual(1, exit_code)

        self.assertEmpty(self.getLogs('info'))
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Bad TCP port number. Must be an integer in the range of 1-65535', error)

    def test_error_noserver(self):
        exit_code = self.mod.main([])
        self.assertEqual(1, exit_code)

        self.assertEmpty(self.getLogs('info'))
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('No target server specified.', error)

    def test_error_streak_conflict(self):
        exit_code = self.mod.main(['127.0.0.1', '-r', '-u'])
        self.assertEqual(1, exit_code)

        self.assertEmpty(self.getLogs('info'))
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Cannot wait for reliable and unreliable pings at the same time.', error)

    def test_error_streak_unreachable_a(self):
        exit_code = self.mod.main(['127.0.0.1', '-r', '-c', '9'])
        self.assertEqual(1, exit_code)

        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Can never reach streak goal of 10 with a count limit of 9.', error)

    def test_error_streak_unreachable_b(self):
        exit_code = self.mod.main(['127.0.0.1', '-u', '-c', '9'])
        self.assertEqual(1, exit_code)

        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Can never reach streak goal of 10 with a count limit of 9.', error)

    def test_hexit(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.main(['-h'])
        self.assertEqual(0, ctx.exception.code)

        self.assertEmpty(self.getLogs('error'))
        info = self.getLogs('info')
        self.assertTrue(len(info) > 5)

'''
Test pinging and general functions.
'''
class CommandPingTests(common.TestCase, metaclass=common.LoggableTestCase):
    def setUp(self):
        self.mod, self.ctx = load_module()

    '''
    Perform a single successful ping.
    '''
    def test_ping_one(self):
        addr = '127.0.0.1'
        exit_code = self.mod.main([addr, '-c', '1'])
        self.assertEqual(0, exit_code)

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEmpty(self.ctx.sleep)

        self.assertEqual(addr, ping_req[-1])
        self.assertEqual(-1, kwargs['stdout'])
        self.assertEqual(-1, kwargs['stderr'])

        self.assertEmpty(self.getLogs('error'))
        info = self.getLogs('info')

        self.assertTrue(len(info) > 5)
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  reply' % addr in l)
        self.assertEmpty(self.getLogs('debug'))

    '''
    Perform a single successful ping with tally mode.
    '''
    def test_ping_one_tally(self):
        addr = '127.0.0.1'
        exit_code = self.mod.main([addr, '-c', '1', '-t'])
        self.assertEqual(0, exit_code)

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEmpty(self.ctx.sleep)

        self.assertEqual(addr, ping_req[-1])
        self.assertEqual(-1, kwargs['stdout'])
        self.assertEqual(-1, kwargs['stderr'])

        self.assertEmpty(self.getLogs('error'))
        info = self.getLogs('info')

        self.assertTrue(len(info) > 5)
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  reply' % addr in l)
        self.assertEmpty(self.getLogs('debug'))

    '''
    Perform a single successful ping with debug enabled.
    '''
    def test_ping_one_debug(self):
        addr = '127.0.0.1'
        exit_code = self.mod.main([addr, '-c', '1', '-d'])
        self.assertEqual(0, exit_code)

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEmpty(self.ctx.sleep)

        self.assertEqual(addr, ping_req[-1])
        self.assertEqual(-1, kwargs['stdout'])
        self.assertEqual(-1, kwargs['stderr'])

        self.assertEmpty(self.getLogs('error'))
        info = self.getLogs('info')

        self.assertTrue(len(info) > 5)
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  reply' % addr in l)
        debug = self.assertSingle(self.getLogs('debug'))

    '''
    Perform a single failed ping.
    '''
    def test_ping_one_fail(self):
        addr = '127.0.2.2'
        self.ctx.arm_ping(1) # Arm a failed ping
        exit_code = self.mod.main([addr, '-c', '1'])
        self.assertEqual(0, exit_code)

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEmpty(self.ctx.sleep)

        self.assertEqual(addr, ping_req[-1])
        self.assertEqual(-1, kwargs['stdout'])
        self.assertEqual(-1, kwargs['stderr'])

        self.assertEmpty(self.getLogs('error'))
        info = self.getLogs('info')

        self.assertTrue(len(info) > 5)
        self.assertSingle(info, lambda l: '0.00%%  [-_________]  %s  timeout' % addr in l)

    '''
    Perform two pings, with both succeeding
    '''
    def test_ping_two(self):
        addr = '127.0.1.1'
        exit_code = self.mod.main([addr, '-c', '2'])
        self.assertEqual(0, exit_code)

        # Expected to sleep in between
        sleep = self.assertSingle(self.ctx.sleep)
        self.assertTrue(sleep < 1.001 and sleep > 0.90)

        self.assertEqual(2, len(self.ctx.cmd))
        ping_req1, kwargs1 = self.ctx.cmd[0]
        ping_req2, kwargs2 = self.ctx.cmd[1]

        self.assertEqual(addr, ping_req1[-1])
        self.assertEqual(-1, kwargs1['stdout'])
        self.assertEqual(-1, kwargs1['stderr'])

        self.assertEqual(ping_req1, ping_req2)
        self.assertEqual(kwargs1, kwargs2)

        info = self.getLogs('info')
        self.assertTrue(len(info) > 5)
        self.assertDoesNotContain(lambda i: 'Time between attempts (seconds):' in i, info)
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  reply' % addr in l)
        self.assertSingle(info, lambda l: '100.00%%  [^^________]  %s  reply' % addr in l)

    '''
    Perform two pings, with the second one failing.
    This should cause a display of a 50% success rate.

    '''
    def test_ping_partial(self):
        addr = '127.0.1.1'

        self.ctx.arm_ping(0) # Success
        self.ctx.arm_ping(1) # Failure

        exit_code = self.mod.main([addr, '-c', '2'])
        self.assertEqual(0, exit_code)

        # Expected to sleep in between
        sleep = self.assertSingle(self.ctx.sleep)
        self.assertTrue(sleep < 1.001 and sleep > 0.90)

        self.assertEqual(2, len(self.ctx.cmd))
        ping_req1, kwargs1 = self.ctx.cmd[0]
        ping_req2, kwargs2 = self.ctx.cmd[1]

        self.assertEqual(addr, ping_req1[-1])
        self.assertEqual(-1, kwargs1['stdout'])
        self.assertEqual(-1, kwargs1['stderr'])

        self.assertEqual(ping_req1, ping_req2)
        self.assertEqual(kwargs1, kwargs2)

        info = self.getLogs('info')
        self.assertTrue(len(info) > 5)
        self.assertDoesNotContain(lambda i: 'Time between attempts (seconds):' in i, info)
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  reply' % addr in l)
        self.assertSingle(info, lambda l: ' 50.00%%  [^-________]  %s  timeout' % addr in l)

    '''
    Perform two pings.
    '''
    def test_ping_two_interval(self):
        addr = '127.1.1.1'
        exit_code = self.mod.main([addr, '-c', '2', '-i', '5'])

        # Expected to sleep in between
        sleep = self.assertSingle(self.ctx.sleep)
        self.assertTrue(sleep < 5.001 and sleep > 4.90)

        self.assertEqual(2, len(self.ctx.cmd))
        ping_req1, kwargs1 = self.ctx.cmd[0]
        ping_req2, kwargs2 = self.ctx.cmd[1]

        self.assertEqual(addr, ping_req1[-1])
        self.assertEqual(-1, kwargs1['stdout'])
        self.assertEqual(-1, kwargs1['stderr'])

        self.assertEqual(ping_req1, ping_req2)
        self.assertEqual(kwargs1, kwargs2)

        self.assertEmpty(self.getLogs('error'))
        info = self.getLogs('info')
        self.assertContains('Time between attempts (seconds): 5', info)

    '''
    Perform an unrestricted ping, with a reliability check.

    Quit after 5 consecutive successful pings in a row.

    The system will succeed on the first ping, fail on the next ping, then continue successfully.

    This should result in a total of 7 pings
    '''
    def test_ping_reliability_reliable(self):

        self.ctx.arm_ping(0) # First ping: success
        self.ctx.arm_ping(1) # Second ping: failure

        addr = '127.1.2.7'

        exit_code = self.mod.main([addr, '5', '-r'])
        self.assertEqual(0, exit_code)

        expected_number = 7
        self.assertEqual(expected_number, len(self.ctx.cmd))
        self.assertEqual(expected_number - 1, len(self.ctx.sleep))

        info = self.getLogs('info')
        # Spot-check mid-way through
        self.assertSingle(info, lambda l: '75.00%%  [^-^^______]  %s  reply' % addr in l)
        self.assertSingle(info, lambda l: '80.00%%  [^-^^^_____]  %s  reply' % addr in l)

    '''
    Perform an unrestricted ping, with a reliability check.

    Quit after 10 consecutive successful pings in a row (the default),
      but only give the script 5 pings in which to do it.

    The script will encounter one failure, meaning that it
      should not be able to reach it's streak.

    The exit_code from this should be 1.
    '''
    def test_ping_reliability_reliable_limited(self):

        self.ctx.arm_ping(1) # First ping: failure

        addr = '127.1.2.7'

        exit_code = self.mod.main([addr, '-r', '-c', '10'])
        self.assertEqual(1, exit_code)

        expected_number = 10
        self.assertEqual(expected_number, len(self.ctx.cmd))
        self.assertEqual(expected_number - 1, len(self.ctx.sleep))

        info = self.getLogs('info')
        # Spot-check mid-way through
        self.assertSingle(info, lambda l: '75.00%%  [-^^^______]  %s  reply' % addr in l)
        self.assertSingle(info, lambda l: '80.00%%  [-^^^^_____]  %s  reply' % addr in l)

    '''
    Perform an unrestricted ping, with a reliability check.

    Quit after 6 consecutive unsuccessful pings in a row.

    The script should behave as follows:
        1. Fail on the first ping
        2. Succeed on the second and third pings
        3. Fail on the next 6 pings

    This should result in a total of 9 pings
    '''
    def test_ping_reliability_unreliable(self):

        self.ctx.arm_ping(1) # First ping: failure
        self.ctx.arm_ping(0) # Second/Third ping: success
        self.ctx.arm_ping(0)
        for i in range(6):    # Next 6 pings: Failure
            self.ctx.arm_ping(1)
        # If we went beyond the 6 defined failures,
        #   we would default to successes that would trigger a test-safety net.

        addr = '127.1.2.7'

        exit_code = self.mod.main([addr, '6', '-u'])
        self.assertEqual(0, exit_code)

        expected_number = 9
        self.assertEqual(expected_number, len(self.ctx.cmd))
        self.assertEqual(expected_number - 1, len(self.ctx.sleep))

        info = self.getLogs('info')
        # Spot-check mid-way through
        self.assertSingle(info, lambda l: '50.00%%  [-^^-______]  %s  timeout' % addr in l)

    '''
    Perform an unrestricted ping, with a reliability check and tally mode.

    Quit after 6 consecutive unsuccessful pings in a row.

    The script should behave as follows:
        1. Fail on the first ping
        2. Succeed on the second and third pings
        3. Fail on the next 6 pings

    This should result in a total of 9 pings
    '''
    def test_ping_reliability_unreliable_tally(self):

        self.ctx.arm_ping(1) # First ping: failure
        self.ctx.arm_ping(0) # Second/Third ping: success
        self.ctx.arm_ping(0)
        for i in range(6):    # Next 6 pings: Failure
            self.ctx.arm_ping(1)
        # If we went beyond the 6 defined failures,
        #   we would default to successes that would trigger a test-safety net.

        addr = '127.1.2.7'

        exit_code = self.mod.main([addr, '6', '-u', '-t'])
        self.assertEqual(0, exit_code)

        expected_number = 9
        self.assertEqual(expected_number, len(self.ctx.cmd))
        self.assertEqual(expected_number - 1, len(self.ctx.sleep))

        info = self.getLogs('info')
        # Spot-check mid-way through
        self.assertSingle(info, lambda l: '50.00%%  [-^^-______]  %s  timeout' % addr in l)

    '''
    Perform an unrestricted ping, which should trigger a test-only safety check.
    '''
    def test_ping_unlimited(self):
        addr = '127.1.2.3'

        with self.assertRaises(MockContext.SafetyException) as ctx:
            self.mod.main([addr])

        expected_number = 100
        self.assertEqual(expected_number, len(self.ctx.cmd))
        self.assertEqual(expected_number, len(self.ctx.sleep))

        info = self.getLogs('info')
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  reply' % addr in l)
        self.assertEqual(expected_number - 9, len([1 for l in info if '100.00%%  [^^^^^^^^^^]  %s  reply' % addr in l]))
        self.assertContains('100/100 100.00%%  [^^^^^^^^^^]  %s  reply' % addr, info[-1])

'''
Tests specifically covering TCP
'''
class CommandTcpTests(common.TestCase, metaclass=common.LoggableTestCase):

    def setUp(self):
        self.mod, self.ctx = load_module()

    '''
    Send a single TCP packet to TCP/22.
    '''
    def test_tcp_single(self):
        addr = '127.1.2.3'
        port = '22'

        exit_code = self.mod.main([addr, '-c', '1', '-p', port])
        self.assertEqual(0, exit_code)

        req_addr, req_port = self.assertSingle(self.ctx.tcp)
        self.assertEqual(addr, req_addr)
        self.assertEqual(int(port), req_port)

        info = self.getLogs('info')
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  open  TCP/%s' % (addr, port) in l)
        self.assertEmpty(self.getLogs('debug'))

    '''
    Send a single TCP packet to TCP/22.
    '''
    def test_tcp_single_debug(self):
        addr = '127.1.2.3'
        port = '22'

        exit_code = self.mod.main([addr, '-c', '1', '-p', port, '-d'])
        self.assertEqual(0, exit_code)

        req_addr, req_port = self.assertSingle(self.ctx.tcp)
        self.assertEqual(addr, req_addr)
        self.assertEqual(int(port), req_port)

        info = self.getLogs('info')
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  open  TCP/%s' % (addr, port) in l)
        debug = self.assertSingle(self.getLogs('debug'))

    '''
    Demo the range of TCP responses.
    '''
    def test_tcp_range(self):
        addr = '127.1.2.3'
        port = '22'

        self.ctx.arm_tcp(mod_static.RESULT_SUCCESS)
        self.ctx.arm_tcp('again')
        self.ctx.arm_tcp(mod_static.RESULT_TIMEOUT)
        self.ctx.arm_tcp(mod_static.RESULT_CLOSED)
        self.ctx.arm_tcp(mod_static.RESULT_UNREACHABLE)

        exit_code = self.mod.main([addr, '-c', '5', '-p', port])
        self.assertEqual(0, exit_code)

        info = self.getLogs('info')
        # This shows that closed does NOT count as a success, despite the similar icon.
        self.assertSingle(info, lambda l: ' 25.00%%  [^-^x______]  %s  unreachable  TCP/%s' % (addr, port) in l)
        self.assertSingle(info, lambda l: ' 40.00%%  [^-^x^_____]  %s  open  TCP/%s' % (addr, port) in l)

    '''
    Perform an unrestricted ping to TCP/1234, which should trigger a test-only safety check.
    '''
    def test_tcp_unlimited(self):
        addr = '127.127.0.1'
        port = '1234'

        with self.assertRaises(MockContext.SafetyException) as ctx:
            self.mod.main([addr, '-p', port])

        expected_number = 100
        self.assertEqual(expected_number, len(self.ctx.tcp))
        self.assertEqual(expected_number, len(self.ctx.sleep))

        info = self.getLogs('info')
        self.assertSingle(info, lambda l: '100.00%%  [^_________]  %s  open  TCP/%s' % (addr, port) in l)
        self.assertEqual(expected_number - 9, len([1 for l in info if '100.00%%  [^^^^^^^^^^]  %s  open  TCP/%s' % (addr, port) in l]))
        self.assertContains('100/100 100.00%%  [^^^^^^^^^^]  %s  open  TCP/%s' % (addr, port), info[-1])

'''
Tests for IPv6 handling and address family selection.
'''
class IPv6Tests(common.TestCase, metaclass=common.LoggableTestCase):
    def setUp(self):
        self.mod, self.ctx = load_module()
        self.mod.platform = lambda: 'Linux'

    def fake_getaddrinfo(self, host, port, family=0, socktype=0):
        '''Dual-stack host that lists IPv6 first, as a system preferring IPv6 would.'''
        results = []
        if host in ('dualstack', 'v6only'):
            results.append((socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:db8::1', port or 0, 0, 0)))
        if host in ('dualstack', 'v4only'):
            results.append((socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', port or 0)))
        results = [r for r in results if family in (socket.AF_UNSPEC, r[0])]
        if not results:
            raise socket.gaierror(socket.EAI_NONAME, 'Name or service not known')
        return results

    def run_tcp(self, *extra):
        with mock.patch.object(self.mod.socket, 'getaddrinfo', self.fake_getaddrinfo):
            return self.mod.main(list(extra) + ['-c', '1', '-p', '22'])

    def test_error_both_families(self):
        exit_code = self.mod.main(['127.0.0.1', '-4', '-6'])
        self.assertEqual(1, exit_code)
        self.assertSingle(self.getLogs('error'), lambda l: 'Cannot use -4 and -6' in l)

    def test_error_family_with_url(self):
        exit_code = self.mod.main(['http://localhost/', '-6'])
        self.assertEqual(1, exit_code)
        self.assertSingle(self.getLogs('error'), lambda l: 'only apply to ICMP and TCP' in l)

    def test_error_prefer_ipv6_with_url(self):
        exit_code = self.mod.main(['http://localhost/', '--prefer-ipv6'])
        self.assertEqual(1, exit_code)
        self.assertSingle(self.getLogs('error'), lambda l: 'only apply to ICMP and TCP' in l)

    def test_error_prefer_ipv6_with_ipv4_only(self):
        exit_code = self.mod.main(['127.0.0.1', '-4', '--prefer-ipv6'])
        self.assertEqual(1, exit_code)
        self.assertSingle(self.getLogs('error'), lambda l: 'Cannot use -4 and --prefer-ipv6' in l)

    def test_family_default_prefers_ipv4(self):
        # The fake resolver lists IPv6 first, so this overrides the system order.
        self.assertEqual(0, self.run_tcp('dualstack'))
        self.assertEqual([socket.AF_INET], self.ctx.tcp_families)
        self.assertEqual([('192.0.2.1', 22)], self.ctx.tcp)

    def test_family_default_falls_back_to_ipv6(self):
        self.assertEqual(0, self.run_tcp('v6only'))
        self.assertEqual([('2001:db8::1', 22, 0, 0)], self.ctx.tcp)

    def test_family_prefer_ipv6(self):
        self.assertEqual(0, self.run_tcp('dualstack', '--prefer-ipv6'))
        self.assertEqual([socket.AF_INET6], self.ctx.tcp_families)
        self.assertEqual([('2001:db8::1', 22, 0, 0)], self.ctx.tcp)

    def test_family_prefer_ipv6_falls_back_to_ipv4(self):
        self.assertEqual(0, self.run_tcp('v4only', '--prefer-ipv6'))
        self.assertEqual([('192.0.2.1', 22)], self.ctx.tcp)

    def run_tcp_env(self, value, *extra):
        with mock.patch.dict(os.environ, {'PING_PREFER_IPV6': value}):
            return self.run_tcp(*extra)

    def test_env_prefer_ipv6(self):
        for value in ('1', 'true', 'YES', ' on '):
            self.ctx.tcp = []
            self.assertEqual(0, self.run_tcp_env(value, 'dualstack'), value)
            self.assertEqual([('2001:db8::1', 22, 0, 0)], self.ctx.tcp, value)

    def test_env_prefer_ipv4(self):
        for value in ('', '0', 'false', 'No', 'off'):
            self.ctx.tcp = []
            self.assertEqual(0, self.run_tcp_env(value, 'dualstack'), value)
            self.assertEqual([('192.0.2.1', 22)], self.ctx.tcp, value)

    def test_env_prefer_ipv6_falls_back_to_ipv4(self):
        self.assertEqual(0, self.run_tcp_env('1', 'v4only'))
        self.assertEqual([('192.0.2.1', 22)], self.ctx.tcp)

    def test_env_prefer_ipv6_overridden_by_ipv4_flag(self):
        self.assertEqual(0, self.run_tcp_env('1', 'dualstack', '-4'))
        self.assertEqual([('192.0.2.1', 22)], self.ctx.tcp)
        self.assertEmpty(self.getLogs('error'))

    def test_env_prefer_ipv6_ignored_for_url(self):
        with mock.patch.dict(os.environ, {'PING_PREFER_IPV6': '1'}):
            valid, args = self.mod.parse_args(['http://localhost/'])
        self.assertTrue(valid)
        self.assertEmpty(self.getLogs('error'))

    def test_env_invalid(self):
        self.assertEqual(1, self.run_tcp_env('maybe', 'dualstack'))
        self.assertSingle(self.getLogs('error'), lambda l: 'Invalid PING_PREFER_IPV6 value: maybe' in l)
        self.assertEmpty(self.ctx.tcp)

    def test_family_forced_ipv4(self):
        self.assertEqual(0, self.run_tcp('dualstack', '-4'))
        self.assertEqual([socket.AF_INET], self.ctx.tcp_families)
        self.assertEqual([('192.0.2.1', 22)], self.ctx.tcp)

    def test_family_forced_ipv6(self):
        self.assertEqual(0, self.run_tcp('dualstack', '-6'))
        self.assertEqual([('2001:db8::1', 22, 0, 0)], self.ctx.tcp)

    def test_family_forced_ipv6_unavailable(self):
        self.assertEqual(1, self.run_tcp('v4only', '-6'))
        self.assertSingle(self.getLogs('error'), lambda l: 'Unable to resolve address' in l)

    def test_icmp_ipv6_literal(self):
        self.ctx.arm_ping(line='64 bytes from ::1: icmp_seq=1 ttl=64 time=0.045 ms')
        exit_code = self.mod.main(['::1', '-c', '1'])
        self.assertEqual(0, exit_code)

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEqual(['ping', '-6', '-W1', '-c1', '::1'], ping_req)
        self.assertSingle(self.getLogs('info'), lambda l: '::1  reply  ttl=64 t=0.04 ms' in l)

    def test_icmp_ipv6_hostname_reply(self):
        self.ctx.arm_ping(line='64 bytes from localhost (::1): icmp_seq=1 ttl=64 time=0.045 ms')
        exit_code = self.mod.main(['::1', '-c', '1'])
        self.assertEqual(0, exit_code)
        self.assertSingle(self.getLogs('info'), lambda l: '::1  reply  ttl=64 t=0.04 ms' in l)

    def test_icmp_ipv6_darwin(self):
        self.mod.platform = lambda: 'Darwin'
        self.ctx.arm_ping(line='16 bytes from ::1, icmp_seq=0 hlim=64 time=0.045 ms')
        self.mod.main(['::1', '-c', '1'])
        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEqual(['ping6', '-c1', '::1'], ping_req)

    def test_icmp_ipv6_windows(self):
        self.mod.platform = lambda: 'Windows'
        self.ctx.arm_ping(line='Reply from ::1: time<1ms')
        exit_code = self.mod.main(['::1', '-c', '1'])
        self.assertEqual(0, exit_code)

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEqual(['ping', '-6', '-w', '1000', '-n', '1', '::1'], ping_req)
        self.assertSingle(self.getLogs('info'), lambda l: '::1  reply  time<1ms' in l)

    def test_icmp_ipv4_windows(self):
        self.mod.platform = lambda: 'Windows'
        self.ctx.arm_ping(line='Reply from 127.0.0.1: bytes=32 time<1ms TTL=128')
        exit_code = self.mod.main(['127.0.0.1', '-c', '1'])
        self.assertEqual(0, exit_code)

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEqual(['ping', '-w', '1000', '-n', '1', '127.0.0.1'], ping_req)
        self.assertSingle(self.getLogs('info'), lambda l: '127.0.0.1  reply  time<1ms TTL=128' in l)

    def test_strip_ipv6_prefix(self):
        tests = [
            ('fe80::7285:c2ff:fec2:200d/64%enp39s0', 'fe80::7285:c2ff:fec2:200d%enp39s0'),
            ('fe80::7285:c2ff:fec2:200d%enp39s0/64', 'fe80::7285:c2ff:fec2:200d%enp39s0'),
            ('fe80::7285:c2ff:fec2:200d/64', 'fe80::7285:c2ff:fec2:200d'),
            ('2001:db8::1/128', '2001:db8::1'),
            ('::/0', '::'),
            # Left alone
            ('fe80::7285:c2ff:fec2:200d', 'fe80::7285:c2ff:fec2:200d'),
            ('fe80::7285:c2ff:fec2:200d%enp39s0', 'fe80::7285:c2ff:fec2:200d%enp39s0'),
            ('2001:db8::1/129', '2001:db8::1/129'),
            ('2001:db8::1/64/64', '2001:db8::1/64/64'),
            ('192.0.2.1/24', '192.0.2.1/24'),
            ('example.com/64', 'example.com/64'),
            ('example.com', 'example.com'),
        ]
        for value, expected in tests:
            self.assertEqual(expected, self.mod._strip_ipv6_prefix(value), value)

    def test_icmp_ipv6_prefix_stripped(self):
        self.ctx.arm_ping(line='64 bytes from 2001:db8::1: icmp_seq=1 ttl=64 time=0.045 ms')
        with mock.patch.object(self.mod.socket, 'getaddrinfo', wraps=socket.getaddrinfo) as lookup:
            exit_code = self.mod.main(['2001:db8::1/64', '-c', '1'])
        self.assertEqual(0, exit_code)
        self.assertEqual('2001:db8::1', lookup.call_args[0][0])

        ping_req, kwargs = self.assertSingle(self.ctx.cmd)
        self.assertEqual('2001:db8::1', ping_req[-1])
        self.assertSingle(self.getLogs('info'), lambda l: '2001:db8::1  reply' in l)

    def test_tcp_ipv6_literal(self):
        exit_code = self.mod.main(['::1', '-c', '1', '-p', '22'])
        self.assertEqual(0, exit_code)
        self.assertEqual([socket.AF_INET6], self.ctx.tcp_families)
        self.assertEqual([('::1', 22, 0, 0)], self.ctx.tcp)

    def test_tcp_network_unreachable(self):
        self.ctx.tcp_connect_replies.append(errno.ENETUNREACH)
        self.mod.main(['::1', '-c', '1', '-p', '22'])
        self.assertSingle(self.getLogs('info'), lambda l: '::1  unreachable  TCP/22' in l)

class TimeDisplayTests(unittest.TestCase):

    def __test_unit(self, unit, multiplier, increment):
        '''Central method for testing only one unit'''
        self.assertEqual('1 %s' % unit, self.mod._translate_seconds(multiplier))
        for i in range(2,increment-1):
            self.assertEqual('%d %ss' % (i, unit), self.mod._translate_seconds(i * multiplier))
        self.assertNotEqual('%d %ss' % (increment, unit), self.mod._translate_seconds(increment * multiplier))

    def setUp(self):
        # Discard ctx
        self.mod, ctx = load_module()

    def test_combo_oxford_a(self):
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('4 hours, 5 minutes, and 52 seconds', self.mod._translate_seconds(hours + minutes + seconds))

    def test_combo_oxford_b(self):
        years = 3 * 52 * 7 * 24 * 60 * 60
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('3 years, 4 hours, 5 minutes, and 52 seconds', self.mod._translate_seconds(years + hours + minutes + seconds))

    def test_combo_oxford_c(self):
        years = 3 * 52 * 7 * 24 * 60 * 60
        weeks = 42 * 7 * 24 * 60 * 60
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('3 years, 42 weeks, 4 hours, 5 minutes, and 52 seconds', self.mod._translate_seconds(years + weeks + hours + minutes + seconds))

    def test_combo_two_values_a(self):
        hours = 4 * 60 * 60
        minutes = 5 * 60

        self.assertEqual('4 hours, 5 minutes', self.mod._translate_seconds(hours + minutes))

    def test_combo_two_values_b(self):
        days = 4 * 24 * 60 * 60
        seconds = 22

        self.assertEqual('4 days, 22 seconds', self.mod._translate_seconds(days + seconds))

    def test_only_days(self):
        self.__test_unit('day', 60 * 60 * 24, 7)

    def test_only_hours(self):
        self.__test_unit('hour', 60 * 60, 24)

    def test_only_minutes(self):
        self.__test_unit('minute', 60, 60)

    def test_only_seconds(self):
        self.__test_unit('second', 1, 60)

    def test_zero_seconds(self):
        self.assertEqual('0 seconds', self.mod._translate_seconds(0))


'''
Tests for anything not covered under another test case.
'''
class UtilityTests(common.TestCase, metaclass=common.LoggableTestCase):
    def setUp(self):
        self.mod, self.ctx = load_module(override=False)

    def test_build_logger(self):
        self.assertNotEqual(None, self.mod._build_logger('label'))
        self.assertNotEqual(None, self.mod.logger)

    def test_get_target(self):
        tests = [
            ('a', 'b', 'a (b)'),
            ('a', 'a', 'a')
        ]

        for addr, ip, expected in tests:
            self.assertEqual(expected, self.mod.get_target_display(addr=addr, ip=ip))

    '''
    Confirm the behavior of the get_tcp_socket function,
      which is overridden for most other tests.
    '''
    def test_get_tcp_socket(self):
        s = mod_static.get_tcp_socket()
        self.assertIs(socket.socket, type(s))
        self.assertEqual(socket.AF_INET, s.family)
        self.assertEqual(socket.SOCK_STREAM, s.type)
        self.assertEqual(1, s.timeout)

    def test_translate_result(self):
        tests = [
            (mod_static.RESULT_SUCCESS, 'success'),
            (mod_static.RESULT_CLOSED, 'closed'),
            (mod_static.RESULT_TIMEOUT, 'timeout'),
            (mod_static.RESULT_UNREACHABLE, 'unreachable')
        ]
        for result, expected in tests:
            self.assertEqual(expected, mod_static._translate_result(result))
