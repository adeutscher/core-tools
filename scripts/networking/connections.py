#!/usr/bin/env python3

'''
List incoming or outgoing IPv4 TCP connections.

Connections are read from /proc/net/tcp, netstat, or conntrack.
'''

from __future__ import annotations

import argparse, collections, enum, errno, fcntl, functools, ipaddress, json, os
import platform, re, socket, struct, subprocess, sys, typing
from dataclasses import dataclass

#
# Common Colours and Message Functions
###


def _print_message(
    header_colour, header_text, message, stderr=False
):  # pragma: no cover
    f = sys.stdout
    if stderr:
        f = sys.stderr
    print(
        '%s[%s]: %s'
        % (
            colour_text(header_text, header_colour),
            colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN),
            message,
        ),
        file=f,
    )


def colour_text(text, colour=None):  # pragma: no cover
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)


def enable_colours(force=False):  # pragma: no cover
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


def print_error(message):  # pragma: no cover
    _print_message(COLOUR_RED, 'Error', message, True)


def print_warning(message):  # pragma: no cover
    _print_message(COLOUR_YELLOW, 'Warning', message, True)


#
# Types
###


class Source(enum.Enum):
    '''
    Where connection information comes from, and therefore its format.
    '''

    CONNTRACK = 'conntrack'
    NETLINK = 'netlink'
    NETSTAT = 'netstat'
    PROCFS = 'procfs'


# Reader key for standard input, which can hold any text format.
STDIN = 'stdin'


class TcpState(enum.IntEnum):
    '''
    TCP states used by this script, numbered as the kernel numbers them.
    '''

    ESTABLISHED = 1
    SYN_SENT = 2
    LISTEN = 10

    @classmethod
    def from_name(cls, name: str) -> TcpState | None:
        return cls.__members__.get(name)

    @classmethod
    def from_number(cls, number: int) -> TcpState | None:
        try:
            return cls(number)
        except ValueError:
            return None


class SourceError(Exception):
    '''
    Raised when a connection source cannot be read.
    '''


IPAddress = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPInterface = typing.Union[ipaddress.IPv4Interface, ipaddress.IPv6Interface]
IPNetwork = typing.Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


@dataclass(frozen=True)
class Endpoint:
    ip: IPAddress
    port: int
    # Interface name for link-local IPv6 addresses, when known.
    zone: str | None = None

    @property
    def host(self) -> str:
        if self.zone:
            return f'{self.ip}%{self.zone}'
        return str(self.ip)

    @property
    def host_key(self) -> tuple:
        # Sorts IPv4 before IPv6, then by address.
        return (self.ip.version, int(self.ip), self.zone or '')

    def __str__(self) -> str:
        if self.ip.version == 6:
            return f'[{self.host}]/{self.port}'
        return f'{self.host}/{self.port}'


@dataclass(frozen=True)
class Connection:
    src: Endpoint
    dst: Endpoint
    state: TcpState

    @property
    def identifier(self) -> tuple:
        # Connections with the same identifier are grouped in the summary.
        return (self.src.host_key, self.dst.host_key, self.dst.port)

    @property
    def sort_key(self) -> tuple:
        return self.identifier + (self.src.port,)

    @property
    def is_localhost(self) -> bool:
        return self.src.ip.is_loopback

    def __str__(self) -> str:
        return f'{self.src}->{self.dst}'


@dataclass(frozen=True)
class SocketRecord:
    '''
    A socket as seen from this machine.

    Listening sockets have no remote endpoint.
    '''

    state: TcpState
    local: Endpoint
    remote: Endpoint | None = None


@dataclass(frozen=True)
class Interface:
    name: str
    address: IPInterface

    @property
    def ip(self) -> IPAddress:
        return self.address.ip

    @property
    def network(self) -> IPNetwork:
        return self.address.network


@dataclass(frozen=True)
class UserFilter:
    '''
    A filter given on the command line.

    Empty networks or ports match any address or port.
    '''

    allow: bool
    target: str  # 'src' or 'dst'
    networks: tuple[IPNetwork, ...] = ()
    ports: tuple[range, ...] = ()

    def matches(self, connection: Connection) -> bool:
        endpoint = connection.src if self.target == 'src' else connection.dst
        if self.networks and not any(endpoint.ip in n for n in self.networks):
            return False
        return not self.ports or any(endpoint.port in r for r in self.ports)


@dataclass(frozen=True)
class Options:
    outgoing: bool = False
    allow_localhost: bool = False
    lan: bool = False
    remote: bool = False
    lan_interfaces: bool = False
    block_self: bool = False
    filter_and: bool = False
    filters: tuple[UserFilter, ...] = ()
    # Restrict to one IP version (4 or 6), or None for both
    family: int | None = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Options:
        return cls(
            family=args.family,
            outgoing=args.outgoing,
            allow_localhost=args.allow_localhost,
            lan=args.lan,
            remote=args.remote,
            lan_interfaces=args.lan_interfaces,
            block_self=args.block_self,
            filter_and=args.filter_and,
            filters=tuple(args.opt_filters),
        )


# Default definition of a LAN address
LAN_NETWORKS = (
    ipaddress.IPv4Network('10.0.0.0/8'),
    ipaddress.IPv4Network('172.16.0.0/12'),
    ipaddress.IPv4Network('192.168.0.0/16'),
    # Unique local and link-local
    ipaddress.IPv6Network('fc00::/7'),
    ipaddress.IPv6Network('fe80::/10'),
)

#
# Arguments and Filters
###


def parse_args(raw_args: list[str]) -> tuple[argparse.Namespace, list[str]]:

    description_pre = 'Display incoming TCP connections over IPv4 and IPv6. Connections are read from the kernel over Netlink, or from /proc/net/tcp and /proc/net/tcp6 if Netlink is unavailable.'
    description_post = '''
Valid filter/exclusion examples:
  "*:22" - Match any address on port 22
  "tcp/22" - Match any address on port 22
  "10.20.30.40:1234" - Match address 10.20.30.40 on port 1234
  "src:10.20.30.40" - Match source address 10.20.30.40
  "dst:40.30.20.10" - Match destination address 40.30.20.10
  "fd00::/8" - Match IPv6 addresses within fd00::/8
  "[2001:db8::1]:443" - Match address 2001:db8::1 on port 443. IPv6 addresses need brackets when a port is given.

If no explicit filter direction is given, then the filter (including any port) is assumed to be referring to the source in incoming mode and the destination in outgoing mode. For example, use "dst:tcp/22" to match incoming connections to a local service on port 22.

IPv4 connections to dual-stack IPv6 sockets (::ffff:a.b.c.d) are shown as IPv4. Link-local IPv6 addresses are shown with their interface (fe80::1%eth0) when read over Netlink. Interfaces in filters are ignored.

Connection direction is determined from listening sockets when the input includes them (Netlink, procfs, and netstat modes). Otherwise, the side with the higher port is assumed to be the client.
'''

    parser = argparse.ArgumentParser(
        description=description_pre,
        epilog=description_post,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'filter',
        nargs='*',
        help='Whitelist filters on output. Conditions must match at least one condition in order to be displayed. Content can be an IP address, CIDR range, or TCP port. TCP ports can be phrased as "tcp/<port>". See below for more details.',
    )

    # Store colour-formatted
    netstat_c = colour_text('netstat', COLOUR_BLUE)
    conntrack_c = colour_text('conntrack', COLOUR_BLUE)

    # General Filters
    parser.add_argument(
        '-e',
        action='append',
        default=[],
        dest='filters_exclusion',
        help='Exclusion filters. Exclude a particular set of ports/ranges. See below for details.',
    )
    parser.add_argument(
        '--filter-and',
        action='store_true',
        dest='filter_and',
        help='If specified, whitelist filters must all match (as opposed to at least one matching).',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        dest='json',
        help='Print each matching connection as a JSON object instead of a grouped summary.',
    )
    parser.add_argument(
        '-l',
        action='store_true',
        dest='lan',
        help='LAN Mode. Restrict source addresses (or destination addresses for outgoing mode) to LAN addresses. By default, a LAN address is any address within 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7 (unique local), or fe80::/10 (link-local). Cancels out -r.',
    )
    families = parser.add_mutually_exclusive_group()
    families.add_argument(
        '-4',
        action='store_const',
        const=4,
        dest='family',
        help='Only show IPv4 connections, including IPv4 connections to dual-stack IPv6 sockets.',
    )
    families.add_argument(
        '-6',
        action='store_const',
        const=6,
        dest='family',
        help='Only show IPv6 connections.',
    )
    parser.add_argument(
        '--lan-interfaces',
        action='store_true',
        dest='lan_interfaces',
        help='When using LAN mode, consider a LAN address to be networks that the machine has an address on.',
    )
    parser.add_argument(
        '-L',
        action='store_true',
        dest='allow_localhost',
        help='Show localhost connections.',
    )
    # Deprecated alias for --netstat. Kept out of the sources group below
    #   because argparse in Python 3.7 cannot hide members of exclusive groups.
    parser.add_argument(
        '-n', action='store_true', dest='netstat_alias', help=argparse.SUPPRESS
    )
    parser.add_argument(
        '-o',
        action='store_true',
        dest='outgoing',
        help='Show outgoing connections instead of incoming connections.',
    )
    parser.add_argument(
        '-r',
        action='store_true',
        dest='remote',
        help='Remote Mode. Restrict source addresses (or destination addresses for outgoing mode) to remote addresses. A remote address is considered to be any non-LAN address. Cancels out -l.',
    )

    s_options = parser.add_argument_group(
        'Connection Sources',
        'By default, connections are read from the kernel over Netlink.',
    )
    sources = s_options.add_mutually_exclusive_group()
    sources.add_argument(
        '-C',
        action='store_true',
        dest='conntrack',
        help=f'Conntrack Mode. Use {conntrack_c} as the source for connection information.',
    )
    sources.add_argument(
        '--netstat',
        action='store_true',
        dest='netstat',
        help=f'Legacy option. Use {netstat_c} as the source for connection information.',
    )
    sources.add_argument(
        '--procfs',
        action='store_true',
        dest='procfs',
        help='Legacy option. Read connections from /proc/net/tcp and /proc/net/tcp6.',
    )
    s_options.add_argument(
        '-S',
        action='store_true',
        dest='stdin',
        help='Read input from stdin, in /proc/net/tcp format unless --netstat or -C is given.',
    )

    c_options = parser.add_argument_group('Conntrack Options')
    c_options.add_argument(
        '-A',
        action='store_true',
        dest='conntrack_all',
        help='Conntrack All-Mode: Also show connections passing through the script runner.',
    )
    c_options.add_argument(
        '--no-self',
        action='store_true',
        dest='block_self',
        help='When in Conntrack all-mode, exclude connections involving script runner. When enabled while not in conntrack all-mode, incoming mode bars local addresses from source, and outgoing mode bars local addresses from destination.',
    )

    args = parser.parse_args(raw_args)
    errors = []
    args.warnings = []

    if args.netstat_alias:
        args.warnings.append('-n is deprecated. Use --netstat instead.')
        if args.conntrack or args.procfs:
            errors.append('-n cannot be combined with -C or --procfs.')
        args.netstat = True

    if args.conntrack:
        if platform.system() != 'Linux':
            errors.append(f'{conntrack_c} requires a Linux system.')

        # Cannot have allow-localhost AND no -r/-l AND conntrack AND all AND block-self
        if (
            args.allow_localhost
            and not (args.lan or args.remote)
            and args.conntrack_all
            and args.block_self
        ):
            errors.append(
                f'Cannot show only localhost addresses in {conntrack_c} mode.'
            )
    elif args.conntrack_all:
        errors.append('All-mode specified without conntrack mode.')

    if args.conntrack:
        args.source = Source.CONNTRACK
    elif args.netstat:
        args.source = Source.NETSTAT
    elif args.procfs or args.stdin:
        # Standard input defaults to /proc/net/tcp format.
        args.source = Source.PROCFS
    else:
        args.source = Source.NETLINK

    # Filters with no explicit direction apply to the remote side.
    default_target = 'dst' if args.outgoing else 'src'

    args.opt_filters = []
    for allow, raw_filters in ((False, args.filters_exclusion), (True, args.filter)):
        for raw_filter in raw_filters:
            user_filter, f_errors = parse_filter(raw_filter, allow, default_target)
            if user_filter:
                args.opt_filters.append(user_filter)
            errors += f_errors

    return args, errors


# Direction prefix, followed by the rest of the filter
TARGET_PATTERN = re.compile(r'^(?P<target>d|dst|s|src):(?P<rest>.+)$')
# Bracketed IPv6 address or network, with an optional port
BRACKET_PATTERN = re.compile(r'^\[(?P<addr>[^\]]+)\](?::(?P<port>.+))?$')
# Unbracketed IPv6 address or network
BARE_IPV6_PATTERN = re.compile(r'^(?P<addr>[^\[\]]+)$')
# IPv4 address, network, or hostname, with an optional port
ADDR_PORT_PATTERN = re.compile(r'^(?P<addr>[^:]+)(?::(?P<port>.+))?$')
# Matches 'tcp/' or 'tcp-' in front of a port
PORT_PREFIX = re.compile(r'^tcp[/\-]+', re.IGNORECASE)


def parse_network(addr: str) -> IPNetwork | None:
    '''
    Parse an IPv4 or IPv6 address or network. Interfaces (fe80::1%eth0) are ignored.
    '''
    try:
        return ipaddress.ip_network(addr.split('%')[0], strict=False)
    except ValueError:
        return None


def split_filter(raw: str) -> tuple[str | None, str | None, str | None] | None:
    '''
    Split a filter into its target ('src', 'dst', or None), address, and port.

    Returns None if the filter is malformed.
    '''
    target = None
    m = TARGET_PATTERN.match(raw)
    # An IPv6 address such as 'd::1' looks like it has a direction prefix.
    if m and not parse_network(raw):
        target = 'dst' if m.group('target').startswith('d') else 'src'
        raw = m.group('rest')

    if raw.startswith('['):
        pattern = BRACKET_PATTERN
    elif raw.count(':') > 1:
        # A bare IPv6 address or network, which cannot have a port
        pattern = BARE_IPV6_PATTERN
    else:
        pattern = ADDR_PORT_PATTERN

    m = pattern.match(raw)
    if not m:
        return None
    addr, port = m.group('addr'), m.groupdict().get('port')

    if port is None and PORT_PREFIX.match(addr):
        # Port-only filter, like 'tcp/22'
        addr, port = None, addr
    if port is not None:
        port = PORT_PREFIX.sub('', port)

    return target, addr, port


def parse_addresses(addr: str | None) -> list[IPNetwork] | None:
    '''
    Parse an address, CIDR range, or hostname into networks.

    An empty list matches any address. Returns None if a hostname cannot be resolved.
    '''
    if addr is None or addr == '*':
        return []

    network = parse_network(addr)
    if network:
        return [network]

    if ':' in addr:
        # Not a valid IPv6 address, and hostnames cannot contain colons.
        return None

    try:
        results = socket.getaddrinfo(addr, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return None

    networks = []
    for result in results:
        network = parse_network(result[4][0])
        if network and network not in networks:
            networks.append(network)
    return networks or None


def parse_ports(raw_filter: str, ports: str) -> tuple[list[range], list[str]]:
    ranges = []
    errors = []

    for part in ports.split(','):
        bounds = part.replace(':', '-').split('-')
        try:
            low, high = int(bounds[0]), int(bounds[-1])
        except ValueError:
            errors.append(f'Invalid ports in "{raw_filter}": {part}')
            continue

        if not (0 <= low <= 65535 and 0 <= high <= 65535):
            errors.append(f'TCP ports must be within 0-65535: {part}')
            continue

        if low > high:
            low, high = high, low
        ranges.append(range(low, high + 1))

    return ranges, errors


def parse_filter(
    raw_filter: str, allow: bool, default_target: str
) -> tuple[UserFilter | None, list[str]]:

    parts = split_filter(raw_filter)
    if parts is None:
        return None, [f'Invalid filter arg: {raw_filter}']
    target, addr, port = parts

    errors = []

    networks = parse_addresses(addr)
    if networks is None:
        errors.append(f'Could not resolve address: {addr}')

    ranges = []
    if port:
        ranges, port_errors = parse_ports(raw_filter, port)
        errors += port_errors

    if errors:
        return None, errors

    user_filter = UserFilter(
        allow=allow,
        target=target or default_target,
        networks=tuple(networks),
        ports=tuple(ranges),
    )
    return user_filter, []


class ConnectionFilter:
    '''
    Decides which connections to display.
    '''

    def __init__(self, options: Options, interfaces: list[Interface]):
        self.options = options

        interfaces = [i for i in interfaces if not i.ip.is_loopback]
        self.addresses = {i.ip for i in interfaces}
        if options.lan_interfaces:
            self.lan_networks = [i.network for i in interfaces]
        else:
            self.lan_networks = LAN_NETWORKS

        # LAN and remote modes are opposites, so using both cancels them out.
        self.mode_lan = options.lan and not options.remote
        self.mode_remote = options.remote and not options.lan

        self.allow_filters = [f for f in options.filters if f.allow]
        self.deny_filters = [f for f in options.filters if not f.allow]

    def check(self, connection: Connection) -> bool:
        return self.check_basic(connection) and self.check_user(connection)

    def check_basic(self, connection: Connection) -> bool:
        family = self.options.family
        if family and connection.src.ip.version != family:
            return False

        if connection.is_localhost:
            return self.options.allow_localhost

        # Without -l or -r, -L shows only localhost connections.
        if self.options.allow_localhost and not (
            self.options.lan or self.options.remote
        ):
            return False

        return self.check_direction(connection)

    def check_direction(self, connection: Connection) -> bool:
        if self.options.outgoing:
            local, peer = connection.src, connection.dst
        else:
            local, peer = connection.dst, connection.src

        if local.ip not in self.addresses:
            return False
        if self.options.block_self and peer.ip in self.addresses:
            return False
        if self.mode_lan and not self.is_lan(peer.ip):
            return False
        if self.mode_remote and self.is_lan(peer.ip):
            return False
        return True

    def check_user(self, connection: Connection) -> bool:
        if any(f.matches(connection) for f in self.deny_filters):
            return False

        if not self.allow_filters:
            return True

        combine = all if self.options.filter_and else any
        return combine(f.matches(connection) for f in self.allow_filters)

    def is_lan(self, ip: IPAddress) -> bool:
        # Networks of the other IP version never match.
        return any(ip in n for n in self.lan_networks)


#
# Parsers
###


def make_endpoint(ip: IPAddress, port: int, zone: str | None = None) -> Endpoint:
    if ip.version == 6:
        if ip.ipv4_mapped:
            # An IPv4 connection to a dual-stack IPv6 socket (::ffff:a.b.c.d)
            return Endpoint(ip.ipv4_mapped, port)
        if ip.is_link_local:
            return Endpoint(ip, port, zone)
    return Endpoint(ip, port)


def parse_host_port(raw: str) -> tuple:
    '''
    Parse netstat's 'address:port' notation, with an optional %interface.
    '''
    addr, port = raw.rsplit(':', 1)
    addr, _, zone = addr.partition('%')
    return ipaddress.ip_address(addr), int(port), zone or None


def parse_procfs_address(raw: str) -> tuple:
    '''
    Decode an address from /proc/net/tcp or /proc/net/tcp6.

    The kernel prints each 32-bit word of the address in host byte order.
    '''
    addr_hex, port_hex = raw.split(':')
    raw_bytes = bytes.fromhex(addr_hex)
    if sys.byteorder == 'little':
        raw_bytes = b''.join(
            raw_bytes[i : i + 4][::-1] for i in range(0, len(raw_bytes), 4)
        )
    return ipaddress.ip_address(raw_bytes), int(port_hex, 16)


def make_record(state: TcpState, local: tuple, remote) -> SocketRecord:
    '''
    Build a socket record from (ip, port[, zone]) tuples.

    remote is a function returning a tuple, so listeners skip parsing it.
    '''
    if state == TcpState.LISTEN:
        return SocketRecord(state, make_endpoint(*local))
    return SocketRecord(state, make_endpoint(*local), make_endpoint(*remote()))


def parse_procfs_line(line: str) -> SocketRecord | None:
    parts = line.split()
    if len(parts) < 4 or not re.match(r'^\d+:$', parts[0]):
        return None

    try:
        state = TcpState.from_number(int(parts[3], 16))
        if state is None:
            return None
        local = parse_procfs_address(parts[1])
        return make_record(state, local, lambda: parse_procfs_address(parts[2]))
    except ValueError:
        return None


def parse_netstat_line(line: str) -> SocketRecord | None:
    cols = line.split()
    if len(cols) < 6 or cols[0] not in ('tcp', 'tcp6'):
        return None

    state = TcpState.from_name(cols[5])
    if state is None:
        return None

    try:
        local = parse_host_port(cols[3])
        return make_record(state, local, lambda: parse_host_port(cols[4]))
    except ValueError:
        return None


def parse_conntrack_line(line: str) -> Connection | None:
    parts = line.split()

    if len(parts) < 4 or parts[0] != 'tcp' or parts[3] != 'ESTABLISHED':
        return None

    # Each key appears once for the original direction,
    #   then again for the reply direction.
    values = collections.defaultdict(list)
    for part in parts:
        if re.match(r'^[^=]+=', part):
            key, value = part.split('=', 1)
            values[key].append(value)

    try:
        # The original source is the client.
        client = make_endpoint(
            ipaddress.ip_address(values['src'][0]), int(values['sport'][0])
        )
        # The reply source is the server that answered, after any DNAT.
        if len(values['src']) > 1:
            server = (values['src'][1], values['sport'][1])
        else:
            server = (values['dst'][0], values['dport'][0])
        server = make_endpoint(ipaddress.ip_address(server[0]), int(server[1]))
    except (IndexError, ValueError):
        return None

    return Connection(client, server, TcpState.ESTABLISHED)


def connections_from_sockets(records: list[SocketRecord]) -> list[Connection]:
    '''
    Work out which side of each socket started the connection.

    A socket whose local endpoint is listening was connected to from outside.
    '''
    # Listening sockets may not record an interface, so zones are ignored.
    listeners = {
        (r.local.ip, r.local.port) for r in records if r.state == TcpState.LISTEN
    }
    # Wildcard listeners (0.0.0.0 or ::) are treated as covering both families.
    wildcard_ports = {port for ip, port in listeners if ip.is_unspecified}

    connections = []
    for record in records:
        if record.state == TcpState.LISTEN:
            continue

        if record.state == TcpState.SYN_SENT:
            # Still connecting out
            local_is_client = True
        elif listeners:
            local_is_client = not (
                (record.local.ip, record.local.port) in listeners
                or record.local.port in wildcard_ports
            )
        else:
            # No listening sockets to go by. Assume the client has the higher port.
            local_is_client = record.local.port > record.remote.port

        if local_is_client:
            connections.append(Connection(record.local, record.remote, record.state))
        else:
            connections.append(Connection(record.remote, record.local, record.state))

    return connections


def parse_lines(source: Source, lines: list[str]) -> list[Connection]:
    if source == Source.CONNTRACK:
        return [c for c in map(parse_conntrack_line, lines) if c]

    if source == Source.NETSTAT:
        parse = parse_netstat_line
    else:
        parse = parse_procfs_line
    return connections_from_sockets([r for r in map(parse, lines) if r])


#
# Netlink
###


NETLINK_ROUTE = 0
NETLINK_SOCK_DIAG = 4

NLM_F_REQUEST = 0x001
NLM_F_DUMP = 0x300
NLMSG_ERROR = 2
NLMSG_DONE = 3

# Large enough for one datagram of a dump. ss and iproute2 use 32 KiB.
NETLINK_BUFFER_SIZE = 65536

# struct nlmsghdr: length, type, flags, sequence number, port ID
NLMSG_HEADER = struct.Struct('=IHHII')
NLMSG_ERROR_CODE = struct.Struct('=i')

SOCK_DIAG_BY_FAMILY = 20

# struct inet_diag_req_v2, followed by an all-zero struct inet_diag_sockid:
#   family, protocol, extensions, padding, state bitmask
INET_DIAG_REQ = struct.Struct('=BBBxI')
INET_DIAG_SOCKID_SIZE = 48

# struct inet_diag_msg: family, state, timer, retransmits, then the socket ID
#   (ports and addresses in network byte order, interface index, cookie),
#   then expiry, receive queue, send queue, UID, and inode.
INET_DIAG_MSG = struct.Struct('=BBBB2s2s16s16sI8sIIIII')

INET_DIAG_STATES = (
    (1 << TcpState.ESTABLISHED) | (1 << TcpState.SYN_SENT) | (1 << TcpState.LISTEN)
)


def iter_netlink_messages(data: bytes):
    '''
    Yield (type, sequence number, payload) for each message in a datagram.
    '''
    offset = 0
    while offset + NLMSG_HEADER.size <= len(data):
        length, msg_type, _, seq, _ = NLMSG_HEADER.unpack_from(data, offset)
        if length < NLMSG_HEADER.size or offset + length > len(data):
            raise OSError(errno.EBADMSG, 'Truncated Netlink message')

        yield msg_type, seq, data[offset + NLMSG_HEADER.size : offset + length]
        # Messages are aligned to 4 bytes.
        offset += (length + 3) & ~3


def netlink_error(payload: bytes) -> OSError | None:
    # Errors are reported as a negative errno. Zero is an acknowledgement.
    if len(payload) < NLMSG_ERROR_CODE.size:
        return None
    code = -NLMSG_ERROR_CODE.unpack_from(payload)[0]
    if code <= 0:
        return None
    return OSError(code, os.strerror(code))


def netlink_dump(
    protocol: int, msg_type: int, payload: bytes, sock_factory=socket.socket
) -> list[tuple[int, bytes]]:
    '''
    Send a Netlink dump request, returning (type, payload) for each reply.

    Raises OSError if Netlink is unavailable or the kernel reports an error.
    '''
    family = getattr(socket, 'AF_NETLINK', None)
    if family is None:
        raise OSError(errno.EAFNOSUPPORT, 'Netlink is not supported on this system')

    seq = 1
    header = NLMSG_HEADER.pack(
        NLMSG_HEADER.size + len(payload), msg_type, NLM_F_REQUEST | NLM_F_DUMP, seq, 0
    )

    replies = []
    with sock_factory(family, socket.SOCK_RAW, protocol) as s:
        s.sendto(header + payload, (0, 0))

        while True:
            data = s.recv(NETLINK_BUFFER_SIZE)
            if not data:
                raise OSError(errno.EIO, 'Netlink dump ended early')

            for reply_type, reply_seq, reply in iter_netlink_messages(data):
                if reply_seq != seq:
                    continue

                if reply_type in (NLMSG_ERROR, NLMSG_DONE):
                    error = netlink_error(reply)
                    if error:
                        raise error
                    if reply_type == NLMSG_DONE:
                        return replies
                    continue

                replies.append((reply_type, reply))


def parse_inet_diag(payload: bytes) -> SocketRecord | None:
    if len(payload) < INET_DIAG_MSG.size:
        return None

    fields = INET_DIAG_MSG.unpack_from(payload)
    family, state, _, _, sport, dport, src, dst, index = fields[:9]

    state = TcpState.from_number(state)
    if state is None:
        return None

    if family == socket.AF_INET:
        size = 4
    elif family == socket.AF_INET6:
        size = 16
    else:
        return None

    # Sockets on link-local addresses are bound to an interface.
    zone = interface_name(index) if index else None

    local = (ipaddress.ip_address(src[:size]), int.from_bytes(sport, 'big'), zone)
    remote = (ipaddress.ip_address(dst[:size]), int.from_bytes(dport, 'big'), zone)
    return make_record(state, local, lambda: remote)


def read_netlink_sockets(
    families: tuple[int, ...] = (socket.AF_INET, socket.AF_INET6),
    sock_factory=socket.socket,
) -> list[SocketRecord]:
    '''
    Dump TCP sockets with the kernel's sock_diag interface.

    Raises OSError if IPv4 sockets cannot be dumped.
    '''
    records = []
    for family in families:
        request = INET_DIAG_REQ.pack(
            family, socket.IPPROTO_TCP, 0, INET_DIAG_STATES
        ) + bytes(INET_DIAG_SOCKID_SIZE)

        try:
            replies = netlink_dump(
                NETLINK_SOCK_DIAG, SOCK_DIAG_BY_FAMILY, request, sock_factory
            )
        except OSError:
            if family == socket.AF_INET:
                raise
            # IPv6 may be disabled. procfs skips a missing tcp6 the same way.
            continue

        for reply_type, reply in replies:
            if reply_type == SOCK_DIAG_BY_FAMILY:
                record = parse_inet_diag(reply)
                if record:
                    records.append(record)

    return records


#
# Sources
###


PROCFS_PATHS = ('/proc/net/tcp', '/proc/net/tcp6')


def read_command(cmd: list[str]) -> list[str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise SourceError(f'Command not found: {cmd[0]}')

    if proc.returncode:
        raise SourceError(
            f'"{" ".join(cmd)}" exited with code {proc.returncode}: {proc.stderr.strip()}'
        )

    return proc.stdout.splitlines()


def read_procfs(paths: tuple[str, ...] = PROCFS_PATHS) -> list[str]:
    # Missing files are skipped (e.g. tcp6 when IPv6 is disabled),
    #   but at least one file must be readable.
    lines = []
    errors = []
    for path in paths:
        try:
            with open(path, 'r') as f:
                lines += f.read().splitlines()
        except OSError as e:
            errors.append(e)

    if len(errors) == len(paths):
        raise SourceError(f'Unable to read {paths[0]}: {errors[0]}')
    return lines


def read_stdin() -> list[str]:  # pragma: no cover
    return sys.stdin.read().splitlines()


READERS = {
    Source.CONNTRACK: functools.partial(read_command, ['conntrack', '-L']),
    Source.NETLINK: read_netlink_sockets,
    # -a for listening sockets, -W to avoid truncating IPv4-mapped addresses.
    Source.NETSTAT: functools.partial(read_command, ['netstat', '-tanW']),
    Source.PROCFS: read_procfs,
    STDIN: read_stdin,
}

#
# Interfaces
###


RTM_NEWADDR = 20
RTM_GETADDR = 22

# struct ifaddrmsg: family, prefix length, flags, scope, interface index
IFADDRMSG = struct.Struct('=BBBBI')
# struct rtattr: length, type
RTATTR = struct.Struct('=HH')
IFA_ADDRESS = 1
IFA_LOCAL = 2
IFA_LABEL = 3

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891B


def iter_rtattrs(data: bytes, offset: int):
    '''
    Yield (type, payload) for each route attribute from offset onwards.
    '''
    while offset + RTATTR.size <= len(data):
        length, attr_type = RTATTR.unpack_from(data, offset)
        if length < RTATTR.size:
            return
        yield attr_type, data[offset + RTATTR.size : offset + length]
        # Attributes are aligned to 4 bytes.
        offset += (length + 3) & ~3


def interface_name(index: int, label: bytes | None = None) -> str:
    if label:
        return label.rstrip(b'\0').decode('utf-8', 'replace')
    try:
        return socket.if_indextoname(index)
    except OSError:
        return str(index)


def parse_ifaddrmsg(payload: bytes) -> Interface | None:
    if len(payload) < IFADDRMSG.size:
        return None

    family, prefix_length, _, _, index = IFADDRMSG.unpack_from(payload)
    if family not in (socket.AF_INET, socket.AF_INET6):
        return None

    attrs = dict(iter_rtattrs(payload, IFADDRMSG.size))

    # IFA_LOCAL is the local address. IFA_ADDRESS is the peer address on
    #   point-to-point links, and the same as IFA_LOCAL otherwise.
    raw = attrs.get(IFA_LOCAL) or attrs.get(IFA_ADDRESS)
    if raw is None:
        return None

    try:
        ip = ipaddress.ip_address(raw)
        address = ipaddress.ip_interface(f'{ip}/{prefix_length}')
    except ValueError:
        return None
    return Interface(interface_name(index, attrs.get(IFA_LABEL)), address)


def read_netlink_interfaces(sock_factory=socket.socket) -> list[Interface]:
    '''
    Dump every address on every interface, including secondary addresses.

    Raises OSError if Netlink is unavailable.
    '''
    # AF_UNSPEC requests both IPv4 and IPv6 addresses.
    request = IFADDRMSG.pack(socket.AF_UNSPEC, 0, 0, 0, 0)
    replies = netlink_dump(NETLINK_ROUTE, RTM_GETADDR, request, sock_factory)

    interfaces = []
    for reply_type, reply in replies:
        if reply_type == RTM_NEWADDR:
            interface = parse_ifaddrmsg(reply)
            if interface:
                interfaces.append(interface)
    return interfaces


def get_interfaces(netlink=read_netlink_interfaces, fallback=None) -> list[Interface]:
    try:
        return netlink()
    except OSError:
        return (fallback or read_fallback_interfaces)()


def read_fallback_interfaces() -> list[Interface]:  # pragma: no cover
    '''
    Find addresses without Netlink.

    ioctl only sees each interface's primary IPv4 address.
    IPv6 addresses are read from /proc/net/if_inet6.
    '''
    return read_ioctl_interfaces() + read_if_inet6()


def parse_if_inet6_line(line: str) -> Interface | None:
    '''
    Parse a line of /proc/net/if_inet6:
      address (hex, network byte order), index, prefix length, scope, flags, name
    '''
    parts = line.split()
    if len(parts) < 6:
        return None
    try:
        ip = ipaddress.IPv6Address(bytes.fromhex(parts[0]))
        prefix_length = int(parts[2], 16)
    except ValueError:
        return None
    return Interface(parts[5], ipaddress.IPv6Interface(f'{ip}/{prefix_length}'))


def read_if_inet6(path: str = '/proc/net/if_inet6') -> list[Interface]:
    try:
        with open(path, 'r') as f:
            lines = f.read().splitlines()
    except OSError:
        # IPv6 is disabled.
        return []
    return [i for i in map(parse_if_inet6_line, lines) if i]


def read_ioctl_interfaces() -> list[Interface]:  # pragma: no cover
    interfaces = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for name in sorted(os.listdir('/sys/class/net')):
            try:
                addr = _ioctl_address(s, SIOCGIFADDR, name)
                netmask = _ioctl_address(s, SIOCGIFNETMASK, name)
            except OSError as e:
                # The interface has no IPv4 address.
                if e.errno != errno.EADDRNOTAVAIL:
                    raise
                continue
            interfaces.append(
                Interface(name, ipaddress.IPv4Interface(f'{addr}/{netmask}'))
            )
    return interfaces


def _ioctl_address(
    s: socket.socket, request: int, name: str
) -> str:  # pragma: no cover
    ifquery = struct.pack('256s', name[:15].encode('utf-8'))
    return socket.inet_ntoa(fcntl.ioctl(s.fileno(), request, ifquery)[20:24])


#
# Output
###


def display(connections: list[Connection]):
    groups = collections.defaultdict(list)
    for connection in connections:
        groups[connection.identifier].append(connection)

    for identifier in sorted(groups):
        group = groups[identifier]
        src, dst = group[0].src, group[0].dst
        suffix = f', {len(group)} connections' if len(group) > 1 else ''
        print(
            f'{colour_text(src.host, COLOUR_BLUE)} -> {colour_text(dst.host, COLOUR_BLUE)} (tcp/{dst.port}{suffix})'
        )


def display_json(connections: list[Connection]):
    connections = sorted(connections, key=lambda c: c.sort_key)
    records = [
        {
            'src': c.src.host,
            'src_port': c.src.port,
            'dst': c.dst.host,
            'dst_port': c.dst.port,
            'state': c.state.name,
        }
        for c in connections
    ]
    print(json.dumps(records, indent=2))


#
# Main
###


def read_connections(args: argparse.Namespace, readers) -> list[Connection]:
    if args.stdin:
        return parse_lines(args.source, readers[STDIN]())

    if args.source == Source.NETLINK:
        try:
            records = readers[Source.NETLINK]()
        except OSError:
            # Netlink is unavailable, so quietly fall back to procfs.
            return parse_lines(Source.PROCFS, readers[Source.PROCFS]())
        return connections_from_sockets(records)

    return parse_lines(args.source, readers[args.source]())


def collect(
    args: argparse.Namespace, readers=None, interface_source=None
) -> list[Connection]:
    '''
    Read, filter, and de-duplicate connections.

    Raises SourceError if the source cannot be read.
    '''
    readers = readers or READERS
    interface_source = interface_source or get_interfaces

    connections = read_connections(args, readers)
    connection_filter = ConnectionFilter(Options.from_args(args), interface_source())

    # De-duplicate, keeping the first copy of each connection.
    unique = {}
    for connection in connections:
        if connection_filter.check(connection):
            unique.setdefault((connection.src, connection.dst), connection)
    return list(unique.values())


def main(argv: list[str] | None = None, readers=None, interface_source=None) -> int:
    args, errors = parse_args(sys.argv[1:] if argv is None else argv)
    for warning in args.warnings:
        print_warning(warning)
    if errors:
        for e in errors:
            print_error(e)
        return 1

    try:
        connections = collect(args, readers, interface_source)
    except SourceError as e:
        print_error(e)
        return 1

    if args.json:
        display_json(connections)
    else:
        display(connections)
    return 0


if __name__ == '__main__':  # pragma: no cover
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
