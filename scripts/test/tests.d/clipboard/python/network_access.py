#!/usr/bin/python

import common, unittest
import os, tempfile

mod = common.load('network_access', common.TOOLS_DIR + '/scripts/clipboard/python/network_access.py')

class NetworkAccessTests(common.TestCase):
    def setUp(self):
        self.access = mod.NetAccess()

    '''
    Confirm that an address is allowed on a NetAccess instance with no loaded rules.
    '''
    def test_allow_simple(self):
        self.assertTrue(self.access.is_allowed('127.0.0.1'))

    '''
    Confirm that an address is allowed on account of not being a blacklisted address.
    '''
    def test_allow_blacklist(self):
        self.access.add_blacklist('10.0.0.1')
        self.assertFalse(self.access.is_allowed('10.0.0.1'))
        self.assertTrue(self.access.is_allowed('10.1.1.1'))

    '''
    Confirm that an address is allowed on account of not being in a blacklisted network.
    '''
    def test_allow_blacklist_network(self):
        self.access.add_blacklist('10.0.0.0/16')
        self.assertTrue(self.access.is_allowed('10.1.1.1'))

    '''
    Confirm that an address is allowed on account of being a whitelisted address.
    '''
    def test_allow_whitelist(self):
        self.access.add_whitelist('10.0.0.1')
        self.assertTrue(self.access.is_allowed('10.0.0.1'))

    '''
    Confirm that an address is allowed on account of being in a whitelisted network network.
    '''
    def test_allow_whitelist_network(self):
        self.access.add_whitelist('10.0.0.0/16')
        self.assertTrue(self.access.is_allowed('10.0.0.1'))
        self.assertTrue(self.access.is_allowed('10.0.254.254'))
        self.assertTrue(self.access.is_allowed('10.0.1.2'))

    '''
    Test block on account of a blacklisted address.
    '''
    def test_block_blacklist(self):

        addr = '127.0.0.1'

        self.access.add_blacklist(addr)
        self.assertFalse(self.access.is_allowed(addr))

    '''
    Test block on account of being in a blacklisted network.
    '''
    def test_block_blacklist_network(self):

        self.access.add_blacklist('10.0.0.0/16')
        self.assertTrue(self.access.is_allowed('9.255.255.254')) # Lower address
        self.assertTrue(self.access.is_allowed('10.1.0.1')) # Higher address
        self.assertFalse(self.access.is_allowed('10.0.0.1')) # Start of range
        self.assertFalse(self.access.is_allowed('10.0.254.254')) # End of range

    '''
    Confirm that blacklisted address takes precedence over a whitelisted network.
    '''
    def test_block_blacklist_precedence_address(self):
        self.access.add_whitelist('10.0.0.0/16')
        self.access.add_blacklist('10.0.0.1')
        self.assertFalse(self.access.is_allowed('10.0.0.1'))
        self.assertTrue(self.access.is_allowed('10.0.0.2'))

    '''
    Confirm that blacklisted network takes precedence over a whitelisted network.
    '''
    def test_block_blacklist_precedence_network(self):
        self.access.add_whitelist('10.0.0.0/16')
        self.access.add_blacklist('10.0.0.0/24')
        self.assertFalse(self.access.is_allowed('10.0.0.1'))
        self.assertTrue(self.access.is_allowed('10.0.1.1'))

    '''
    Test block on account of not being a whitelisted address.
    '''
    def test_block_whitelist(self):

        self.access.add_whitelist('192.168.0.1')
        self.assertFalse(self.access.is_allowed('192.168.0.2'))

    '''
    Test block on account of not being within a whitelisted network.
    '''
    def test_block_whitelist_network(self):

        self.access.add_whitelist('192.168.0.0/24')
        self.assertFalse(self.access.is_allowed('192.168.1.1'))

    '''
    Test block on account of not being within a whitelisted network on a file with a lower address
    '''
    def test_block_whitelist_network_b(self):

        self.access.add_whitelist('192.168.1.0/24')
        self.assertFalse(self.access.is_allowed('192.168.0.255')) # Test an address below the whitelisted range
        self.assertFalse(self.access.is_allowed('192.168.2.0')) # Test an address above the whitelisted range

    '''
    Test behavior of loading a file containing blacklisted addresses.
    '''
    def test_file_blacklist_file(self):
        with tempfile.TemporaryDirectory() as src:
            path = os.path.join(src, 'access-file')
            with open(path, 'w') as f:
                f.write('192.168.0.1\n')
                f.write('192.168.1.0/24\n')

            self.access.load_blacklist_file(path)

            self.assertFalse(self.access.is_allowed('192.168.0.1')) # Test the manual unwanted address
            self.assertFalse(self.access.is_allowed('192.168.1.1')) # Test an unwanted address in the blacklisted CIDR range.
            self.assertTrue(self.access.is_allowed('192.168.0.2')) # Test a not-unwanted field

    '''
    Test behavior of loading a file containing whitelisted addresses.
    '''
    def test_file_whitelist_file(self):
        with tempfile.TemporaryDirectory() as src:
            path = os.path.join(src, 'access-file')
            with open(path, 'w') as f:
                f.write('192.168.0.1\n')
                f.write('192.168.1.0/24\n')

            self.access.load_whitelist_file(path)

            self.assertTrue(self.access.is_allowed('192.168.0.1')) # Test the manual address
            self.assertTrue(self.access.is_allowed('192.168.1.1')) # Test an address in the allowed CIDR range.
            self.assertFalse(self.access.is_allowed('192.168.0.2')) # Test an unwanted field

    '''
    Confirm various conversions of IPv4 addreses to a number.
    '''
    def test_ip_strton(self):

        tests = [
            ('255.255.255.254', 4294967294),
            ('192.168.0.1', 3232235521),
            ('10.0.0.1', 167772161),
            ('10.0.0.2', 167772162)
        ]
        for value_string, value_num in tests:
            self.assertEqual(value_num, self.access.ip_strton(value_string))
