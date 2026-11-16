#!/usr/bin/env python

import common, unittest # General test requirements

import os, signal, socket, subprocess, sys, threading, time

SCRIPT = common.TOOLS_DIR + '/scripts/networking/relay_udp.py'

def free_port(kind):
    s = socket.socket(socket.AF_INET, kind)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

class RelayUdpTunnelTests(common.TestCase):

    def setUp(self):
        self.processes = []

        # UDP echo server for the tunnel server to relay to.
        self.echo = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.echo.bind(('127.0.0.1', 0))
        self.echo.settimeout(0.2)
        self.echo_port = self.echo.getsockname()[1]
        self.echo_running = True
        self.echo_thread = threading.Thread(target=self.run_echo)
        self.echo_thread.start()

        self.udp_port = free_port(socket.SOCK_DGRAM)
        self.tunnel_port = free_port(socket.SOCK_STREAM)

    def tearDown(self):
        for p in self.processes:
            self.stop(p)
        self.echo_running = False
        self.echo_thread.join()
        self.echo.close()

    def run_echo(self):
        while self.echo_running:
            try:
                data, addr = self.echo.recvfrom(65535)
            except socket.timeout:
                continue
            self.echo.sendto(b'echo:' + data, addr)

    def relay(self, *args):
        p = subprocess.Popen([sys.executable, SCRIPT, '-b', '127.0.0.1'] + list(args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(p)
        return p

    def start_server(self):
        return self.relay('--tunnel-server', '--tunnel-port', str(self.tunnel_port), '127.0.0.1:%d' % self.echo_port)

    def start_intake(self, *args):
        return self.relay('--tunnel-intake', '-p', str(self.udp_port), '127.0.0.1:%d' % self.tunnel_port, *args)

    def stop(self, p):
        if p.poll() is None:
            p.send_signal(signal.SIGINT)
            p.wait(5)

    '''
    Send a datagram to the intake, retrying until a reply comes back or time runs out.
    '''
    def ask(self, client, payload, attempts=10):
        client.settimeout(0.5)
        for i in range(attempts):
            client.sendto(payload, ('127.0.0.1', self.udp_port))
            try:
                return client.recvfrom(65535)[0]
            except socket.timeout:
                pass
        return None

    def client(self):
        c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(c.close)
        return c

    '''
    Datagrams make a round trip through the intake, the tunnel, and the tunnel server.
    '''
    def test_round_trip(self):
        self.start_server()
        self.start_intake()
        client = self.client()

        self.assertEqual(b'echo:hello', self.ask(client, b'hello'))
        big = os.urandom(60000)
        self.assertEqual(b'echo:' + big, self.ask(client, big, 1))
        self.assertEqual(b'echo:', self.ask(client, b'', 1))

    '''
    The intake reconnects on its own after the tunnel server restarts.
    '''
    def test_reconnect(self):
        server = self.start_server()
        self.start_intake()
        client = self.client()
        self.assertEqual(b'echo:before', self.ask(client, b'before'))

        self.stop(server)
        self.start_server()
        self.assertEqual(b'echo:after', self.ask(client, b'after'))

    '''
    With lazy reconnection, the datagram that reopens the tunnel is held and delivered.
    '''
    def test_lazy_reconnect(self):
        server = self.start_server()
        self.start_intake('--lazy-reconnect')
        client = self.client()
        self.assertEqual(b'echo:before', self.ask(client, b'before'))

        self.stop(server)
        self.start_server()
        time.sleep(0.5)
        self.assertEqual(b'echo:after', self.ask(client, b'after', 1))
