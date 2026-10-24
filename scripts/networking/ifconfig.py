#!/usr/bin/env python3

'''
ifconfig substitution script
'''

from os.path import isfile
from re import sub as regex_repl
from sys import argv
import argparse

class InterfaceLinux:
    def __init__(self, path_procnet_dev):
        self.__path_procnet_dev = path_procnet_dev

def do_interface_print(args, path_procnet_dev):

    interfaces = get_interface_stats(path_procnet_dev)
    if args.interface:
        interfaces = {args.interface: interfaces.get(args.interface)}

    for data in interfaces.values():
        if not print_interface(args, data):
            return 1
    return 0

def get_interface_stats(path_procnet_dev):
    '''
    return all interfaces
    '''

    interfaces = {}

    def get_values(line_raw):
        return regex_repl(r':\s', ' ', regex_repl(r'\s+', ' ', line_raw)).strip().split(' ')

    with open(path_procnet_dev, 'r') as handle:

        sections = get_values(handle.readline().replace('|', '')) # Eat first line (header junk)

        header_line = handle.readline()
        headers = []
        for i_section, header_section in enumerate(header_line.split('|')):
            header_values = get_values(header_section)
            for header in header_values:

                headers.append(f'{sections[i_section]}{header}'.replace('|', '').replace('-', '').lower())

        for line in handle:
            current_interface = {}
            for i, value in enumerate(get_values(line)):
                current_interface[headers[i]] = value
            interfaces[current_interface['interface']] = current_interface
    return interfaces

def main(**kwargs):
    args, errors = parse_args(kwargs.get('args'))

    if errors:
        # Problem in parsing args, exit
        for e in errors:
            print(f'Error: {e}')
        exit(1)

    if not args.commands:
        exit_code = do_interface_print(args, kwargs.get('path_procnet_dev'))
        exit(exit_code)

    raise Exception('NYI')

def parse_args(args_raw):
    parser = argparse.ArgumentParser(description='network interface display')

    parser.add_argument('-a', action='store_true', dest='display_all', help='display all interfaces which are currently available, even if down')

    parser.add_argument('interface', nargs='?', help='target interface')
    parser.add_argument('commands', nargs='*', help='commands')

    args = parser.parse_args(args_raw)
    errors = []

    return args, errors

def print_interface(arg, stats):
    interface = stats['interface']
    print(f'{interface}: flags=???<FLAGS NYI> mtu NYI')

    # Cycle through and print IPv4 addresses
    # NYI

    # Cycle through and print IPv6 addresses
    # NYI
    
    # Display hardware address and link information


    def print_packet_line(abbreviation, direction):
        '''
        Print common structure of bytes in/out
        '''
        data_packets = stats.get(f'{direction}packets')
        data_bytes = stats.get(f'{direction}bytes')

        if data_bytes:
            data_bytes_human = int(data_bytes) # Full conversion nyi
        else:
            data_bytes_human = '??'

        print(f'\t{abbreviation} packets {data_packets}  bytes {data_bytes} ({data_bytes_human})')

    print_packet_line('RX', 'receive')

    rx_errors = stats.get(f'receiveerrs')
    rx_dropped = stats.get(f'receivedrop')
    rx_overruns = stats.get(f'receivefifo') # fifo == overrun is unconfirmed, but it is common to rx/tx
    rx_frame = stats.get(f'receiveframe')
    print(f'\tRX errors {rx_errors}  dropped {rx_dropped}  overruns {rx_overruns}  frame {rx_frame}')

    print_packet_line('TX', 'transmit')
    tx_errors = stats.get(f'transmiterrs')
    tx_dropped = stats.get(f'transmitdrop')
    tx_overruns = stats.get(f'transmitfifo') # fifo == overrun is unconfirmed, but it is common to rx/tx
    tx_carrier = stats.get(f'transmitcarrier')
    tx_collisions = stats.get(f'transmitcolls')
    print(f'\tTX errors {tx_errors}  dropped {tx_dropped}  overruns {tx_overruns}  carrier {tx_carrier}  collisions {tx_collisions}')

    return True

if __name__ == '__main__':
    main(args=argv[1:], path_procnet_dev='/proc/net/dev')
