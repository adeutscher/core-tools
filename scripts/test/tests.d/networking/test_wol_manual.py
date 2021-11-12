#!/usr/bin/env python

import common, unittest # General test requirements
import binascii, re, socket

class WoLTests(common.TestCase, metaclass=common.LoggableTestCase):
    def setUp(self):
        self.load_module()

    def confirm_help(self):
        info_messages = self.getLogs('info')
        # Loosely assume that the thing responsible for
        #   so many info printouts is the help output
        self.assertTrue(len(info_messages) > 5)

    def confirm_payload(self, mac, payload):
        # From Wikipedia
        # The magic packet is a broadcast frame containing anywhere within
        #   its payload 6 bytes of all 255 (FF FF FF FF FF FF in hexadecimal),
        #   followed by sixteen repetitions of the target computer's
        #   48-bit MAC address, for a total of 102 bytes.
        self.assertEqual(102, len(payload))
        self.assertEqual(b'\xff\xff\xff\xff\xff\xff', payload[:6])
        for r in range(16):
            self.assertEqual(binascii.unhexlify(bytes(re.sub(':','',mac), 'utf-8')), payload[6 * (r+1):6 * (r+1) + 6])

    def load_module(self, override_send_packet=True):
        self.mod = common.load('wol_manual', common.TOOLS_DIR + '/scripts/networking/wol_manual.py')
        self.mod.logger = common.logging.getLogger(common.LABEL_TEST_LOGGER)

        self.packets = []
        if override_send_packet:
            def send_packet(payload, address):
                addr, port = address
                self.packets.append((payload, addr, port))
            self.mod.send_packet = send_packet

    def test_error_invalid_args(self):
        exit_code = self.mod.run(['--nope'])
        self.assertEqual(1, exit_code)
        error = self.assertSingle(self.getLogs('error'))
        self.assertStartsWith('Error parsing arguments', error)

    def test_error_invalid_mac(self):
        bad_mac = 'aa:bb:cc:dd:ee:fx'
        exit_code = self.mod.run([bad_mac])
        self.assertEqual(1, exit_code)
        error = self.assertSingle(self.getLogs('error'))
        self.assertContains('Invalid MAC address', error)

    def test_error_invalid_addr(self):
        exit_code = self.mod.run(['-a', 'not-an-address', 'aa:bb:cc:dd:ee:ff'])
        self.assertEqual(1, exit_code)
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Not a valid target address: not-an-address', error)
        self.confirm_help()

    def test_error_invalid_port(self):
        exit_code = self.mod.run(['-p', 65536])
        self.assertEqual(1, exit_code)
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('Invalid port number: 65536', error)
        self.confirm_help()

    def test_error_no_macs(self):
        exit_code = self.mod.run([])
        self.assertEqual(1, exit_code)
        error = self.assertSingle(self.getLogs('error'))
        self.assertEqual('No MAC addresses provided.', error)
        self.confirm_help()

    def test_main_run_addr(self):
        mac = 'aa:bb:cc:dd:ee:ff'
        target = '192.168.0.0'
        exit_code = self.mod.run([mac, '-a', target])
        self.assertEqual(0, exit_code)
        payload, addr, port = self.assertSingle(self.packets)
        self.confirm_payload(mac, payload)
        self.assertEqual(target, addr)
        self.assertEqual(40000, port)

    def test_main_run_cidr(self):
        mac = 'aa:bb:cc:dd:ee:ff'
        target = '192.168.0.0'
        exit_code = self.mod.run([mac, '-a', '%s/24' % target])
        self.assertEqual(0, exit_code)
        payload, addr, port = self.assertSingle(self.packets)
        self.confirm_payload(mac, payload)
        self.assertEqual(target, addr)
        self.assertEqual(40000, port)

    def test_main_run_one(self):
        mac = 'aa:bb:cc:dd:ee:ff'
        exit_code = self.mod.run([mac])
        self.assertEqual(0, exit_code)
        payload, addr, port = self.assertSingle(self.packets)

        self.confirm_payload(mac, payload)
        self.assertEqual('255.255.255.255', addr)
        self.assertEqual(40000, port)

    def test_main_run_port(self):
        mac = 'aa:bb:cc:dd:ee:ff'
        exit_code = self.mod.run([mac, '-p', 1234])
        self.assertEqual(0, exit_code)
        payload, addr, port = self.assertSingle(self.packets)

        self.confirm_payload(mac, payload)
        self.assertEqual('255.255.255.255', addr)
        self.assertEqual(1234, port)

    def test_main_run_two(self):
        mac1 = 'aa:bb:cc:11:22:33'
        mac2 = '11:22:33:44:55:66'
        exit_code = self.mod.run([mac1, mac2])
        self.assertEqual(0, exit_code)

        self.assertEqual(2, len(self.packets))

        payload, addr, port = self.packets[0]
        self.confirm_payload(mac1, payload)
        self.assertEqual('255.255.255.255', addr)
        self.assertEqual(40000, port)

        payload, addr, port = self.packets[1]
        self.confirm_payload(mac2, payload)
        self.assertEqual('255.255.255.255', addr)
        self.assertEqual(40000, port)

    def test_help(self):
        exit_code = self.mod.run(['-h'])
        self.assertEqual(0, exit_code)
        self.assertEmpty(self.getLogs('error'))
        self.confirm_help()

    '''
    Confirm default port
    '''
    def test_port(self):
        self.assertEqual(40000, self.mod.DEFAULT_WOL_PORT)

    '''
    Confirm the send_packet function, which we are overriding in every other test.
    '''
    def test_send_packet(self):

        self.load_module(False)

        storage_data = {}
        storage_options = []
        storage_packets = []

        class MockSocket:
            def __init__(self, s_family, s_type):
                storage_data['family'] = s_family
                storage_data['type'] = s_type

            def setsockopt(self, level, option, value):
                storage_options.append((level, option, value))

            def sendto(self, data, address):
                addr, port = address
                storage_packets.append((data, addr, port))

        self.mod.socket_object = MockSocket
        self.mod.send_packet('abc', ('a', 123))

        self.assertEqual(socket.AF_INET, storage_data['family'])
        self.assertEqual(socket.SOCK_DGRAM, storage_data['type'])

        level, option, value = self.assertSingle(storage_options)
        self.assertEqual(socket.SOL_SOCKET, level)
        self.assertEqual(socket.SO_BROADCAST, option)
        self.assertEqual(1, value)



