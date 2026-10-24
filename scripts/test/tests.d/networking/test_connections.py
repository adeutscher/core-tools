#!/usr/bin/env python

import common, unittest # General test requirements

import io, ipaddress, json, os, socket, struct, tempfile, unittest.mock

class BaseConnectionsTest(common.TestCase):

    def setUp(self):
        self.mod = common.load('connections', common.TOOLS_DIR + '/scripts/networking/connections.py')
        self.mod.print_error = lambda message: None
        self.mod.print_warning = lambda message: None

    def interface(self, name, address):
        return self.mod.Interface(name, ipaddress.ip_interface(address))

    def interfaces(self, *extra):
        return [self.interface('lo', '127.0.0.1/8'), self.interface('eth0', '10.11.12.13/24')] + list(extra)

    '''
    Readers that return the given lines for every text source.
    Netlink is unavailable unless records are given.
    '''
    def readers(self, lines, records=None):
        readers = dict((k, lambda: list(lines)) for k in self.mod.READERS)

        def netlink():
            if records is None:
                raise OSError(93, 'Protocol not supported')
            return list(records)
        readers[self.mod.Source.NETLINK] = netlink
        return readers

    '''
    Parse arguments and collect connections from the given input lines.
    '''
    def run_lines(self, lines, argv, interfaces=None):
        args, errors = self.mod.parse_args(argv)
        self.assertEmpty(errors)
        return self.mod.collect(args, self.readers(lines), lambda: interfaces or self.interfaces())

    '''
    Orient a single parsed socket record into a connection.
    '''
    def orient(self, record):
        self.assertNotEqual(None, record)
        return self.assertSingle(self.mod.connections_from_sockets([record]))

class ConnectionsTests(BaseConnectionsTest):

    '''
    Given two connections, filter down to one by src port range
    '''
    def test_run_filter_src_port_range(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:1234      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', 'src:*:2000-1000']))
        self.assertEqual('30.30.30.30/1234->10.11.12.13/445', str(connection))

    '''
    Given two connections, show the incoming one.
    '''
    def test_run_filter_incoming(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:1234        30.30.30.30:445      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat']))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    Given two connections, show the outgoing one.
    '''
    def test_run_filter_outgoing(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:1234        30.30.30.30:445      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-o']))
        self.assertEqual('10.11.12.13/1234->30.30.30.30/445', str(connection))

    '''
    Confirm that localhost connections can be shown using the proper switch.
    '''
    def test_run_filter_localhost(self):
        lines = ['tcp        0      0 127.0.0.1:22            127.0.1.1:1122      ESTABLISHED']
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-L']))
        self.assertEqual('127.0.1.1/1122->127.0.0.1/22', str(connection))

    '''
    Confirm that localhost connections are normally excluded
    '''
    def test_run_filter_localhost_excluded(self):
        lines = ['tcp        0      0 127.0.0.1:22            127.0.1.1:1122      ESTABLISHED']
        self.assertEmpty(self.run_lines(lines, ['--netstat']))

    '''
    Without -l or -r, -L shows only localhost connections.
    '''
    def test_run_filter_localhost_only(self):
        lines = [
            'tcp        0      0 127.0.0.1:22            127.0.1.1:1122      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321    ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-L']))
        self.assertEqual('127.0.1.1/1122->127.0.0.1/22', str(connection))
        self.assertEqual(2, len(self.run_lines(lines, ['--netstat', '-L', '-r'])))

    '''
    Given two connections, filter down to one by source port
    '''
    def test_run_filter_src_port(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:1234      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', 'src:tcp/4321']))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    Given two connections, filter down to one by excluding a source port
    '''
    def test_run_filter_src_port_exclusion(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:1234      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-e', 'src:tcp/4321']))
        self.assertEqual('30.30.30.30/1234->10.11.12.13/445', str(connection))

    '''
    Given two source addresses, filter down to one by address
    '''
    def test_run_filter_src_address(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:4321      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', 'src:20.20.20.20']))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    Given two source addresses, filter down to one by cidr range
    '''
    def test_run_filter_src_cidr(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:4321      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', 'src:30.30.30.0/24']))
        self.assertEqual('30.30.30.30/4321->10.11.12.13/445', str(connection))

    def test_run_filter_and(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:4321      ESTABLISHED'
        ]
        self.assertEqual(2, len(self.run_lines(lines, ['--netstat', '20.20.20.20', '30.30.30.30'])))
        self.assertEmpty(self.run_lines(lines, ['--netstat', '--filter-and', '20.20.20.20', '30.30.30.30']))

    '''
    An exclusion filter for a hostname with several addresses excludes all of them.
    '''
    def test_run_filter_exclusion_multiple_addresses(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         40.40.40.40:4321      ESTABLISHED'
        ]
        resolved = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (a, 0)) for a in ('20.20.20.20', '30.30.30.30', '20.20.20.20')]
        with unittest.mock.patch.object(self.mod.socket, 'getaddrinfo', return_value=resolved):
            connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-e', 'multi.example']))
        self.assertEqual('40.40.40.40/4321->10.11.12.13/445', str(connection))

    def test_run_filter_lan(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         192.168.1.5:4321      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-l']))
        self.assertEqual('192.168.1.5/4321->10.11.12.13/445', str(connection))
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-r']))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))
        # Opposite modes cancel out
        self.assertEqual(2, len(self.run_lines(lines, ['--netstat', '-l', '-r'])))

    def test_run_filter_lan_interfaces(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         10.11.12.13:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         192.168.1.5:4321      ESTABLISHED'
        ]
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-l', '--lan-interfaces']))
        self.assertEqual('10.11.12.13/4321->10.11.12.13/445', str(connection))

    '''
    A /32 interface only makes its own address a LAN address.
    '''
    def test_run_filter_lan_interfaces_host_route(self):
        lines = [
            'tcp        0      0 100.96.0.2:445          100.96.0.3:4321       ESTABLISHED',
            'tcp        0      0 100.96.0.2:445          10.11.12.13:4321      ESTABLISHED'
        ]
        interfaces = self.interfaces(self.interface('warp', '100.96.0.2/32'))
        connections = self.run_lines(lines, ['--netstat', '-l', '--lan-interfaces'], interfaces)
        connection = self.assertSingle(connections)
        self.assertEqual('10.11.12.13/4321->100.96.0.2/445', str(connection))

    def test_run_filter_no_self(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         10.11.12.13:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED'
        ]
        interfaces = self.interfaces(self.interface('eth1', '10.11.12.13/24'))
        self.assertEqual(2, len(self.run_lines(lines, ['--netstat'], interfaces)))
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '--no-self'], interfaces))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    The same connection seen twice is only reported once.
    '''
    def test_run_duplicates(self):
        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED'
        ]
        self.assertSingle(self.run_lines(lines, ['--netstat']))

    '''
    Basic test of being able to pick up a connection from conntrack.
    '''
    def test_run_conntrack_basic(self):
        lines = ['tcp      6 431951 ESTABLISHED src=10.11.12.13 dst=10.11.12.13 sport=12345 dport=22 src=10.11.12.13 dst=10.11.12.13 sport=22 dport=12345 [ASSURED] mark=0 use=1']
        connection = self.assertSingle(self.run_lines(lines, ['-C']))
        self.assertEqual('10.11.12.13/12345->10.11.12.13/22', str(connection))

    '''
    Basic test of being able to pick up a connection from netstat.
    '''
    def test_run_netstat_basic(self):
        lines = ['tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED']
        connection = self.assertSingle(self.run_lines(lines, ['--netstat']))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    Confirm that the script will not explode given no arguments.
    '''
    def test_run_noargs(self):
        self.assertEmpty(self.run_lines([], []))

    '''
    Basic test of being able to pick up a connection from procfs.
    '''
    def test_run_procfs_basic(self):
        interfaces = self.interfaces(self.interface('eth1', '192.168.0.1/24'))
        connection = self.assertSingle(self.run_lines(['0: 0100A8C0:0016 6400A8C0:F106 01'], [], interfaces))
        self.assertEqual('192.168.0.100/61702->192.168.0.1/22', str(connection))

    '''
    Standard input is read instead of the source, but parsed in the source's format.
    '''
    def test_run_stdin(self):
        args, errors = self.mod.parse_args(['-S', '--netstat'])
        readers = self.readers([])
        readers[self.mod.STDIN] = lambda: ['tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED']
        connection = self.assertSingle(self.mod.collect(args, readers, self.interfaces))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    Standard input without a format option is parsed as /proc/net/tcp, never Netlink.
    '''
    def test_run_stdin_procfs(self):
        args, errors = self.mod.parse_args(['-S'])
        readers = self.readers([], records=[])
        readers[self.mod.STDIN] = lambda: ['1: 0A0A0A0A:01BD 14141414:10E1 01']
        connection = self.assertSingle(self.mod.collect(args, readers, self.interfaces))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    Netlink records are used when Netlink is available.
    '''
    def test_run_netlink(self):
        args, errors = self.mod.parse_args([])
        records = [self.mod.parse_procfs_line('1: 0A0A0A0A:01BD 14141414:10E1 01')]
        readers = self.readers(['1: 0A0A0A0A:01BD 1E1E1E1E:10E1 01'], records=records)
        connection = self.assertSingle(self.mod.collect(args, readers, self.interfaces))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    procfs is read when Netlink is unavailable.
    '''
    def test_run_netlink_fallback(self):
        connection = self.assertSingle(self.run_lines(['1: 0A0A0A0A:01BD 1E1E1E1E:10E1 01'], []))
        self.assertEqual('30.30.30.30/4321->10.11.12.13/445', str(connection))

    '''
    --procfs skips Netlink even when it is available.
    '''
    def test_run_procfs_option(self):
        args, errors = self.mod.parse_args(['--procfs'])
        records = [self.mod.parse_procfs_line('1: 0A0A0A0A:01BD 14141414:10E1 01')]
        readers = self.readers(['1: 0A0A0A0A:01BD 1E1E1E1E:10E1 01'], records=records)
        connection = self.assertSingle(self.mod.collect(args, readers, self.interfaces))
        self.assertEqual('30.30.30.30/4321->10.11.12.13/445', str(connection))

class ArgumentTests(BaseConnectionsTest):

    def parse_exits(self, argv):
        with unittest.mock.patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                self.mod.parse_args(argv)

    def test_args_conflicting_sources(self):
        self.parse_exits(['--netstat', '-C'])
        self.parse_exits(['--procfs', '--netstat'])
        self.parse_exits(['--procfs', '-C'])

    '''
    -n is a deprecated, hidden alias for --netstat.
    '''
    def test_args_netstat_alias(self):
        args, errors = self.mod.parse_args(['-n'])
        self.assertEmpty(errors)
        self.assertEqual(self.mod.Source.NETSTAT, args.source)
        self.assertSingle(args.warnings)
        self.assertEmpty(self.mod.parse_args(['--netstat'])[0].warnings)

        for argv in (['-n', '-C'], ['-n', '--procfs']):
            args, errors = self.mod.parse_args(argv)
            self.assertNotEmpty(errors)

    def test_args_help(self):
        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            with self.assertRaises(SystemExit):
                self.mod.parse_args(['-h'])
        text = ' '.join(out.getvalue().split())
        self.assertIn('--procfs Legacy option.', text)
        self.assertIn('--netstat Legacy option.', text)
        self.assertNotIn('-n ', text)

    def test_args_all_mode_requires_conntrack(self):
        args, errors = self.mod.parse_args(['-A'])
        self.assertNotEmpty(errors)

    def test_args_bad_filter(self):
        for raw in ['src:tcp/abc', '*:70000', '1.2.3.4:b:c', 'src:']:
            args, errors = self.mod.parse_args([raw])
            self.assertNotEmpty(errors)

    def test_args_source(self):
        Source = self.mod.Source
        tests = [
            ([], Source.NETLINK),
            (['--procfs'], Source.PROCFS),
            (['-S'], Source.PROCFS),
            (['--netstat'], Source.NETSTAT),
            (['-S', '--netstat'], Source.NETSTAT),
            (['-C'], Source.CONNTRACK),
        ]
        for argv, expected in tests:
            self.assertEqual(expected, self.mod.parse_args(argv)[0].source)

    '''
    Filters without a direction apply to the remote side.
    '''
    def test_args_default_target(self):
        self.assertEqual('src', self.mod.parse_args(['tcp/22'])[0].opt_filters[0].target)
        self.assertEqual('dst', self.mod.parse_args(['-o', 'tcp/22'])[0].opt_filters[0].target)

class FilterParsingTests(BaseConnectionsTest):

    '''
    "TCP/" prefixes are case-insensitive and must be stripped from the port.
    '''
    def test_split_filter_tcp_prefix(self):
        self.assertEqual((None, None, '22'), self.mod.split_filter('TCP/22'))
        self.assertEqual((None, '10.0.0.1', '22'), self.mod.split_filter('10.0.0.1:Tcp-22'))
        self.assertEqual(('dst', '10.0.0.1', None), self.mod.split_filter('d:10.0.0.1'))
        self.assertEqual(None, self.mod.split_filter('src:'))

    def test_parse_addresses(self):
        net = ipaddress.IPv4Network
        self.assertEqual([], self.mod.parse_addresses('*'))
        self.assertEqual([net('1.2.3.4/32')], self.mod.parse_addresses('1.2.3.4'))
        self.assertEqual([net('1.2.3.4/32')], self.mod.parse_addresses('1.2.3.4/32'))
        self.assertEqual([net('10.0.0.0/24')], self.mod.parse_addresses('10.0.0.5/24'))

    def test_parse_ports(self):
        ranges, errors = self.mod.parse_ports('x', '22,1000-900,80:81')
        self.assertEmpty(errors)
        self.assertEqual([range(22, 23), range(900, 1001), range(80, 82)], ranges)

    '''
    A source port match must not override a failed destination match.
    '''
    def test_filter_targets_one_side(self):
        connection = self.mod.Connection(
            self.mod.Endpoint(ipaddress.ip_address('20.20.20.20'), 4321),
            self.mod.Endpoint(ipaddress.ip_address('10.11.12.13'), 445),
            self.mod.TcpState.ESTABLISHED)
        user_filter, errors = self.mod.parse_filter('dst:1.2.3.4', True, 'src')
        self.assertFalse(user_filter.matches(connection))
        user_filter, errors = self.mod.parse_filter('src:20.20.20.20:4321', True, 'dst')
        self.assertTrue(user_filter.matches(connection))

class ParserTests(BaseConnectionsTest):

    def test_conntrack(self):
        connection = self.mod.parse_conntrack_line('tcp      6 431951 ESTABLISHED src=10.11.12.13 dst=2.4.6.8 sport=12345 dport=22 src=2.4.6.8 dst=10.11.12.13 sport=22 dport=12345 [ASSURED] mark=0 use=1')
        self.assertEqual('10.11.12.13/12345->2.4.6.8/22', str(connection))

    '''
    The destination of a DNAT-ed connection is the server that replied.
    '''
    def test_conntrack_dnat(self):
        connection = self.mod.parse_conntrack_line('tcp      6 431951 ESTABLISHED src=20.20.20.20 dst=1.2.3.4 sport=40000 dport=80 src=10.11.12.13 dst=20.20.20.20 sport=8080 dport=40000 [ASSURED] mark=0 use=1')
        self.assertEqual('20.20.20.20/40000->10.11.12.13/8080', str(connection))

    '''
    Coverage for the cases where parsing conntrack would fail
    '''
    def test_conntrack_none(self):
        tests = [
            '',
            'udp      6 431951 ESTABLISHED', # Not TCP
            'tcp      6 431951 NOTESTABLISHED', # Unrecognized state
            'tcp      6 431951 ESTABLISHED src=10.11.12.13', # Incomplete
        ]
        for test in tests:
            self.assertEqual(None, self.mod.parse_conntrack_line(test))

    def test_netstat(self):
        connection = self.orient(self.mod.parse_netstat_line('tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED'))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    def test_netstat_tcp6_mapped(self):
        connection = self.orient(self.mod.parse_netstat_line('tcp6       0      0 ::ffff:10.11.12.13:22   ::ffff:20.20.20.20:4321 ESTABLISHED'))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/22', str(connection))

    '''
    Coverage for the cases where parsing netstat would fail
    '''
    def test_netstat_none(self):
        tests = [
            '',
            'nottcp ',
            'udp      6 431951 ESTABLISHED', # Not TCP
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      TIME_WAIT', # Unrecognized state
        ]
        for test in tests:
            self.assertEqual(None, self.mod.parse_netstat_line(test))

    def test_procfs_a(self):
        connection = self.orient(self.mod.parse_procfs_line('0: 0100A8C0:0016 6400A8C0:F106 01'))
        self.assertEqual('192.168.0.100/61702->192.168.0.1/22', str(connection))
        self.assertEqual(self.mod.TcpState.ESTABLISHED, connection.state)

    def test_procfs_b(self):
        connection = self.orient(self.mod.parse_procfs_line('0: 6400A8C0:0016 0100A8C0:F106 01'))
        self.assertEqual('192.168.0.1/61702->192.168.0.100/22', str(connection))

    def test_procfs_c(self):
        connection = self.orient(self.mod.parse_procfs_line('0: 6500A8C0:0011 0a00A8C0:0010 01'))
        self.assertEqual('192.168.0.101/17->192.168.0.10/16', str(connection))

    '''
    IPv4 connections accepted on dual-stack sockets appear in /proc/net/tcp6.
    '''
    def test_procfs_tcp6_mapped(self):
        connection = self.orient(self.mod.parse_procfs_line('0: 0000000000000000FFFF00000A0A0A0A:0016 0000000000000000FFFF000014141414:10E1 01'))
        self.assertEqual('20.20.20.20/4321->10.11.12.13/22', str(connection))

    '''
    Test the various cases where parsing would fail
    '''
    def test_procfs_none(self):
        tests = [
            '',
            'Not a line.',
            '  sl  local_address rem_address   st', # Header
            '0: 6500A8C0:0011 0a00A8C0:0010 03', # Unrecognized state
        ]
        for test in tests:
            self.assertEqual(None, self.mod.parse_procfs_line(test))

class DirectionTests(BaseConnectionsTest):

    def sockets(self, parse, lines):
        return self.mod.connections_from_sockets([parse(l) for l in lines])

    '''
    A service on a high port should be identified from its listening socket.
    '''
    def test_procfs_listener_high_port(self):
        lines = [
            '0: 00000000:C350 00000000:0000 0A',  # Listening on *:50000
            '1: 0A0A0A0A:C350 14141414:9C40 01',  # 10.11.12.13:50000 <- 20.20.20.20:40000
        ]
        connection = self.assertSingle(self.sockets(self.mod.parse_procfs_line, lines))
        self.assertEqual('20.20.20.20/40000->10.11.12.13/50000', str(connection))

    '''
    A connection from a low local port to a remote high port is outgoing
    if the local port is not listening.
    '''
    def test_procfs_listener_outgoing_low_port(self):
        lines = [
            '0: 00000000:0016 00000000:0000 0A',  # Listening on *:22
            '1: 0A0A0A0A:0400 14141414:1F90 01',  # 10.11.12.13:1024 -> 20.20.20.20:8080
        ]
        connection = self.assertSingle(self.sockets(self.mod.parse_procfs_line, lines))
        self.assertEqual('10.11.12.13/1024->20.20.20.20/8080', str(connection))

    def test_procfs_listener_specific_address(self):
        lines = [
            '0: 0A0A0A0A:C350 00000000:0000 0A',  # Listening on 10.11.12.13:50000
            '1: 0A0A0A0A:C350 14141414:9C40 01',  # 10.11.12.13:50000 <- 20.20.20.20:40000
            '2: 0B0A0A0A:C350 14141414:9C41 01',  # 10.11.12.13:50000 -> 20.20.20.20:40001
        ]
        connections = self.sockets(self.mod.parse_procfs_line, lines)
        self.assertEqual(['20.20.20.20/40000->10.11.12.13/50000', '10.11.12.13/50000->20.20.20.20/40001'], [str(c) for c in connections])

    def test_procfs_listener_tcp6_wildcard(self):
        lines = [
            '0: 00000000000000000000000000000000:C350 00000000000000000000000000000000:0000 0A',
            '1: 0000000000000000FFFF00000A0A0A0A:C350 0000000000000000FFFF000014141414:9C40 01',
        ]
        connection = self.assertSingle(self.sockets(self.mod.parse_procfs_line, lines))
        self.assertEqual('20.20.20.20/40000->10.11.12.13/50000', str(connection))

    '''
    SYN_SENT sockets are always connecting out.
    '''
    def test_procfs_syn_sent(self):
        connection = self.orient(self.mod.parse_procfs_line('0: 0A0A0A0A:0016 14141414:9C40 02'))
        self.assertEqual('10.11.12.13/22->20.20.20.20/40000', str(connection))
        self.assertEqual(self.mod.TcpState.SYN_SENT, connection.state)

    def test_netstat_listener(self):
        lines = [
            'tcp6       0      0 :::50000                :::*                    LISTEN',
            'tcp        0      0 10.11.12.13:50000       20.20.20.20:40000       ESTABLISHED',
        ]
        connection = self.assertSingle(self.sockets(self.mod.parse_netstat_line, lines))
        self.assertEqual('20.20.20.20/40000->10.11.12.13/50000', str(connection))

class OutputTests(BaseConnectionsTest):

    def connection(self, src, sport, dst, dport):
        ip = ipaddress.ip_address
        return self.mod.Connection(self.mod.Endpoint(ip(src), sport), self.mod.Endpoint(ip(dst), dport), self.mod.TcpState.ESTABLISHED)

    def capture(self, function, *args):
        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            function(*args)
        return out.getvalue()

    def test_display(self):
        connections = [
            self.connection('30.30.30.30', 4321, '10.11.12.13', 445),
            self.connection('20.20.20.20', 4321, '10.11.12.13', 445),
            self.connection('20.20.20.20', 4322, '10.11.12.13', 445),
        ]
        self.mod.enable_colours(False)
        self.assertEqual([
            '20.20.20.20 -> 10.11.12.13 (tcp/445, 2 connections)',
            '30.30.30.30 -> 10.11.12.13 (tcp/445)',
        ], self.capture(self.mod.display, connections).splitlines())

    def test_display_json(self):
        output = self.capture(self.mod.display_json, [self.connection('20.20.20.20', 4321, '10.11.12.13', 445)])
        self.assertEqual([{
            'src': '20.20.20.20', 'src_port': 4321,
            'dst': '10.11.12.13', 'dst_port': 445,
            'state': 'ESTABLISHED'
        }], json.loads(output))

class SourceTests(BaseConnectionsTest):

    def test_read_command_missing(self):
        with self.assertRaises(self.mod.SourceError):
            self.mod.read_command(['/nonexistent/connections-test-cmd'])

    def test_read_command_failure(self):
        with self.assertRaises(self.mod.SourceError) as ctx:
            self.mod.read_command(['sh', '-c', 'echo denied >&2; exit 3'])
        self.assertIn('denied', str(ctx.exception))
        self.assertIn('3', str(ctx.exception))

    def test_read_command(self):
        self.assertEqual(['a', 'b'], self.mod.read_command(['printf', 'a\\nb\\n']))

    def test_read_procfs(self):
        with tempfile.TemporaryDirectory() as td:
            path_a = os.path.join(td, 'a')
            path_b = os.path.join(td, 'b')
            with open(path_a, 'w') as f:
                f.write('a\n')
            with open(path_b, 'w') as f:
                f.write('b\n')
            self.assertEqual(['a', 'b'], self.mod.read_procfs((path_a, os.path.join(td, 'missing'), path_b)))

            with self.assertRaises(self.mod.SourceError):
                self.mod.read_procfs((os.path.join(td, 'missing'),))

class MainTests(BaseConnectionsTest):

    def main(self, argv, lines, interfaces=None):
        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            exit_code = self.mod.main(argv, self.readers(lines), lambda: interfaces or self.interfaces())
        return exit_code, out.getvalue()

    def test_main(self):
        self.mod.enable_colours(False)
        lines = ['tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED']
        exit_code, output = self.main(['--netstat'], lines)
        self.assertEqual(0, exit_code)
        self.assertEqual('20.20.20.20 -> 10.11.12.13 (tcp/445)\n', output)

    def test_main_json(self):
        lines = ['tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED']
        exit_code, output = self.main(['--netstat', '--json'], lines)
        self.assertEqual(0, exit_code)
        self.assertEqual('20.20.20.20', json.loads(output)[0]['src'])

    def test_main_bad_args(self):
        exit_code, output = self.main(['-n', '-C'], [])
        self.assertEqual(1, exit_code)
        self.assertEqual('', output)

    def test_main_source_error(self):
        def fail():
            raise self.mod.SourceError('nope')
        readers = dict((k, fail) for k in self.mod.READERS)
        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            exit_code = self.mod.main([], readers, self.interfaces)
        self.assertEqual(1, exit_code)
        self.assertEqual('', out.getvalue())

class FakeNetlink:
    '''
    Stands in for socket.socket. Replies to each request with the datagrams
    listed for the request's address family (the first byte of its payload).
    '''
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def __call__(self, family, sock_type, protocol):
        self.protocol = protocol
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def sendto(self, data, address):
        self.requests.append(data)
        response = self.responses[data[16]]
        if isinstance(response, Exception):
            raise response
        self.queue = list(response)

    def recv(self, size):
        return self.queue.pop(0) if self.queue else b''

class NetlinkTestBase(BaseConnectionsTest):

    def diag(self, family, state, src, sport, dst, dport):
        pack = lambda a: ipaddress.ip_address(a).packed.ljust(16, b'\0')
        return self.mod.INET_DIAG_MSG.pack(
            family, state, 0, 0, sport.to_bytes(2, 'big'), dport.to_bytes(2, 'big'),
            pack(src), pack(dst), 0, bytes(8), 0, 0, 0, 1000, 12345)

    def message(self, msg_type, payload, seq=1):
        length = self.mod.NLMSG_HEADER.size + len(payload)
        padding = bytes((4 - length % 4) % 4)
        return self.mod.NLMSG_HEADER.pack(length, msg_type, 2, seq, 0) + payload + padding

    def done(self, code=0):
        return self.message(self.mod.NLMSG_DONE, struct.pack('=i', code))

    def error(self, code):
        # An error carries the request's header after the code.
        return self.message(self.mod.NLMSG_ERROR, struct.pack('=i', code) + bytes(16))

    def sock_diag(self, *args):
        return self.message(self.mod.SOCK_DIAG_BY_FAMILY, self.diag(*args))

    def parse(self, *args):
        return self.mod.parse_inet_diag(self.diag(*args))

class NetlinkTests(NetlinkTestBase):

    def test_parse_inet_diag_ipv4(self):
        connection = self.orient(self.parse(socket.AF_INET, 1, '10.11.12.13', 22, '20.20.20.20', 40000))
        self.assertEqual('20.20.20.20/40000->10.11.12.13/22', str(connection))
        self.assertEqual(self.mod.TcpState.ESTABLISHED, connection.state)

    def test_parse_inet_diag_ipv6_mapped(self):
        connection = self.orient(self.parse(socket.AF_INET6, 1, '::ffff:10.11.12.13', 22, '::ffff:20.20.20.20', 40000))
        self.assertEqual('20.20.20.20/40000->10.11.12.13/22', str(connection))

    def test_parse_inet_diag_listener(self):
        record = self.parse(socket.AF_INET6, 10, '::', 22, '::', 0)
        self.assertEqual(self.mod.TcpState.LISTEN, record.state)
        self.assertEqual('[::]/22', str(record.local))
        self.assertEqual(None, record.remote)

    def test_parse_inet_diag_none(self):
        tests = [
            self.diag(socket.AF_INET, 6, '10.11.12.13', 22, '20.20.20.20', 40000), # TIME_WAIT
            self.diag(socket.AF_UNIX, 1, '10.11.12.13', 22, '20.20.20.20', 40000), # Unknown family
            self.diag(socket.AF_INET, 1, '10.11.12.13', 22, '20.20.20.20', 40000)[:40], # Short
        ]
        for test in tests:
            self.assertEqual(None, self.mod.parse_inet_diag(test))

    '''
    Replies can span several datagrams and messages from other requests are ignored.
    '''
    def test_read_netlink_sockets(self):
        fake = FakeNetlink({
            socket.AF_INET: [
                self.sock_diag(socket.AF_INET, 10, '0.0.0.0', 22, '0.0.0.0', 0)
                + self.sock_diag(socket.AF_INET, 1, '10.11.12.13', 22, '20.20.20.20', 40000),
                self.message(self.mod.SOCK_DIAG_BY_FAMILY, self.diag(socket.AF_INET, 1, '1.1.1.1', 1, '2.2.2.2', 2), seq=99)
                + self.done(),
            ],
            socket.AF_INET6: [
                self.sock_diag(socket.AF_INET6, 1, '::ffff:10.11.12.13', 50000, '::ffff:30.30.30.30', 443)
                + self.done(),
            ],
        })
        records = self.mod.read_netlink_sockets(sock_factory=fake)
        self.assertEqual(self.mod.NETLINK_SOCK_DIAG, fake.protocol)
        self.assertEqual(['0.0.0.0/22', '10.11.12.13/22', '10.11.12.13/50000'], [str(r.local) for r in records])

        # Request: TCP, with the state bitmask for ESTABLISHED, SYN_SENT, and LISTEN
        family, protocol, ext, states = self.mod.INET_DIAG_REQ.unpack_from(fake.requests[0], 16)
        self.assertEqual((socket.AF_INET, socket.IPPROTO_TCP, 0, 0x406), (family, protocol, ext, states))

        connections = self.mod.connections_from_sockets(records)
        self.assertEqual(['20.20.20.20/40000->10.11.12.13/22', '10.11.12.13/50000->30.30.30.30/443'], [str(c) for c in connections])

    def test_read_netlink_sockets_errors(self):
        tests = [
            [self.error(-13)], # EACCES
            [self.done(-16)], # Dump failed
            [self.sock_diag(socket.AF_INET, 1, '10.11.12.13', 22, '20.20.20.20', 40000)[:50]], # Truncated
            [], # Socket closed before the dump finished
        ]
        for datagrams in tests:
            fake = FakeNetlink({socket.AF_INET: datagrams, socket.AF_INET6: [self.done()]})
            with self.assertRaises(OSError):
                self.mod.read_netlink_sockets(sock_factory=fake)

        fake = FakeNetlink({socket.AF_INET: PermissionError(1, 'Operation not permitted')})
        with self.assertRaises(PermissionError):
            self.mod.read_netlink_sockets(sock_factory=fake)

    '''
    IPv6 failures are skipped, like a missing /proc/net/tcp6.
    '''
    def test_read_netlink_sockets_ipv6_unavailable(self):
        fake = FakeNetlink({
            socket.AF_INET: [self.sock_diag(socket.AF_INET, 1, '10.11.12.13', 22, '20.20.20.20', 40000) + self.done()],
            socket.AF_INET6: [self.error(-97)], # EAFNOSUPPORT
        })
        self.assertSingle(self.mod.read_netlink_sockets(sock_factory=fake))

    '''
    An acknowledgement (error code 0) is not an error.
    '''
    def test_netlink_dump_ack(self):
        fake = FakeNetlink({socket.AF_INET: [self.error(0) + self.done()]})
        self.assertEmpty(self.mod.netlink_dump(0, 0, bytes([socket.AF_INET]), fake))

    def test_netlink_unsupported(self):
        with unittest.mock.patch.object(self.mod.socket, 'AF_NETLINK', None, create=True):
            with self.assertRaises(OSError):
                self.mod.read_netlink_sockets(sock_factory=FakeNetlink({}))

    '''
    Live check: a loopback connection shows up with the right direction.
    '''
    def test_read_netlink_sockets_live(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            with socket.create_connection(server.getsockname()) as client:
                accepted, _ = server.accept()
                with accepted:
                    try:
                        records = self.mod.read_netlink_sockets()
                    except OSError as e: # pragma: no cover
                        self.skipTest('Netlink is unavailable: %s' % e)

                    expected = '127.0.0.1/%d->127.0.0.1/%d' % (client.getsockname()[1], server.getsockname()[1])
                    connections = [str(c) for c in self.mod.connections_from_sockets(records)]
                    self.assertIn(expected, connections)

class NetlinkInterfaceTests(NetlinkTestBase):

    def rtattr(self, attr_type, payload):
        length = self.mod.RTATTR.size + len(payload)
        padding = bytes((4 - length % 4) % 4)
        return self.mod.RTATTR.pack(length, attr_type) + payload + padding

    def ifaddr(self, family, prefix_length, index, *attrs):
        return self.mod.IFADDRMSG.pack(family, prefix_length, 0, 0, index) + b''.join(self.rtattr(*a) for a in attrs)

    def ipv4(self, address):
        return ipaddress.ip_address(address).packed

    def test_parse_ifaddrmsg(self):
        payload = self.ifaddr(socket.AF_INET, 24, 999999,
            (self.mod.IFA_ADDRESS, self.ipv4('10.99.0.2')),
            (self.mod.IFA_LOCAL, self.ipv4('10.99.0.2')),
            (self.mod.IFA_LABEL, b'conn-test\0'))
        interface = self.mod.parse_ifaddrmsg(payload)
        self.assertEqual('conn-test', interface.name)
        self.assertEqual(ipaddress.ip_interface('10.99.0.2/24'), interface.address)

    '''
    On point-to-point links, IFA_ADDRESS is the peer and IFA_LOCAL is ours.
    '''
    def test_parse_ifaddrmsg_point_to_point(self):
        payload = self.ifaddr(socket.AF_INET, 32, 999999,
            (self.mod.IFA_ADDRESS, self.ipv4('10.8.0.1')),
            (self.mod.IFA_LOCAL, self.ipv4('10.8.0.2')))
        interface = self.mod.parse_ifaddrmsg(payload)
        self.assertEqual(ipaddress.ip_interface('10.8.0.2/32'), interface.address)
        # No label, and no interface with this index
        self.assertEqual('999999', interface.name)

    def test_parse_ifaddrmsg_none(self):
        tests = [
            self.ifaddr(socket.AF_INET, 24, 1), # No address
            self.ifaddr(socket.AF_INET, 24, 1)[:4], # Short
            self.ifaddr(socket.AF_INET, 24, 1, (self.mod.IFA_LOCAL, b'\x01\x02')), # Malformed address
        ]
        for test in tests:
            self.assertEqual(None, self.mod.parse_ifaddrmsg(test))

    def test_read_netlink_interfaces(self):
        primary = self.ifaddr(socket.AF_INET, 24, 999999, (self.mod.IFA_LOCAL, self.ipv4('10.99.0.1')))
        secondary = self.ifaddr(socket.AF_INET, 24, 999999, (self.mod.IFA_LOCAL, self.ipv4('10.99.0.2')))
        ula = self.ifaddr(socket.AF_INET6, 64, 999999, (self.mod.IFA_ADDRESS, ipaddress.ip_address('fd00:99::1').packed))
        fake = FakeNetlink({socket.AF_UNSPEC: [
            self.message(self.mod.RTM_NEWADDR, primary),
            self.message(self.mod.RTM_NEWADDR, secondary) + self.message(self.mod.RTM_NEWADDR, ula) + self.done(),
        ]})
        interfaces = self.mod.read_netlink_interfaces(sock_factory=fake)
        self.assertEqual(self.mod.NETLINK_ROUTE, fake.protocol)
        self.assertEqual(['10.99.0.1/24', '10.99.0.2/24', 'fd00:99::1/64'], [str(i.address) for i in interfaces])

    def test_get_interfaces_fallback(self):
        fallback = [self.interface('eth0', '10.11.12.13/24')]
        def netlink():
            raise OSError(93, 'Protocol not supported')
        self.assertEqual(fallback, self.mod.get_interfaces(netlink, lambda: fallback))
        self.assertEqual([], self.mod.get_interfaces(lambda: [], lambda: fallback))

    '''
    Live check: the loopback address is found over Netlink.
    '''
    def test_read_netlink_interfaces_live(self):
        try:
            interfaces = self.mod.read_netlink_interfaces()
        except OSError as e: # pragma: no cover
            self.skipTest('Netlink is unavailable: %s' % e)
        self.assertIn(ipaddress.ip_address('127.0.0.1'), [i.ip for i in interfaces])

class IPv6Tests(BaseConnectionsTest):

    def interfaces(self, *extra):
        return super().interfaces(
            self.interface('lo', '::1/128'),
            self.interface('eth0', 'fd00:99::10/64'),
            self.interface('eth0', '2001:db8:1::10/64'),
            self.interface('eth0', 'fe80::10/64'),
            *extra)

    def endpoint(self, ip, port, zone=None):
        return self.mod.Endpoint(ipaddress.ip_address(ip), port, zone)

    def test_endpoint_str(self):
        self.assertEqual('10.0.0.1/22', str(self.endpoint('10.0.0.1', 22)))
        self.assertEqual('[fd00::1]/22', str(self.endpoint('fd00::1', 22)))
        self.assertEqual('[fe80::1%eth0]/22', str(self.endpoint('fe80::1', 22, 'eth0')))
        self.assertEqual('fe80::1%eth0', self.endpoint('fe80::1', 22, 'eth0').host)

    '''
    Zones are only kept for link-local addresses, and mapped addresses become IPv4.
    '''
    def test_make_endpoint(self):
        ip = ipaddress.ip_address
        self.assertEqual(self.endpoint('10.0.0.1', 22), self.mod.make_endpoint(ip('::ffff:10.0.0.1'), 22, 'eth0'))
        self.assertEqual(self.endpoint('fd00::1', 22), self.mod.make_endpoint(ip('fd00::1'), 22, 'eth0'))
        self.assertEqual(self.endpoint('fe80::1', 22, 'eth0'), self.mod.make_endpoint(ip('fe80::1'), 22, 'eth0'))

    def test_split_filter_ipv6(self):
        tests = [
            ('fd00::/8', (None, 'fd00::/8', None)),
            ('fd00:99::1', (None, 'fd00:99::1', None)),
            ('[2001:db8::1]:443', (None, '2001:db8::1', '443')),
            ('[::1]', (None, '::1', None)),
            ('[fd00::/8]:tcp/22,80', (None, 'fd00::/8', '22,80')),
            ('dst:fd00::1', ('dst', 'fd00::1', None)),
            ('src:[fe80::1%eth0]:22', ('src', 'fe80::1%eth0', '22')),
            # Looks like a direction prefix, but is an IPv6 address
            ('d::1', (None, 'd::1', None)),
            ('d:d::1', (None, 'd:d::1', None)), # Also an IPv6 address
            ('d:[d::1]', ('dst', 'd::1', None)),
            ('[::1', None),
        ]
        for raw, expected in tests:
            self.assertEqual(expected, self.mod.split_filter(raw), raw)

    def test_parse_addresses_ipv6(self):
        net = ipaddress.ip_network
        self.assertEqual([net('2001:db8::1/128')], self.mod.parse_addresses('2001:db8::1'))
        self.assertEqual([net('fd00::/8')], self.mod.parse_addresses('fd00::1/8'))
        # Interfaces are ignored
        self.assertEqual([net('fe80::1/128')], self.mod.parse_addresses('fe80::1%eth0'))

        # Not an address, and not a hostname either, so no lookup is made
        with unittest.mock.patch.object(self.mod.socket, 'getaddrinfo') as getaddrinfo:
            self.assertEqual(None, self.mod.parse_addresses('a:b:c'))
            getaddrinfo.assert_not_called()

    def test_parse_addresses_hostname_both_families(self):
        resolved = [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:db8::5', 0, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.5', 0)),
        ]
        with unittest.mock.patch.object(self.mod.socket, 'getaddrinfo', return_value=resolved):
            networks = self.mod.parse_addresses('dual.example')
        self.assertEqual([ipaddress.ip_network('2001:db8::5/128'), ipaddress.ip_network('192.0.2.5/32')], networks)

    def test_procfs_ipv6(self):
        # [2001:db8::10]:22 <- [2001:db8:2::20]:40000
        line = '1: B80D0120000000000000000010000000:0016 B80D0120000002000000000020000000:9C40 01'
        connection = self.orient(self.mod.parse_procfs_line(line))
        self.assertEqual('[2001:db8:2::20]/40000->[2001:db8::10]/22', str(connection))

    def test_netstat_ipv6(self):
        connection = self.orient(self.mod.parse_netstat_line('tcp6       0      0 fe80::10%eth0:22   fe80::20%eth0:40000 ESTABLISHED'))
        self.assertEqual('[fe80::20%eth0]/40000->[fe80::10%eth0]/22', str(connection))
        connection = self.orient(self.mod.parse_netstat_line('tcp6       0      0 fe80::10:22   fe80::20:40000 ESTABLISHED'))
        self.assertEqual('[fe80::20]/40000->[fe80::10]/22', str(connection))

    def test_conntrack_ipv6(self):
        connection = self.mod.parse_conntrack_line('tcp      6 431951 ESTABLISHED src=2001:db8:2::20 dst=2001:db8::10 sport=40000 dport=22 src=2001:db8::10 dst=2001:db8:2::20 sport=22 dport=40000 [ASSURED] mark=0 use=1')
        self.assertEqual('[2001:db8:2::20]/40000->[2001:db8::10]/22', str(connection))

    '''
    A listener with no interface still matches connections that have one.
    '''
    def test_listener_ignores_zone(self):
        Endpoint, SocketRecord, TcpState = self.endpoint, self.mod.SocketRecord, self.mod.TcpState
        records = [
            SocketRecord(TcpState.LISTEN, Endpoint('fe80::10', 50000)),
            SocketRecord(TcpState.ESTABLISHED, Endpoint('fe80::10', 50000, 'eth0'), Endpoint('fe80::20', 60000, 'eth0')),
        ]
        connection = self.assertSingle(self.mod.connections_from_sockets(records))
        self.assertEqual('[fe80::20%eth0]/60000->[fe80::10%eth0]/50000', str(connection))

    def lines(self):
        return [
            'tcp        0      0 10.11.12.13:22          20.20.20.20:40000       ESTABLISHED',
            'tcp6       0      0 fd00:99::10:22          fd00:99::20:40001       ESTABLISHED',
            'tcp6       0      0 2001:db8:1::10:22       2001:db8:2::20:40002    ESTABLISHED',
            'tcp6       0      0 fe80::10%eth0:22        fe80::20%eth0:40003     ESTABLISHED',
            'tcp6       0      0 ::1:22                  ::1:40004               ESTABLISHED',
            'tcp6       0      0 ::ffff:10.11.12.13:22   ::ffff:30.30.30.30:40005 ESTABLISHED',
        ]

    def sources(self, argv):
        return [c.src.host for c in self.run_lines(self.lines(), ['--netstat'] + argv)]

    def test_run_ipv6_incoming(self):
        self.assertEqual(['20.20.20.20', 'fd00:99::20', '2001:db8:2::20', 'fe80::20%eth0', '30.30.30.30'], self.sources([]))

    def test_run_family(self):
        self.assertEqual(['20.20.20.20', '30.30.30.30'], self.sources(['-4']))
        self.assertEqual(['fd00:99::20', '2001:db8:2::20', 'fe80::20%eth0'], self.sources(['-6']))

    def test_run_family_exclusive(self):
        with unittest.mock.patch('sys.stderr', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                self.mod.parse_args(['-4', '-6'])

    def test_run_localhost_ipv6(self):
        self.assertEqual(['::1'], self.sources(['-L', '-6']))

    '''
    Unique local and link-local addresses are LAN addresses by default.
    '''
    def test_run_lan(self):
        self.assertEqual(['fd00:99::20', 'fe80::20%eth0'], self.sources(['-6', '-l']))
        self.assertEqual(['2001:db8:2::20'], self.sources(['-6', '-r']))

    def test_run_lan_interfaces(self):
        lines = ['tcp6       0      0 2001:db8:1::10:22       2001:db8:1::20:40000    ESTABLISHED'] + self.lines()
        sources = [c.src.host for c in self.run_lines(lines, ['--netstat', '-6', '-l', '--lan-interfaces'])]
        self.assertEqual(['2001:db8:1::20', 'fd00:99::20', 'fe80::20%eth0'], sources)

    def test_run_filters(self):
        self.assertEqual(['fd00:99::20'], self.sources(['fd00::/8']))
        self.assertEqual(['2001:db8:2::20'], self.sources(['[2001:db8:2::/48]:40000-40002']))
        self.assertEqual(['20.20.20.20', '30.30.30.30'], self.sources(['-e', '::/0']))
        self.assertEqual(['fd00:99::20', '2001:db8:2::20', 'fe80::20%eth0'], self.sources(['-e', '0.0.0.0/0']))
        # Interfaces in filters are ignored
        self.assertEqual(['fe80::20%eth0'], self.sources(['fe80::20%eth9']))

    def test_run_outgoing_ipv6(self):
        lines = ['tcp6       0      0 2001:db8:1::10:40000    2001:db8:9::1:443       ESTABLISHED']
        connection = self.assertSingle(self.run_lines(lines, ['--netstat', '-o']))
        self.assertEqual('[2001:db8:1::10]/40000->[2001:db8:9::1]/443', str(connection))

    def test_display_mixed(self):
        connections = self.run_lines(self.lines() + [self.lines()[1].replace('40001', '40009')], ['--netstat'])
        self.mod.enable_colours(False)
        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.mod.display(connections)
        self.assertEqual([
            '20.20.20.20 -> 10.11.12.13 (tcp/22)',
            '30.30.30.30 -> 10.11.12.13 (tcp/22)',
            '2001:db8:2::20 -> 2001:db8:1::10 (tcp/22)',
            'fd00:99::20 -> fd00:99::10 (tcp/22, 2 connections)',
            'fe80::20%eth0 -> fe80::10%eth0 (tcp/22)',
        ], out.getvalue().splitlines())

        with unittest.mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            self.mod.display_json(connections)
        records = json.loads(out.getvalue())
        self.assertEqual('fe80::20%eth0', records[-1]['src'])
        self.assertEqual(6, len(records))

class IPv6NetlinkTests(NetlinkTestBase):

    def test_parse_inet_diag_ipv6(self):
        connection = self.orient(self.parse(socket.AF_INET6, 1, '2001:db8::10', 22, '2001:db8:2::20', 40000))
        self.assertEqual('[2001:db8:2::20]/40000->[2001:db8::10]/22', str(connection))

    '''
    The interface index of a link-local socket becomes its zone.
    '''
    def test_parse_inet_diag_link_local(self):
        payload = bytearray(self.diag(socket.AF_INET6, 1, 'fe80::10', 22, 'fe80::20', 40000))
        struct.pack_into('=I', payload, 40, 7) # Interface index
        with unittest.mock.patch.object(self.mod.socket, 'if_indextoname', return_value='eth7'):
            connection = self.orient(self.mod.parse_inet_diag(bytes(payload)))
        self.assertEqual('[fe80::20%eth7]/40000->[fe80::10%eth7]/22', str(connection))

    def test_parse_ifaddrmsg_ipv6(self):
        payload = self.mod.IFADDRMSG.pack(socket.AF_INET6, 64, 0, 0, 999999) + self.mod.RTATTR.pack(20, self.mod.IFA_ADDRESS) + ipaddress.ip_address('fe80::10').packed
        with unittest.mock.patch.object(self.mod.socket, 'if_indextoname', return_value='eth7'):
            interface = self.mod.parse_ifaddrmsg(payload)
        self.assertEqual('eth7', interface.name)
        self.assertEqual(ipaddress.ip_interface('fe80::10/64'), interface.address)

    def test_parse_if_inet6(self):
        interface = self.mod.parse_if_inet6_line('fd000099000000000000000000000001 05 40 00 80  conn-test')
        self.assertEqual('conn-test', interface.name)
        self.assertEqual(ipaddress.ip_interface('fd00:99::1/64'), interface.address)
        self.assertEqual(None, self.mod.parse_if_inet6_line('bad'))
        self.assertEqual(None, self.mod.parse_if_inet6_line('zz 05 40 00 80 eth0'))

    def test_read_if_inet6(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'if_inet6')
            with open(path, 'w') as f:
                f.write('00000000000000000000000000000001 01 80 10 80       lo\n')
            self.assertEqual([ipaddress.ip_interface('::1/128')], [i.address for i in self.mod.read_if_inet6(path)])
            self.assertEqual([], self.mod.read_if_inet6(os.path.join(td, 'missing')))
