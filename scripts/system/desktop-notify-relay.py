#!/usr/bin/python

'''
    This is a super-silly server made play desktop notifications from a remote server.
    Client notifications are sent over TCP or UDP (use -u switch to switch to UDP),
    and the server presents the first line received.
    For access control options, see the help menu (-h).

    Note: I have not experimented desktop environments other than MATE. If your desktop environment
          does not have the 'nofify-send' command, then this script will need some adaptation.
'''

import getopt, os, re, socket, struct, subprocess, sys, thread, time

DEFAULT_RELAY_PORT = 1234

def enable_colours(force = False):
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

#
# Common Message Functions
###

def print_denied(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_RED, "Denied", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_error(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_RED, "Error", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

def print_notice(message):
    print "%s%s%s[%s%s%s]: %s" % (COLOUR_BLUE, "Notice", COLOUR_OFF, COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF, message)

class NetAccess:
    # Basic IPv4 CIDR syntax check
    REGEX_INET4_CIDR='^(([0-9]){1,3}\.){3}([0-9]{1,3})\/[0-9]{1,2}$'

    def __init__(self):
        self.errors = []
        self.allowed_addresses = []
        self.allowed_networks = []
        self.denied_addresses = []
        self.denied_networks = []

    def add_access(self, addr_list, net_list, candidate):
        error = False
        candidate = candidate.strip()
        if re.match(self.REGEX_INET4_CIDR, candidate):
            e, n = self.ip_validate_cidr(candidate)
            error = e
            if not e:
                # No error
                net_list.append((n, candidate))
        else:
            e, a, astr = self.ip_validate_address(candidate)
            error = e
            if not e:
                # No error
                addr_list.append((a, candidate, astr))
        return error

    def add_blacklist(self, candidate):
        return self.add_access(self.denied_addresses, self.denied_networks, candidate)

    def add_whitelist(self, candidate):
        return self.add_access(self.allowed_addresses, self.allowed_networks, candidate)

    def announce_filter_actions(self):
        for action, address_list, network_list in [("Allowing", self.allowed_addresses, self.allowed_networks), ("Denying", self.denied_addresses, self.denied_networks)]:
            l = []
            l.extend([("address", s, i) for n, s, i in address_list])
            l.extend([("network", s, s) for n, s in network_list])

            for title, ip, address in l:
                if ip == address:
                    print_notice("%s %s: %s%s%s" % (action, title, COLOUR_GREEN, address, COLOUR_OFF))
                else:
                    print_notice("%s %s: %s%s%s (%s%s%s)" % (action, title, COLOUR_GREEN, address, COLOUR_OFF, COLOUR_GREEN, ip, COLOUR_OFF))

    def load_access_file(self, fn, path, header):
        if not os.path.isfile(path):
            self.errors.append("Path to %s file does not exist: %s%s%s" % (header, COLOUR_GREEN, path, COLOUR_OFF))
            return False
        with open(path) as f:
            for l in f.readlines():
                fn(l)

    def load_blacklist_file(self, path):
        return self.load_access_file(self.add_blacklist, path, "blacklist")

    def load_whitelist_file(self, path):
        return self.load_access_file(self.add_whitelist, path, "whitelist")

    # Credit for initial IP functions: http://code.activestate.com/recipes/66517/

    def ip_make_mask(self, n):
        # Return a mask of n bits as a long integer
        return (2L<<n-1)-1

    def ip_strton(self, ip):
        # Convert decimal dotted quad string to long integer
        return struct.unpack('<L',socket.inet_aton(ip))[0]

    def ip_network_mask(self, ip, bits):
        # Convert a network address to a long integer
        return self.ip_strton(ip) & self.ip_make_mask(int(bits))

    def ip_addrn_in_network(self, ip, net):
        # Is a numeric address in a network?
        return ip & net == net

    def ip_validate_address(self, candidate):
        try:
            ip = socket.gethostbyname(candidate)
            return (False, self.ip_strton(ip), ip)
        except socket.gaierror:
            self.errors.append("Unable to resolve: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF))
            return (True, None, None)

    def ip_validate_cidr(self, candidate):
        a = candidate.split("/")[0]
        m = candidate.split("/")[1]
        try:
            if socket.gethostbyname(a) and int(m) <= 32:
                return (False, self.ip_network_mask(a, m))
        except socket.gaierror:
            pass
        self.errors.append("Invalid CIDR address: %s%s%s" % (COLOUR_GREEN, candidate, COLOUR_OFF))
        return (True, None)

    def is_allowed(self, address):
        # Blacklist/Whitelist filtering
        allowed = True

        if len(self.allowed_addresses) or len(self.allowed_networks):
            # Whitelist processing, address is not allowed until it is cleared.
            allowed = False

            if address in [a[2] for a in self.allowed_addresses]:
                allowed = True
            else:
                # Try checking allowed networks
                cn = self.ip_strton(address)
                for n in [n[0] for n in self.allowed_networks]:
                    if self.ip_addrn_in_network(cn, n):
                        allowed = True
                        break

        if allowed and len(self.denied_addresses) or len(self.denied_networks):
            # Blacklist processing. A blacklist argument one-ups a whitelist argument in the event of a conflict
            # Do not bother to check the blacklist if the address is already denied.

            if address in [a[2] for a in self.denied_addresses]:
                allowed = False
            else:
                # Try checking denied networks
                cn = self.ip_strton(address)
                for n in [n[0] for n in self.denied_networks]:
                    if self.ip_addrn_in_network(cn, n):
                        allowed = False
                        break
        return allowed

    def load_access_file(self, fn, path, header):
        if not os.path.isfile(path):
            self.errors.append("Path to %s file does not exist: %s%s%s" % (header, COLOUR_GREEN, path, COLOUR_OFF))
            return False
        with open(path) as f:
            for l in f.readlines():
                fn(l)

    def load_blacklist_file(self, path):
        return self.load_access_file(self.add_blacklist, path, "blacklist")

    def load_whitelist_file(self, path):
        return self.load_access_file(self.add_whitelist, path, "whitelist")
# Credit for IP functions: http://code.activestate.com/recipes/66517/

def do_message(header, addr, data):
    message = re.sub(r"\n.*", "", data)
    icon = "network-receive" # Default icon
    # Regex search message to make some attempt at context-specific icons.
    if re.match(r"important", message, re.IGNORECASE):
        icon = "dialog-warning"
    if re.match(r"error", message, re.IGNORECASE):
        icon = "dialog-error"
    elif re.match(r"urgent", message, re.IGNORECASE):
        icon = "software-update-urgent"
    elif re.match(r"appointment", message, re.IGNORECASE):
        icon = "appointment"
    elif re.match(r"(firewall|security)", message, re.IGNORECASE):
        icon = "security-medium" # I like the MATE medium security icon more than the high security icon.

    print_notice("%s: %s" % (header, message))
    try:
        p = subprocess.Popen(["notify-send", "--icon", icon, "Message from %s" % addr[0], message])
        p.communicate()
    except OSError as e:
        print_error(sys.stderr, "OSError: %s" % str(e))

def hexit(exit_code):
    print_notice("%s [-a allow-address/range] [-A allow-list-file] [-b bind-address] [-d deny-address/range] [-A deny-list-file] [-h] [-p port] [-u]" % os.path.basename(sys.argv[0]))
    exit(exit_code)

def main():

    err, args = process_arguments()
    if err:
        exit(1)

    udpMode = args.get("udp", False)

    # Print a summary of directory/bind options.
    if udpMode:
        phrasing = "datagrams"
    else:
        phrasing = "connections"
    print_notice("Relaying messages in %s received on %s%s:%d%s" % (phrasing, COLOUR_GREEN, args.get("bind", "0.0.0.0"), args.get("port", DEFAULT_RELAY_PORT), COLOUR_OFF))

    if udpMode:
        sockobj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    else:
        sockobj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind socket to local host and port
    try:
        sockobj.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockobj.bind((args.get("bind", "0.0.0.0"), args.get("port", DEFAULT_RELAY_PORT)))
        if not udpMode:
            sockobj.listen(10)
    except socket.error as msg:
        print_error('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
        exit(1)

    # Keep accepting new messages
    while True:
        try:
            if udpMode:
                data, addr = sockobj.recvfrom(1024)
            else:
                conn, addr = sockobj.accept()
        except KeyboardInterrupt:
            break

        # Blacklist/Whitelist filtering
        allowed = access.is_allowed(addr[0])
        header = "%s%s%s[%s%s%s]" % (COLOUR_GREEN, addr[0], COLOUR_OFF, COLOUR_BOLD, time.strftime("%Y-%m-%d %k:%M:%S"), COLOUR_OFF)
        if not allowed:
            # Not allowed
            print_denied("%s (%s%s%s)" % (header, COLOUR_RED, "Ignored", COLOUR_OFF))
            if not udpMode:
                conn.close()
            continue

        # Allowed
        if udpMode:
            do_message(header, addr, data)
        else:
            # Spawn new thread and pass it the new socket object
            # Multi-threading is so that an established connection
            #   with no data doesn't hold up the line.
            thread.start_new_thread(tcpclientthread, (header, conn,addr))

def process_arguments():
    args = {}
    error = False
    errors = []
    global access
    access = NetAccess()

    try:
        opts, flat_args = getopt.gnu_getopt(sys.argv[1:],"a:A:b:d:D:hp:u")
    except getopt.GetoptError as e:
        print_error("GetoptError: %s" % e)
        hexit(1)
    for opt, arg in opts:
        if opt in ("-a"):
            error = access.add_whitelist(arg) or error
        elif opt in ("-A"):
            error = access.load_whitelist_file(arg) or error
        elif opt in ("-b"):
            args["bind"] = arg
        elif opt in ("-d"):
            error = access.add_blacklist(arg) or error
        elif opt in ("-D"):
            error = access.load_blacklist_file(arg) or error
        elif opt in ("-h"):
            hexit(0)
        elif opt in ("-p"):
            args["port"] = int(arg)
        elif opt in ("-u"):
            args["udp"] = True

    if len(access.errors):
        error = True
        errors.extend(access.errors)

    if not error:
        access.announce_filter_actions()
    else:
        for e in errors:
            print_error(e)

    return error, args

def tcpclientthread(header, conn, addr):
    conn.settimeout(5)
    try:
        data = conn.recv(1024)
        if not data:
            conn.close()
            return
        do_message(header, addr, data)
        reply = "printed\n"
    except OSError:
        reply = "os-error\n"
    except socket.timeout:
        reply = "timeout\n"
    conn.sendall(reply)
    conn.close()

if __name__ == "__main__":
    main()
