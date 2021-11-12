#!/usr/bin/env python3

'''
Parse IPv4 TCP connections using /proc/net/tcp, netstat, or conntrack

Revamped version of connections.
'''

import argparse, ctypes, ipaddress, os, platform, re, subprocess, sys
import fcntl, socket, struct

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message, stderr=False): # pragma: no cover
    f=sys.stdout
    if stderr:
        f=sys.stderr
    print('%s[%s]: %s' % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message), file=ff)

def colour_text(text, colour = None): # pragma: no cover
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)

def enable_colours(force = False): # pragma: no cover
    global COLOUR_PURPLE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_PURPLE = '\033[1;35m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_PURPLE = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_BLUE = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

TYPE_CONNTRACK = 'conntrack'
TYPE_NETSTAT = 'netstat'
TYPE_RAW = 'raw'
TYPE_STDIN = 'standard input'
TYPE_PROCFS = 'procfs'

def display(connections):
    connections_s = sorted(connections, key = lambda c: (c.src.addr_n, c.dst.addr_n, c.dst.port))
    counts = {}

    for cid in set([c.identifier for c in connections]):
        counts[cid] = len([1 for c in connections if c.identifier == cid])

    displayed = []
    for c in connections_s:
        args = {
            'src': colour_text(c.src.addr, COLOUR_BLUE),
            'dst': colour_text(c.dst.addr, COLOUR_BLUE),
            'port': c.dst.port,
            'count': ''
        }

        if c.identifier in displayed:
            continue

        displayed.append(c.identifier)

        count = counts[c.identifier]
        if count > 1:
            args['count'] = ', %d connections' % count

        print('%(src)s -> %(dst)s (tcp/%(port)d%(count)s)' % args)


def parse_addr(addr):
    try:
        a = ipaddress.IPv4Address(addr)
        return (str(a), str(a))
    except ValueError:
        return (None, None)

def parse_args(raw_args):

    description_pre = 'Display incoming IPv4 TCP connections parsed from /proc/net/tcp, netstat, or conntrack'
    description_post = '''
Valid filter/exclusion examples:
  "*:22" - Match any address on port 22
  "tcp/22" - Match any address on port 22
  "10.20.30.40:1234" - Match address 10.20.30.40 on port 1234
  "src:10.20.30.40" - Match source address 10.20.30.40
  "dst:40.30.20.10" - Match destination address 40.20.30.10

If no explicit filter direction is given, then the is assumed to be referring to source address in input mode and destination address in outgoing mode.
'''

    parser = argparse.ArgumentParser(description=description_pre, epilog=description_post, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('filter', nargs='*', help='Whitelist filters on output. Conditions must match at least one condition in order to be displayed. Content can be an IP address, CIDR range, or TCP port. TCP ports can be phrased as "tcp/<port>". See below for more details.')

    # Store colour-formatted
    netstat_c = colour_text('netstat', COLOUR_BLUE)
    conntrack_c = colour_text('conntrack', COLOUR_BLUE)

    # General Filters
    parser.add_argument('-e', action='append', default=[], dest='filters_exclusion', help='Exclusion filters. Exclude a particular set of ports/ranges. See below for details.')
    parser.add_argument('--filter-and', action='store_true', dest='filter_and', help='If specified, whitelist filters must all match (as opposed to at least one matching).')
    parser.add_argument('-l', action='store_true', dest='lan', help='LAN Mode. Restrict source addresses (or destination addresses for outgoing mode) to LAN addresses. By default, a LAN address is any address within 10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16. Cancels out -r.')
    parser.add_argument('--lan-interfaces', action='store_true', dest='lan_interfaces', help='When using LAN mode, consider a LAN address to be networks that the machine has an address on.')
    parser.add_argument('-L', action='store_true', dest='allow_localhost', help='Show localhost connections.')
    parser.add_argument('-n', action='store_true', dest='netstat', help='Netstat Mode. Use %s as the source for connection information.' % netstat_c)
    parser.add_argument('-o', action='store_true', dest='outgoing', help='Show outgoing connections instead of incoming connections.')
    parser.add_argument('-r', action='store_true', dest='remote', help='Remote Mode. Restrict source addresses (or destination addresses for outgoing mode) to remote addresses. A remote address is considered to be any non-LAN address. Cancels out -l.')
    parser.add_argument('-S', action='store_true', dest='stdin', help='Expect input from stdin.')

    c_options = parser.add_argument_group('Conntrack Options')
    c_options.add_argument('-C', action='store_true', dest='conntrack', help='Conntrack Mode. Use %s as the source for connection information.' % conntrack_c)
    c_options.add_argument('-A', action='store_true', dest='conntrack_all', help='Conntrack All-Mode: Also show connections passing through the script runner.')
    c_options.add_argument('--no-self', action='store_true', dest='block_self', help='When in Conntrack all-mode, exclude connections involving script runner. When enabled while not in conntrack all-mode, incoming mode bars local addresses from source, outgoing, out going mode bars local addresses from dest.')

    args = parser.parse_args(raw_args)
    errors = []

    if args.conntrack and args.netstat:
        errors.append('Cannot have both %s and %s as sources.' % (netstat_c, conntrack_c))

    if args.conntrack:
        if platform.system() != 'Linux':
            errors.append('%s requires a Linux system.' % conntrack_c)

        # Cannot have allow-localhost AND no -r/-l AND conntrack AND all AND block-self
        if args.allow_localhost and not (args.lan or args.remote) and args.conntrack_all and args.block_self:
            errors.append('Cannot show only localhost addresses in %s mode.' % conntrack_c)
    else:
        # non-conntrack

        if args.conntrack_all:
            errors.append('All-mode specified without conntrack mode.')

    args.opt_filters = []

    # Handle advanced filters

    # Exclusion filters
    for c_filter in args.filters_exclusion or []:
        filter_params, f_errors = parse_filter(c_filter, False)

        if not f_errors:
            args.opt_filters.append(filter_params)

        errors += f_errors

    # Inclusion filters
    for c_filter in args.filter:
        filter_params, f_errors = parse_filter(c_filter, True)

        if not f_errors:
            args.opt_filters.append(filter_params)

        errors += f_errors

    return args, errors

def parse_cidr(cidr):
    try:
        net = ipaddress.ip_network(cidr)
        return (str(net[1]), str(net[-2]))
    except ValueError:
        return (None, None)

def parse_filter(s_filter, allow):

    f_errors = []

    f_success, f_target, f_addr, f_port, f_port_raw = parse_filter_raw(s_filter)

    if not f_success:
        f_errors.append('Invalid filter arg: %s' % s_filter)
        return ((False, None, None, None, None), f_errors)

    if f_addr == '*' or f_addr is None:
        f_addr = '0.0.0.0/0'

    # Attempt to parse address as IP address or domain name.
    f_addr_low = f_addr_high = None

    # Attempt to parse as an IPv4 address
    f_addr_low, f_addr_high = parse_addr(f_addr)
    addresses = [(f_addr_low, f_addr_high)]
    if f_addr_low is None or f_addr_high is None:

        # Address is not a valid IP address.

        # Attempt to parse as a CIDR range
        f_addr_low, f_addr_high = parse_cidr(f_addr)
        addresses = [(f_addr_low, f_addr_high)]

        if f_addr_low is None or f_addr_high is None:
            # So far, address was not an IPv4 address or CIDR range.
            # Try to resolve hostname.
            addresses = parse_hostname(f_addr)
    if not addresses:
        f_errors.append('Could not resolve address: %s' % f_addr)

    # List of tuples to place valid port ranges
    port_ranges = []

    if f_port:
        # Attempt to read port ranges

        # Split up commas
        port_ranges_a = f_port.split(',')
        for pa in port_ranges_a:
            port_ranges_b = re.sub(':', '-', pa).split('-')
            if len(port_ranges_b) > 1:
                low = port_ranges_b[0]
                high = port_ranges_b[-1]
            else:
                low = high = port_ranges_b[0]

            try:
                low = int(low)
                high = int(high)
            except ValueError:
                f_errors.append('Invalid ports in "%s": %s' % (s_filter, pa))
                continue

            if low < 0 or low > 65535 or high < 0 or high > 65535:
                f_errors.append('TCP ports must be within 0-65535: %s' % pa)
                continue

            if low > high:
                sub = high
                high = low
                low = sub

            port_ranges.append((low, high))

    return ((allow, f_target, addresses, port_ranges), f_errors)

def parse_filter_raw(raw):

    parsing = re.search('^((d|dst|s|src):)?([^:]+)(:(.+))?$', raw)

    if not parsing:
        return (False, None, None, None, None)

    if parsing.group(2):
        if parsing.group(2) in ('d', 'dst'):
            target = 'dst'
        else:
            target = 'src'
    else:
        target = None

    addr = parsing.group(3)
    port = port_raw = parsing.group(5)

    # Pattern to match/strip 'tcp/' or 'tcp-'
    pattern_sub = r'^tcp[/\-]+'

    if not port_raw:
        if re.search(pattern_sub, addr, re.IGNORECASE):
            port_raw = addr
            port = re.sub(pattern_sub, '', addr, re.IGNORECASE)
            addr = None
    elif re.search(pattern_sub, port_raw, re.IGNORECASE):
        port = re.sub(pattern_sub, '', port_raw, re.IGNORECASE)

    return (True, target, addr, port, port_raw)

def parse_hostname(addr):
    try:
        name, aliases, values = socket.gethostbyname_ex(addr)
        return [(str(v), str(v)) for v in values]
    except socket.gaierror:
        return []

def to_str(s):

    if type(s) is str:
        return s

    if sys.version_info.major > 2:
        return str(s, 'utf-8')

    return str(s)

class ConnectionContext:

    FLAG_FILTER_INPUT = 0x01
    FLAG_FILTER_OUTPUT = 0x02
    FLAG_ALLOW_LOCALHOST = 0x04
    FLAG_MODE_LAN = 0x08
    FLAG_MODE_REMOTE = 0x10
    FLAG_BLOCK_SELF = 0x20
    FLAG_LAN_INTERFACES = 0x40
    FLAG_FILTER_AND = 0x80

    def __init__(self, **kwargs):

        self.basic_filters = 0x00
        self.filters = []

        # Get interfaces
        self.__parsers = kwargs.get('parsers', PARSERS)
        self.__sources = kwargs.get('sources', SOURCES)

        self.localhost, self.interfaces = kwargs.get('interface_source').get_interfaces()
        self.reset()

    def __is_allowing_localhost(self):

        if self.basic_filters & self.FLAG_ALLOW_LOCALHOST:
            return True

        return False

    def __is_filter_and(self):

        return self.basic_filters & self.FLAG_FILTER_AND > 0

    def __is_filter_input(self):

        return self.basic_filters & self.FLAG_FILTER_INPUT > 0

    def __is_filter_output(self):
        return self.basic_filters & self.FLAG_FILTER_OUTPUT > 0

    def __is_including_self(self):
        return not self.basic_filters & self.FLAG_BLOCK_SELF > 0

    def __is_lan_interfaces(self):
        return self.basic_filters & self.FLAG_LAN_INTERFACES > 0

    def __is_mode_lan(self):
        return self.basic_filters & self.FLAG_MODE_LAN > 0

    def __is_mode_remote(self):
        return self.basic_filters & self.FLAG_MODE_REMOTE > 0

    def append(self, connection):

        matches = list(filter(lambda i: i.src.addr_b == connection.src.addr_b and i.src.port == connection.src.port and i.dst.addr_b == connection.dst.addr_b and i.dst.port == connection.dst.port, self.connections))

        if matches:
            return

        self.connections.append(connection)

    is_allowing_localhost = property(__is_allowing_localhost)
    is_filter_and = property(__is_filter_and)
    is_filter_input = property(__is_filter_input)
    is_filter_output = property(__is_filter_output)
    is_including_self = property(__is_including_self)
    is_lan_interfaces = property(__is_lan_interfaces)
    is_mode_lan = property(__is_mode_lan)
    is_mode_remote = property(__is_mode_remote)

    def reset(self):
        self.connections = []

    def run(self):
        self.connections = [] # Reset connections

        filter_stack = FilterStackAnd()

        '''
            Build filters

            (
                localhost and localhost is allowed
                OR
                (
                    not localhost
                    AND
                    (
                        not allowing localhost OR -r/-l specified
                    )
                    AND
                    Match at least one Directional/General rules OR no such rules are present
                )
            )
            AND
            Match at least one argument-provided narrowing-down OR no such rules are present
                    If a certain switch is specified, then these argument-filters can be an 'AND' instead
                    of an 'OR' which must all be satisfied if any rules exist
        '''

        # Basic filtering. Covers localhost, direction and pre-baked filters like for remote addresses.
        filter_basic = FilterStackOr()
        filter_stack.append(filter_basic) # Immediately add to main stack

        # Localhost filter
        filter_localhost = FilterLocalhost()
        filter_localhost.allow_localhost = self.is_allowing_localhost
        filter_basic.append(filter_localhost)

        # General pre-baked filters
        ###

        filter_general_and = FilterStackAnd()
        filter_general_and.append(FilterNotLocalhost(self))
        filter_general_or = FilterStackOr()
        filter_general_and.append(filter_general_or)
        filter_basic.append(filter_general_and)

        # Gather variables that we shall use for argument-specified variables
        ranges_addresses = [(i.addr_n, i.addr_n) for i in self.interfaces]

        if self.is_lan_interfaces:
            addresses = self.interfaces
        else:
            addresses = []
            for a, n in [('10.0.0.1', '255.0.0.0'), ('172.31.0.1', '255.240.0.0'), ('192.168.0.1', '255.255.0.0')]:
                args = {
                    'addr': a,
                    'netmask': n
                }
                addresses.append(Interface(**args))

        ranges_networks = [(i.network_n + 1, i.network_n + i.max_addresses) for i in addresses]

        mode_lan_raw = self.is_mode_lan
        mode_remote_raw = self.is_mode_remote
        # LAN/Remote filters. These are opposite filters,
        #   so if both of these switches are used then no filter is applied.
        mode_lan = self.is_mode_lan and not self.is_mode_remote
        mode_remote = self.is_mode_remote and not self.is_mode_lan

        # Add basic filters if specified in arguments.

        if self.is_filter_input:
            # Incoming connections must be aimed at one of our addresses

            components = [
                {
                    'dst': ranges_addresses,
                    'allow': True
                }
            ]

            if not self.is_including_self:
                # Block connections coming from our own addresses
                component = {
                    'src': ranges_addresses,
                    'allow': False
                }
                components.append(component)

            if mode_lan:
                # In LAN mode, allow only items coming from local networks
                component = {
                    'src': ranges_networks,
                    'allow': True
                }
                components.append(component)

            if mode_remote:
                # In remote, block items coming from local addresses. Anything not local is remote
                component = {
                    'src': ranges_networks,
                    'allow': False
                }
                components.append(component)
            # Add input filter as a possible branch
            subfilter = FilterGeneral(components=components)
            filter_general_or.append(subfilter)

        if self.is_filter_output:
            # Outgoing connections must originate at one of our addresses
            # The logic of this is the same as incoming logic, only with dst/src flipped.
            # I could rig something up to cut down on code duplication,
            #   but that would take away from code readability.

            components = [
                {
                    'src': ranges_addresses,
                    'allow': True
                }
            ]

            if not self.is_including_self:
                # Block connections going to our own addresses
                component = {
                    'dst': ranges_addresses,
                    'allow': False
                }
                components.append(component)

            if mode_lan:
                # In LAN mode, allow only items going to local networks
                component = {
                    'dst': ranges_networks,
                    'allow': True
                }
                components.append(component)

            if mode_remote:
                # In remote, block items going to local addresss. Anything not local is remote
                component = {
                    'dst': ranges_networks,
                    'allow': False
                }
                components.append(component)
            subfilter = FilterGeneral(components=components)
            filter_general_or.append(subfilter)

        # Advanced filters, provided as arguments
        # Must pass all advanced whitelists and all advanced blacklists
        advanced_filters = FilterStackAnd()
        filter_stack.append(advanced_filters)

        if self.is_filter_and:
            # Require all filter conditions to be met
            advanced_filters_allow = FilterStackAnd()
        else:
            advanced_filters_allow = FilterStackOr()
        advanced_filters.append(advanced_filters_allow)
        advanced_filters_deny = FilterStackAnd()
        advanced_filters.append(advanced_filters_deny)

        for allow, target, addrs, port_ranges in self.filters:

            filter_addr_stack = FilterStackOr()

            for addr_low, addr_high in addrs:
                if target is None:
                    if self.is_filter_output:
                        target = 'dst'
                    else:
                        target = 'src'

                if target == 'dst':
                    target_ports = 'dports'

                if target == 'src':
                    target_ports = 'sports'

                component = {
                    'allow': allow,
                    target_ports: port_ranges
                }

                if addr_low and addr_high:
                    c_low = ConnectionAddress(self, addr_low)
                    c_high = ConnectionAddress(self, addr_high)
                    component[target] = [(c_low.addr_n, c_high.addr_n)]
                c_args = {
                    'components': [
                        component
                    ]
                }

                filter_addr_stack.append(FilterGeneral(**c_args))

            if allow:
                advanced_filters_allow.append(filter_addr_stack)
            else:
                advanced_filters_deny.append(filter_addr_stack)


        # Get parser, prepare for loop
        c_parser = self.__parsers[self.type_parser]

        # Spawn reader
        with self.__sources[self.type_src]() as reader:
            # Spawn parser
            parser = c_parser(self)

            while True:
                line = reader.readline()

                if not line:
                    break

                connection = parser.parse(to_str(line).strip())

                if connection is None:
                    # Not a valid line
                    continue

                if filter_stack.check(connection):
                    self.append(connection)

        return self.connections

    def set_filters(self, filters):
        self.filters = filters

    def set_parser(self, parser):
        self.type_parser = parser

        if parser not in self.__parsers:
            print('Parser not found: ', parser)
            return 1

    def set_src(self, src):
        self.type_src = src

        if src not in self.__sources:
            print('Source not found: ', src)
            return 1

class FilterLocalhost:
    def __init__(self):
        self.__allow_localhost = False

    def __get_allow_localhost(self):
        return self.__allow_localhost

    def __set_allow_localhost(self, value):
        self.__allow_localhost = value

    allow_localhost = property(__get_allow_localhost, __set_allow_localhost)

    def check(self, connection):
        if not connection.is_localhost:
            # Connection does not involve a localhost address
            return False
        # Connection involves a localhost address
        return self.__allow_localhost

class FilterNotLocalhost:
    '''
        not localhost
        AND
        (
            not allowing localhost OR -r/-l specified
        )
    '''

    def __init__(self, context):
        self.context = context

    def check(self, connection):
        if connection.is_localhost:
            return False

        return not self.context.is_allowing_localhost or (self.context.is_mode_lan or self.context.is_mode_remote)

class FilterGeneral:
    def __init__(self, **kwargs):

        self.components = kwargs.get('components')

    def check(self, connection):

        for component in self.components:
            '''
                Block (blacklist):
                    If the component matches, then immediately return False.
                    If the component doesn't match, then continue to next component

                Allow (whitelist)
                    If the component matches, then continue to next component
                    If the component doesn't match, then immediately return False
            '''

            match_dst = True
            match_src = True

            dports = component.get('dports', [])
            dst = component.get('dst', [])

            sports = component.get('sports', [])
            src = component.get('src', [])

            allow = component['allow']

            if dst:
                match_dst = len(list(filter(lambda a: connection.dst.addr_n >= a[0] and connection.dst.addr_n <= a[1], dst))) > 0

            if match_dst and dports:
                match_dst = len(list(filter(lambda p: connection.dst.port >= p[0] and connection.dst.port <= p[1], dports))) > 0

            if src:
                match_src = len(list(filter(lambda a: connection.src.addr_n >= a[0] and connection.src.addr_n <= a[1], src))) > 0

            if match_src and sports:
                match_dst = len(list(filter(lambda p: connection.src.port >= p[0] and connection.src.port <= p[1], sports))) > 0

            match = match_dst and match_src # Shorthand

            if allow and not match:
                # In Allow component: If the component doesn't match, then immediately return False
                return False

            if not allow and match:
                # In Block (not Allow) component: If the component matches, then immediately return False
                return False

        # Either survived all filter condition components, or there were no such components
        return True

class FilterStackAnd:
    # Note: Not just using filter() in order to keep things consistent
    #         with FilterAnd, which to my knowledge does not have a natural python method.
    def __init__(self):
        self.subfilters = []

    def append(self, new_filter):
        self.subfilters.append(new_filter)

    def check(self, connection):
        for item in self.subfilters:
            if not item.check(connection):
                return False
        return True

class FilterStackOr:
    def __init__(self):
        self.subfilters = []

    def append(self, new_filter):
        self.subfilters.append(new_filter)

    def check(self, connection):

        if not self.subfilters:
            # No filters
            return True

        for subfilter in self.subfilters:
            if subfilter.check(connection):
                return True
        return False

class Interface:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name')

        addr = kwargs.get('addr')
        if addr:
            self.addr_b = self.__str_to_bytes(addr)

        broadcast = kwargs.get('broadcast')
        if broadcast:
            self.broadcast_b = self.__str_to_bytes(broadcast)

        netmask = kwargs.get('netmask')
        if netmask:
            self.netmask_b = self.__str_to_bytes(netmask)

    def __convert_n(self, b):
        return (int(b[0]) * 16777216) + (b[1] * 65536) + (b[2] * 256) + b[3]

    def __get_addr_n(self):
        return self.__convert_n(self.addr_b)

    def __get_addr_s(self):
        return socket.inet_ntoa(self.addr_b)

    def __get_broadcast_n(self):
        return self.__convert_n(self.broadcast_b)

    def __get_broadcast_s(self):
        return socket.inet_ntoa(self.broadcast_b)

    def __get_netmask_n(self):
        return self.__convert_n(self.netmask_b)

    def __get_netmask_s(self):
        return socket.inet_ntoa(self.netmask_b)

    def __get_network_b(self):
        r = b''
        for i in range(4):
            r += bytes([((self.addr_b[i]) - ((self.addr_b[i]) & ~int(self.netmask_b[i])))])
        return r

    def __get_network_n(self):
        return self.__convert_n(self.network_b)

    def __get_network_s(self):
        return socket.inet_ntoa(self.network_b)

    def __get_max_addrs(self):
        # Max IPv4 value in int form
        mm = self.__convert_n(bytes([255,255,255,255]))
        return mm & ~self.netmask_n - 1

    def __str__(self):
        return '%s (%s/%s)' % (self.name, self.addr, self.netmask)

    def __str_to_bytes(self, addr_string):
        # Parse IPv4 address strings to byte representations

        s = b''
        for part in addr_string.split('.'):
            s += bytes([int(part)])

        return s

    addr = property(__get_addr_s)
    addr_n = property(__get_addr_n)
    broadcast = property(__get_broadcast_s)
    broadcast_n = property(__get_broadcast_n)
    netmask = property(__get_netmask_s)
    netmask_n = property(__get_netmask_n)
    network = property(__get_network_s)
    network_b = property(__get_network_b)
    network_n = property(__get_network_n)

    max_addresses = property(__get_max_addrs)

class InterfaceSource:
    def get_interfaces(self):
        interfaces = []
        localhost = None
        for ifname in self.get_interface_names():
            try:
                newif = self.load_interface(ifname)

                if ifname == 'lo':
                    # Store localhost as a special case
                    localhost = newif
                else:
                    interfaces.append(newif)
            except OSError as e:
                # An OSError with an errno value of 99 translates to 'Cannot assign requested address'.
                # Translated for context, it means that the interface does not have an address to fetch info on,
                if e.errno != 99:
                    raise

        return localhost, interfaces

    def get_interface_names(self): # pragma: no cover
        return os.listdir('/sys/class/net')

    def load_interface(self, name): # pragma: no cover
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifquery = struct.pack('256s', bytes(name[:15], 'utf-8'))

        kwargs = {}

        kwargs['addr'] = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            ifquery
        )[20:24])

        kwargs['broadcast'] = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8919,  # SIOCGIFBRDADDR
            ifquery
        )[20:24])

        kwargs['netmask'] = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x891b,  # SIOCGIFNETMASK
            ifquery
        )[20:24])

        return Interface(**kwargs)

class Connection:
    def __init__(self, **kwargs):

        self.context = kwargs.get('context')
        a_addr, a_port = kwargs.get('addr_a')
        b_addr, b_port = kwargs.get('addr_b')

        # The side of the connection with the larger port
        #   is assumed to be the origin of the connection.
        if a_port > b_port:
            # Connection is assumed to be from 'A'
            self.src = ConnectionAddress(self, a_addr, a_port)
            self.dst = ConnectionAddress(self, b_addr, b_port)
        else:
            # Connection is assumed to be from 'B'
            self.src = ConnectionAddress(self, b_addr, b_port)
            self.dst = ConnectionAddress(self, a_addr, a_port)

        self.state = kwargs.get('state')
        self.proto = kwargs.get('proto')

    def __get_identifier(self):
        return (self.src.addr_b, self.dst.addr_b, self.dst.port)

    def __get_interfaces(self):
        return self.context.interfaces

    def __is_localhost(self):
        low = self.context.localhost.network_n
        high = self.context.localhost.network_n + self.context.localhost.max_addresses
        if self.src.addr_n > low and self.src.addr_n <= high:
            return True
        return False

    def __str__(self):
        return '%s->%s' % (self.src, self.dst)

    identifier = property(__get_identifier)
    interfaces = property(__get_interfaces)
    is_localhost = property(__is_localhost)

class ConnectionAddress:
    def __init__(self, context, addr, port = None, netmask = '255.255.255.255'):
        self.context = context

        self.addr = addr
        self.addr_b = self.__str_to_bytes(addr)
        self.port = port

    def __get_addr_n(self):
        return (int(self.addr_b[0]) * 16777216) + (self.addr_b[1] * 65536) + (self.addr_b[2] * 256) + self.addr_b[3]

    def __str__(self):
        return '%s/%d' % (self.addr, self.port)

    def __str_to_bytes(self, addr_string):
        # Parse IPv4 address strings to byte representations

        s = b''
        for part in addr_string.split('.'):
            s += bytes([int(part)])

        return s

    addr_n = property(__get_addr_n)

class ParserConntrack:
    def __init__(self, context):
        self.context = context

    def parse(self, line):

        parts = [c for c in line.split(' ') if c]

        if not parts or parts[0] != 'tcp':
            return None

        state = parts[3]
        if state not in ['ESTABLISHED']:
            return None

        values = {}
        for key, value in [(p.split('=')[0], p.split('=')[1]) for p in parts if re.search('^[^=]+=', p)]:
            values[key] = value

        conn_args = {
            'context': self.context,
            'proto': parts[0],
            'addr_a': (values['src'], int(values['sport'])),
            'addr_b': (values['dst'], int(values['dport'])),
            'state': state
        }
        return Connection(**conn_args)

class ParserNetstat:
    def __init__(self, context):
        self.context = context

    def parse(self, line):
        if not line.startswith('tcp '):
            return

        cols = [c for c in line.split(' ') if c]

        state = cols[5]

        if state not in ['ESTABLISHED', 'SYN_SENT']:
            return

        local_parts = cols[3].split(':')
        local_tup = (local_parts[0], int(local_parts[1]))

        remote_parts = cols[4].split(':')
        remote_tup = (remote_parts[0], int(remote_parts[1]))

        conn_args = {
            'context': self.context,
            'proto': cols[0],
            'addr_a': local_tup,
            'addr_b': remote_tup,
            'state': state
        }
        return Connection(**conn_args)

class ParserProcFS:
    def __init__(self, context):
        self.context = context

    def __get_addr_tuple(self, raw):
        parts = raw.split(':')
        return ('%d.%d.%d.%d' % tuple(reversed((int(parts[0][0:2], 16), int(parts[0][2:4], 16), int(parts[0][4:6], 16), int(parts[0][6:8], 16)))), int(parts[1], 16))

    def parse(self, line):
        parts = [l for l in line.split(' ') if l]

        if not parts or not re.match('\d+:', parts[0]):
            return None

        raw_state = parts[3]
        if raw_state not in ['01', '02']:
            # Not in ESTABLISHED or SYN_SENT states
            return None

        tup_local = self.__get_addr_tuple(parts[1])
        tup_remote = self.__get_addr_tuple(parts[2])

        conn_args = {
            'context': self.context,
            'proto': 'tcp',
            'addr_a': tup_local,
            'addr_b': tup_remote,
            'state': raw_state
        }
        return Connection(**conn_args)

class ParserRaw: # pragma: no cover
    # NYI
    def __init__(self, context):
        self.context = context

    def parse(self, line):
        raise Exception('Raw parse NYI')

PARSERS = {
    TYPE_CONNTRACK: ParserConntrack,
    TYPE_NETSTAT: ParserNetstat,
    TYPE_RAW: ParserRaw,
    TYPE_PROCFS: ParserProcFS
}

class SourceCmd: # pragma: no cover
    # Not testing
    def __enter__(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return self.proc.stdout

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.proc.terminate()

class SourceConntrack(SourceCmd):
    cmd = ['conntrack', '-L']

class SourceNetstat(SourceCmd):
    cmd = ['netstat', '-tn']

class SourceProcFS:
    def __init__(self, path = '/proc/net/tcp'):
        self.__path = path

    def __enter__(self):
        self.handle = open(self.__path, 'r')
        self.readline = self.handle.readline
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.handle.close()

class SourceStandardInput:
    def __init__(self, stream = None):
        self.__stream = stream or sys.stdin

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def readline(self):
        return self.__stream.readline()

SOURCES = {
    TYPE_CONNTRACK: SourceConntrack,
    TYPE_NETSTAT: SourceNetstat,
    TYPE_STDIN: SourceStandardInput,
    TYPE_PROCFS: SourceProcFS
}

def main(**kwargs):
    exit_code, connections = run(**kwargs)
    if exit_code == 0:
        display(connections)
    return exit_code

def run(**kwargs):

    parser = src = TYPE_PROCFS

    args, errors = parse_args(kwargs.get('args', []))

    if errors:
        for e in errors:
            print(e)
        return 1, None

    runner = ConnectionContext(**kwargs)

    flags = 0
    if args.allow_localhost:
        flags |= runner.FLAG_ALLOW_LOCALHOST
    if args.lan:
        flags |= runner.FLAG_MODE_LAN
    if args.lan_interfaces:
        flags |= runner.FLAG_LAN_INTERFACES
    if args.remote:
        flags |= runner.FLAG_MODE_REMOTE
    if args.outgoing:
        flags |= runner.FLAG_FILTER_OUTPUT
    else:
        flags |= runner.FLAG_FILTER_INPUT
    if args.block_self:
        flags |= runner.FLAG_BLOCK_SELF

    if args.netstat:
        parser = src = TYPE_NETSTAT
    if args.conntrack:
        parser = src = TYPE_CONNTRACK

    if args.stdin:
        src = TYPE_STDIN

    # Parser/Src
    runner.set_parser(parser)
    runner.set_src(src)
    runner.basic_filters = flags
    runner.set_filters(args.opt_filters)

    connections = runner.run()
    return 0, connections

if __name__ == '__main__': # pragma: no cover
    try:
        exit(main(args=sys.argv[1:], interface_source=InterfaceSource(), parsers=PARSERS, sources=SOURCES))
    except KeyboardInterrupt:
        exit(130)
