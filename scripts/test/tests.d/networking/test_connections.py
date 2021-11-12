#!/usr/bin/env python

import common, unittest # General test requirements

import io, os, tempfile

mod_static = common.load('connections_static', common.TOOLS_DIR + '/scripts/networking/connections.py')

class BaseConnectionsTest(common.TestCase):

    def loadModule(self, override_sources = True):
        self.mod = common.load('connections', common.TOOLS_DIR + '/scripts/networking/connections.py')

    def setUp(self):
        self.loadModule()

class ConnectionsTests(BaseConnectionsTest):

    class MockInterfaceSource(mod_static.InterfaceSource):
        def __init__(self, test_case):
            self.interfaces = {
                'lo': test_case.mod.Interface(name='lo', addr='127.0.0.1', netmask='255.0.0.0')
            }

        def get_interface_names(self):
            return self.interfaces.keys()

        def load_interface(self, name):
            return self.interfaces[name]

    def get_fixtures(self):
        return ConnectionsTests.MockInterfaceSource(self), self.get_mock_sources()

    def get_mock_sources(self):
        class MockSource:
            def __enter__(self):
                return io.StringIO()
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        keys = self.mod.SOURCES.keys()
        sources = {}
        for k in keys:
            sources[k] = MockSource
        return sources

    '''
    Given two connections, filter down to one by dst port range
    '''
    def test_run_filter_dst_port_range(self):

        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:1234      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n', 'src:*:2000-1000']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('30.30.30.30', connection.src.addr)
        self.assertEqual(1234, connection.src.port)

    '''
    Given two connections, show the incoming one.
    '''
    def test_run_filter_incoming(self):

        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:1234        30.30.30.30:445      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('20.20.20.20', connection.src.addr)
        self.assertEqual(4321, connection.src.port)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

    '''
    Given two connections, show the outgoing one.
    '''
    def test_run_filter_outgoing(self):

        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:1234        30.30.30.30:445      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n', '-o']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('30.30.30.30', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('10.11.12.13', connection.src.addr)
        self.assertEqual(1234, connection.src.port)

    '''
    Confirm that localhost connections can be shown using the proper switch.
    '''
    def test_run_filter_localhost(self):

        lines = [
            'tcp        0      0 127.0.0.1:22            127.0.1.1:1122      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n', '-L']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('127.0.0.1', connection.dst.addr)
        self.assertEqual(22, connection.dst.port)

        self.assertEqual('127.0.1.1', connection.src.addr)
        self.assertEqual(1122, connection.src.port)

    '''
    Confirm that localhost connections are normally excluded
    '''
    def test_run_filter_localhost_excluded(self):

        lines = [
            'tcp        0      0 127.0.0.1:22            127.0.1.1:1122      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        self.assertEmpty(connections)

    '''
    Given two connections, filter down to one by source port
    '''
    def test_run_filter_src_port(self):

        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:1234      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n', 'src:tcp/4321']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('20.20.20.20', connection.src.addr)
        self.assertEqual(4321, connection.src.port)

    '''
    Given two connections, filter down to one by excluding a source port
    '''
    def test_run_filter_src_port_exclusion(self):

        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:1234      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n', '-e', 'src:tcp/4321']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('30.30.30.30', connection.src.addr)
        self.assertEqual(1234, connection.src.port)

    '''
    Given two source addresses, filter down to one by address
    '''
    def test_run_filter_src_address(self):

        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:4321      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n', 'src:20.20.20.20']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('20.20.20.20', connection.src.addr)
        self.assertEqual(4321, connection.src.port)

    '''
    Given two source addresses, filter down to one by cidr range
    '''
    def test_run_filter_src_cidr(self):

        lines = [
            'tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED',
            'tcp        0      0 10.11.12.13:445         30.30.30.30:4321      ESTABLISHED'
        ]
        class MockSource:
            def __enter__(self):
                return io.StringIO('\n'.join(lines))
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n', 'src:30.30.30.0/24']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('30.30.30.30', connection.src.addr)
        self.assertEqual(4321, connection.src.port)

    '''
    Basic test of being able to pick up a connection from conntrack.

    Note: This test does not explicitly cover filtering with a red-herring.
    '''
    def test_run_conntrack_basic(self):

        class MockSource:
            def __enter__(self):
                return io.StringIO('tcp      6 431951 ESTABLISHED src=10.11.12.13 dst=2.4.6.8 sport=12345 dport=22 src=2.4.6.8 dst=10.11.12.13 sport=22 dport=12345 [ASSURED] mark=0 use=1')
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='2.4.6.8', netmask='255.255.255.0', broadcast='2.4.6.255')
        sources[self.mod.TYPE_CONNTRACK] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-C']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('2.4.6.8', connection.dst.addr)
        self.assertEqual(22, connection.dst.port)

        self.assertEqual('10.11.12.13', connection.src.addr)
        self.assertEqual(12345, connection.src.port)

        self.assertEqual('10.11.12.13/12345->2.4.6.8/22', str(connection))

    '''
    Basic test of being able to pick up a connection from netstat.

    Note: This test does not explicitly cover filtering with a red-herring.
    '''
    def test_run_netstat_basic(self):

        class MockSource:
            def __enter__(self):
                return io.StringIO('tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED')
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='10.11.12.13', netmask='255.255.255.0', broadcast='10.11.12.13')
        sources[self.mod.TYPE_NETSTAT] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources,
            'args': ['-n']
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('20.20.20.20', connection.src.addr)
        self.assertEqual(4321, connection.src.port)

    '''
    Confirm that the script will not explode given no arguments.
    '''
    def test_run_noargs(self):

        interfaces, sources = self.get_fixtures()
        kwargs = {
            'interface_source': interfaces,
            'sources': sources
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # The only information we need out of this test is 'no connections'
        self.assertEmpty(connections)

    '''
    Basic test of being able to pick up a connection from procfs.

    Note: This test does not explicitly cover filtering with a red-herring.
    '''
    def test_run_procfs_basic(self):

        class MockSource:
            def __enter__(self):
                return io.StringIO('0: 0100A8C0:0016 6400A8C0:F106 01')
            def __exit__(self, exc_type, exc_value, exc_traceback):
                pass

        interfaces, sources = self.get_fixtures()

        interfaces.interfaces['eth0'] = self.mod.Interface(name='eth0', addr='192.168.0.1', netmask='255.255.255.0', broadcast='192.168.0.255')
        sources[self.mod.TYPE_PROCFS] = MockSource

        kwargs = {
            'interface_source': interfaces,
            'sources': sources
        }
        exit_code, connections = self.mod.run(**kwargs)
        self.assertEqual(0, exit_code)
        # Confirm that we were able to get a connection
        connection = self.assertSingle(connections)

        self.assertEqual('192.168.0.1', connection.dst.addr)
        self.assertEqual(22, connection.dst.port)

        self.assertEqual('192.168.0.100', connection.src.addr)
        self.assertEqual(61702, connection.src.port)

class InterfaceTests(BaseConnectionsTest):

    '''
    Confirm various conversions of IPv4 addreses to a number.
    '''
    def test_addr(self):

        tests = [
            ('255.255.255.254', 4294967294),
            ('192.168.0.1', 3232235521),
            ('10.0.0.1', 167772161),
            ('10.0.0.2', 167772162)
        ]
        for value_string, value_num in tests:
            kwargs = { 'addr': value_string }
            interface = self.mod.Interface(**kwargs)
            self.assertEqual(value_string, interface.addr)
            self.assertEqual(value_num, interface.addr_n)

    '''
    Confirm various conversions of IPv4 broadcasts to a number.
    '''
    def test_broadcast(self):

        tests = [
            ('255.255.255.254', 4294967294),
            ('192.168.0.1', 3232235521),
            ('10.0.0.1', 167772161),
            ('10.0.0.2', 167772162)
        ]
        for value_string, value_num in tests:
            kwargs = { 'broadcast': value_string }
            interface = self.mod.Interface(**kwargs)
            self.assertEqual(value_string, interface.broadcast)
            self.assertEqual(value_num, interface.broadcast_n)

    def test_get_max_addrs(self):
        tests = [
            ('255.255.255.0', 254),
            ('255.255.0.0', 65534)
        ]
        for value_string, expected in tests:
            kwargs = { 'netmask': value_string }
            interface = self.mod.Interface(**kwargs)
            self.assertEqual(value_string, interface.netmask)
            self.assertEqual(expected, interface.max_addresses)

    '''
    Confirm setting of interface name
    '''
    def test_name(self):
        tests = [
            'abc',
            '123'
        ]

        for name in tests:

            kwargs = { 'name': name }
            interface = self.mod.Interface(**kwargs)
            self.assertEqual(name, interface.name)

    '''
    Confirm various conversions of IPv4 netmask to a number.
    '''
    def test_netmask(self):

        tests = [
            ('255.255.255.0', 4294967040),
            ('255.255.0.0', 4294901760)
        ]
        for value_string, value_num in tests:
            kwargs = { 'netmask': value_string }
            interface = self.mod.Interface(**kwargs)
            self.assertEqual(value_string, interface.netmask)
            self.assertEqual(value_num, interface.netmask_n)

    '''
    Confirm various conversions of IPv4 netmask to a number.
    '''
    def test_network(self):

        tests = [
            ('192.168.0.52', '255.255.255.0', '192.168.0.0', 3232235520)
        ]
        for addr, netmask, expected_s, expected_n in tests:
            kwargs = { 'addr': addr, 'netmask': netmask }
            interface = self.mod.Interface(**kwargs)
            self.assertEqual(expected_s, interface.network)
            self.assertEqual(expected_n, interface.network_n)

    '''
    Confirm __str__ method output.
    '''
    def test_str(self):
        tests = [
            ('abc', '20.21.22.23', '255.255.255.0', 'abc (20.21.22.23/255.255.255.0)'),
            ('123', '1.2.3.4', '255.255.0.0', '123 (1.2.3.4/255.255.0.0)'),
            ('xyz', '4.3.2.1', '255.0.0.0', 'xyz (4.3.2.1/255.0.0.0)')
        ]

        for name, addr, netmask, expected in tests:

            kwargs = {
                'name': name,
                'addr': addr,
                'netmask': netmask
            }
            interface = self.mod.Interface(**kwargs)
            self.assertEqual(expected, str(interface))

class MiscTests(BaseConnectionsTest):

    def test_main(self):

        data = {'abc': '123'}

        display_stats = {'ran': False}
        def display(connections):
            display_stats['ran'] = True
            display_stats['data'] = connections.copy()
        run_stats = {'ran': False}
        def run(**kwargs):
            run_stats['ran'] = True
            run_stats['data'] = kwargs.copy()

            return 0, data

        # Override module
        self.mod.display = display
        self.mod.run = run

        args = { 'foo': 'bar' }
        exit_code = self.mod.main(**args)
        self.assertTrue(run_stats['ran'])
        self.assertTrue(display_stats['ran'])

        self.assertEqual(args['foo'], run_stats['data']['foo'])
        self.assertEqual(data['abc'], display_stats['data']['abc'])

    def test_main_fail(self):

        data = {}

        display_stats = {'ran': False}
        def display(connections): # pragma: no cover
            # Not expecting this to be run.
            display_stats['ran'] = True
        run_stats = {'ran': False}
        def run(**kwargs):
            run_stats['ran'] = True
            run_stats['data'] = kwargs.copy()

            return 1, data

        # Override module
        self.mod.display = display
        self.mod.run = run

        args = { 'foo': 'bar' }
        exit_code = self.mod.main(**args)
        self.assertTrue(run_stats['ran'])
        self.assertFalse(display_stats['ran'])

        self.assertEqual(args['foo'], run_stats['data']['foo'])

    def test_ConnectionAddress(self):
        tests = [
            ('10.11.12.13', 22, 168496141),
            ('1.2.3.4', 1234, 16909060)
        ]
        for addr, port, number in tests:
            ca = self.mod.ConnectionAddress(tests, addr, port)

            # Confirm that context object is passed through
            self.assertTrue(tests is ca.context)
            # Confirm addr_n
            self.assertEqual(number, ca.addr_n)
            # Confirm __str__
            self.assertEqual('%s/%s' % (addr, port), str(ca))

    def test_SourceProcFS(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'mock')
            contents = 'a'
            with open(path, 'w') as f:
                f.write(contents)

            with self.mod.SourceProcFS(path) as src:
                self.assertEqual(contents, src.readline())

    def test_SourceStandardInput(self):
        contents = 'abc'
        with io.StringIO(contents) as stream:
            with self.mod.SourceStandardInput(stream) as src:
                self.assertEqual(contents, src.readline())

class ParserTests(BaseConnectionsTest):

    def test_conntrack(self):
        parser = self.mod.ParserConntrack(self)

        connection = parser.parse('tcp      6 431951 ESTABLISHED src=10.11.12.13 dst=2.4.6.8 sport=12345 dport=22 src=2.4.6.8 dst=10.11.12.13 sport=22 dport=12345 [ASSURED] mark=0 use=1')
        self.assertNotEqual(None, connection)
        self.assertTrue(self is connection.context)

        self.assertEqual('2.4.6.8', connection.dst.addr)
        self.assertEqual(22, connection.dst.port)

        self.assertEqual('10.11.12.13', connection.src.addr)
        self.assertEqual(12345, connection.src.port)

        self.assertEqual('10.11.12.13/12345->2.4.6.8/22', str(connection))

    '''
    Coverage for the cases where parsing contrack would fail
    '''
    def test_conntrack_none(self):
        parser = self.mod.ParserConntrack(self)

        tests = [
            '',
            'udp      6 431951 ESTABLISHED' # Not TCP
            'tcp      6 431951 NOTESTABLISHED' # Unrecognized state
        ]
        for test in tests:
            connection = parser.parse(test)
            self.assertEqual(None, connection)

    def test_netstat(self):
        parser = self.mod.ParserNetstat(self)

        connection = parser.parse('tcp        0      0 10.11.12.13:445         20.20.20.20:4321      ESTABLISHED')
        self.assertNotEqual(None, connection)
        self.assertTrue(self is connection.context)

        self.assertEqual('10.11.12.13', connection.dst.addr)
        self.assertEqual(445, connection.dst.port)

        self.assertEqual('20.20.20.20', connection.src.addr)
        self.assertEqual(4321, connection.src.port)

        self.assertEqual('20.20.20.20/4321->10.11.12.13/445', str(connection))

    '''
    Coverage for the cases where parsing contrack would fail
    '''
    def test_netstat_none(self):
        parser = self.mod.ParserNetstat(self)

        tests = [
            '',
            'nottcp ',
            'udp      6 431951 ESTABLISHED' # Not TCP
            'tcp      6 431951 NOTESTABLISHED' # Unrecognized state
        ]
        for test in tests:
            connection = parser.parse(test)
            self.assertEqual(None, connection)

    def test_procfs_a(self):
        parser = self.mod.ParserProcFS(self)

        connection = parser.parse('0: 0100A8C0:0016 6400A8C0:F106 01')
        self.assertNotEqual(None, connection)
        self.assertTrue(self is connection.context)

        self.assertEqual('192.168.0.1', connection.dst.addr)
        self.assertEqual(22, connection.dst.port)

        self.assertEqual('192.168.0.100', connection.src.addr)
        self.assertEqual(61702, connection.src.port)

        self.assertEqual('192.168.0.100/61702->192.168.0.1/22', str(connection))

    def test_procfs_b(self):
        parser = self.mod.ParserProcFS(self)

        connection = parser.parse('0: 6400A8C0:0016 0100A8C0:F106 01')
        self.assertNotEqual(None, connection)
        self.assertTrue(self is connection.context)

        self.assertEqual('192.168.0.100', connection.dst.addr)
        self.assertEqual(22, connection.dst.port)

        self.assertEqual('192.168.0.1', connection.src.addr)
        self.assertEqual(61702, connection.src.port)

        self.assertEqual('192.168.0.1/61702->192.168.0.100/22', str(connection))

    def test_procfs_c(self):
        parser = self.mod.ParserProcFS(self)

        connection = parser.parse('0: 6500A8C0:0011 0a00A8C0:0010 01')
        self.assertNotEqual(None, connection)
        self.assertTrue(self is connection.context)

        self.assertEqual('192.168.0.10', connection.dst.addr)
        self.assertEqual(16, connection.dst.port)

        self.assertEqual('192.168.0.101', connection.src.addr)
        self.assertEqual(17, connection.src.port)

        self.assertEqual('192.168.0.101/17->192.168.0.10/16', str(connection))

    '''
    Test the various cases where parsing would fail
    '''
    def test_procfs_none(self):

        parser = self.mod.ParserProcFS(None)

        tests = [
            '',
            'Not a line.'
            '0: 6500A8C0:0011 0a00A8C0:0010 03' # Unrecognized state
        ]
        for test in tests:
            connection = parser.parse(test)
            self.assertEqual(None, connection)
