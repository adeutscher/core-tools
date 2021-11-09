#!/usr/bin/env python

'''rdp.py: Wrapper script for xfreerdp'''

from __future__ import print_function
import argparse, base64, getpass, os, re, socket, subprocess, sys, time

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message, stderr=False):
    f=sys.stdout
    if stderr:
        f=sys.stderr
    print('%s[%s]: %s' % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message), file=f)

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)

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

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, 'Error', message)

def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ''
    if msg:
        sub_msg = ' (%s)' % msg
    print_error('Unexpected %s%s: %s' % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, 'Notice', message)

def print_warning(message):
    _print_message(COLOUR_YELLOW, 'Warning', message)

class EC2InventoryItem:
    '''Represents an EC2 instance'''
    def __init__(self, entry):

        self.state = entry.get('State', {}).get('Name', 'unknown')
        self.ip_public = entry.get('PublicIpAddress')
        self.ip_internal = entry.get('PrivateIpAddress')
        self.instance_id = entry.get('InstanceId')
        self.platform = entry.get('Platform')
        self.key = entry.get('KeyName')

        self.name = None
        for tag in entry.get('Tags', []):
            if tag.get('Key') == 'Name':
                self.name = tag.get('Value', '')
                break

    def __colour_host(self):
        '''Get text colouring for hostname.'''
        if self.is_windows:
            return COLOUR_BLUE

        return COLOUR_BOLD

    def __colour_state(self):
        '''Get text colouring for state'''
        if self.is_running:
            return COLOUR_GREEN

        if self.state == 'pending':
            return COLOUR_YELLOW

        return COLOUR_RED

    def __is_running(self):
        return self.state == 'running'

    def __is_windows(self):
        return self.platform == 'windows'

    def __str__(self):

        display_values = {
            'id': colour_text(self.instance_id),
            'state': colour_text(self.state, self.__colour_state()),
            'name': colour_text(self.name or '<Unnamed>', self.__colour_host()),
            'ip-internal': colour_text(self.ip_internal, COLOUR_BLUE),
            'ip-public': colour_text(self.ip_public, COLOUR_BLUE),
            'key': colour_text(self.key)
        }

        s = '[%(id)s][%(state)s]: %(name)s' % display_values

        if self.is_running:
            addr_string = 'Internal: %(ip-internal)s' % display_values
            if self.ip_public:
                addr_string += ' , Public: %(ip-public)s' % display_values
            display_values['addr'] = addr_string
            s+= ' ( %(addr)s ). Key: %(key)s' % display_values

        return s

    is_running = property(__is_running)
    is_windows = property(__is_windows)

class RdpWrapper:
    '''Main wrapper around xfreerdp'''

    CMD = 'xfreerdp'

    # Defaults
    DEFAULT_HEIGHT = 900
    DEFAULT_WIDTH = 1600
    # Environment Variables
    ENV_DOMAIN = 'RDP_DOMAIN'
    ENV_USER = 'RDP_USER'
    ENV_HEIGHT = 'RDP_HEIGHT'
    ENV_WIDTH = 'RDP_WIDTH'
    ENV_RDP_INTERNAL = 'RDP_EC2_USE_INTERNAL'

    def __get_command_new(self, display):
        '''Get command string for new-style xfreerdp switches.'''

        # Static switches
        cmd = '%s +auto-reconnect +clipboard +compression +heartbeat /compression-level:2' % self.CMD
        switches = cmd.split(' ')

        if self.is_legacy_security:
            switches.append('/sec:rdp')

        if self.args.ignore_certs:
            switches.append('/cert:ignore')

        if(self.args.audio):
            switches.extend(['/sound', '/microphone'])

        # Display size
        switches.append('/h:%d' % self.height)
        switches.append('/w:%d' % self.width)
        # Domain/Password/User
        if self.args.domain:
            switches.append('/d:%s' % self.args.domain)
        if self.password:
            if display:
                switches.append('/p:%s' % colour_text(''.join([c*len(self.password) for c in '*'])))
            else:
                switches.append('/p:%s' % self.password)

        switches.append('/u:%s' % self.user)
        # Server address
        switches.append('/v:%s' % self.server)

        return switches

    def __get_command_old(self, display):
        '''Get command string for old-style xfreerdp switches.
           The old style of switches probably aren't in use anymore,
           but it's a short and straightforward method.

           This entire script came about because I didn't want to juggle
           switches between a machine with the old style and a script with
           the new one.'''

        # Static switches
        cmd = '%s --plugin cliprdr' % self.CMD
        switches = cmd.split(' ')

        # RDP Security Switch
        if self.legacy_security:
            switches.extend('--sec rdp'.split(' '))

        # Display size
        switches.extend(['-g', self.geometry])
        # Domain/Password/User
        if self.args.domain:
            switches.extend(['-d', self.args.domain])
        if self.password:
            if display:
                switches.extend(['-p', colour_text(''.join([c*len(self.password) for c in '*']))])
            else:
                switches.extend(['-p', self.password])
        switches.extend(['-u', self.user])
        # Server address
        switches.append(self.server)

        return switches

    def __get_ec2_cipher(self):
        if not os.path.isfile(self.args.ec2_key_file):
            print_error('EC2 key file not found: %s' % colour_text(self.args.ec2_key_file, COLOUR_GREEN))
            return None

        # File exists.
        try:
            from Crypto.Cipher import PKCS1_v1_5
            from Crypto.PublicKey import RSA

            with open(self.args.ec2_key_file, 'r') as handle:
                key = RSA.importKey(handle.read())
            return PKCS1_v1_5.new(key)

        except NameError as e:
            print_error("Could not load EC2 key file because required RSA module was not loaded from pycrypto.")
        except Exception as e:
            # Most likely: Path provided was not to a file with a proper RSA key.
            print_error("Encountered %s loading EC2 key file '%s': %s" % (colour_text(type(e).__name__, COLOUR_RED), colour_text(self.args.ec2_key_file, COLOUR_GREEN), str(e)))

    def __get_ec2_prioritize_internal(self):
        return self.args.prioritize_internal or os.environ.get(self.ENV_RDP_INTERNAL) == '1'

    def __get_geometry(self):
        '''Return window dimensions in WxH format.'''
        return '%dx%d' % (self.width, self.height)

    def __get_height(self):
        '''Return the highest-priority window height'''
        try:
            env_height = int(os.environ.get(self.ENV_HEIGHT))
        except (TypeError, ValueError):
            env_height = self.DEFAULT_HEIGHT

        return self.args.height or self.__geo_height or env_height

    def __get_password(self):
        '''Return the highest-priority password source'''
        return self.format_string(self.__prompted_password or self.__stored_password or self.args.password)

    def __get_server(self):
        '''Return the highest-priority server source'''
        return self.__stored_server or self.args.server

    def __get_width(self):
        '''Return the highest-priority window width'''
        try:
            env_width = int(os.environ.get(self.ENV_WIDTH))
        except (TypeError, ValueError):
            env_width = self.DEFAULT_WIDTH

        return self.args.width or self.__geo_width or env_width

    def __get_user(self):
        '''Return the highest-priority user'''
        if self.args.user:
            return self.args.user

        if self.args.ec2_key_file:
            # If an EC2 key file is being used, then assume that the user is 'administrator'
            return 'administrator'

        return os.environ.get(self.ENV_USER, os.getlogin())

    def __init__(self):
        self.__geo_width = None
        self.__geo_height = None
        self.__stored_password = None
        self.__stored_server = None

    def __is_installed(self):

        program = self.CMD
        # Credit: 'Jay': https://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
        is_exe = lambda p : os.path.isfile(p) and os.access(p, os.X_OK)

        fpath, fname = os.path.split(program)
        if fpath and is_exe(program):
            return True

        for path in os.environ.get('PATH', '').split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return True
        return False

    def __is_legacy_security(self):
        return self.args.legacy_security and not self.is_using_ec2

    def __is_new_rdp(self):
        try:
            p = subprocess.Popen([self.CMD], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Read the first 10 lines for the usage summary.
            # Not counting on it being on a specific line within self.
            i = 0
            for line in p.stdout.readlines():
                i += 1
                if i > 10:
                    break
                if self.format_bytes('[/v:<server>[:port]]') in line:
                    return True
                    break
        except OSError:
            # Since we are already checking for xfreerdp, this probably will not come up.
            # This is mostly here because I was doing some initial development on a machine without xfreerdp.
            pass
        return False

    def __is_using_ec2(self):
        return self.args.ec2_key_file is not None

    def collect_password(self, prompt):
        temp = ''
        while not temp.strip():
            temp = getpass.getpass('%s: ' % prompt)
        return temp

    ec2_cipher = property(__get_ec2_cipher)
    ec2_prioritize_internal = property(__get_ec2_prioritize_internal)

    def format_bytes(self, content):
        if sys.version_info.major == 2:
            return bytes(content)
        elif type(content) is bytes:
            return content # Already bytes
        return bytes(content, 'utf-8')

    def format_string(self, content):
        if content is None:
            return ''
        if sys.version_info.major == 2:
            return str(content)
        elif type(content) is str:
            return content # Already string
        return str(content, 'utf-8')

    geometry = property(__get_geometry)

    def get_command(self, display=False):
        initial = ''
        if self.is_new_rdp:
            return self.__get_command_new(display)
        return self.__get_command_old(display)

    height = property(__get_height)
    is_installed = property(__is_installed)
    is_legacy_security = property(__is_legacy_security)
    is_new_rdp = property(__is_new_rdp)
    is_using_ec2 = property(__is_using_ec2)
    password = property(__get_password)
    server = property(__get_server)
    width = property(__get_width)

    def print_error(self, msg):
        '''Lazy wrapper around printing to sys.stderr'''
        print(msg, file=sys.stderr)

    def print_summary(self):
        '''Output a summary of what xfreerdp will be doing.'''

        user = self.user
        if self.args.domain:
            user = '%s\%s' % (self.args.domain, user)

        display_values = {
            'server': colour_text(self.server, COLOUR_BLUE),
            'geometry': colour_text(self.geometry),
            'user': colour_text(user)
        }

        message = 'Connecting to %(server)s (display: %(geometry)s) as %(user)s' % display_values

        if self.password:
            message += ' with a password'
        message += '.'

        print_notice(message)

        if self.is_legacy_security:
            print_warning('Using legacy security mode.')

        if self.args.ignore_certs:
            print_warning('Ignoring certificate validation.')

        if self.is_using_ec2 and not self.args.user:
            # 'administrator' user is assumed, unless overridden a username argument
            print_warning('"%(user)s" user is assumed for connecting to an EC2 instance.' % display_values)

    def process_args(self, args_list):
        '''Handle arguments, and report back if everything looks valid.'''
        good = True
        if not self.is_installed:
            self.print_error('Command is not installed: %s' % colour_text('xfreerdp'))
            good = False

        parser = argparse.ArgumentParser(description='xfreerdp wrapper')
        parser.add_argument('server', help='Server address')
        parser.add_argument('-v', dest='verbose', action='store_true', help='Verbose output')
        # RDP options
        g_rdp = parser.add_argument_group('rdp options')
        g_rdp.add_argument('-a', dest='audio', action='store_true', help='Enable audio I/O for session.')
        g_rdp.add_argument('-g', dest='geometry', help='Specify geometry ( WxH )')
        g_rdp.add_argument('-i', dest='ignore_certs', action='store_true', help='Ignore certificate validation')
        g_rdp.add_argument('-s', dest='legacy_security', action='store_true', help='Use legacy RDP security mode')
        g_rdp.add_argument('--height', dest='height', type=int, help='RDP window height (overrides -g)')
        g_rdp.add_argument('--width', dest='width', type=int, help='RDP window width (overrides -g)')
        # User options
        g_user = parser.add_argument_group('user options')
        g_user.add_argument('-d', dest='domain', default=os.environ.get(self.ENV_DOMAIN), help='User domain name')
        g_user.add_argument('-e', dest='ec2_key_file', help='Path to EC2 key file')
        g_user.add_argument('--ec2-internal', dest='prioritize_internal', action='store_true', help='Use internal EC2 IP. Set %s=1 to make this standard.' % self.ENV_RDP_INTERNAL)
        g_user.add_argument('-P', dest='password_prompt', action='store_true', help='Prompt for password')
        g_user.add_argument('-p', dest='password', help='RDP password')
        g_user.add_argument('-u', dest='user', help='Username')

        self.args = parser.parse_args(args_list)

        self.__prompted_password = None
        if self.args.password_prompt:
            self.__prompted_password = self.collect_password('Enter password')

        if self.args.geometry:
            # Parse geometry
            if re.match('^\d+x\d+$', self.args.geometry):
                parts = [int(i) for i in self.args.geometry.split('x')]
                self.__geo_width = parts[0]
                self.__geo_height = parts[1]
            else:
                self.print_error('Invalid geometry: %s' % self.args.geometry)
                good = False

        # Confirm that no weird height values were given.
        if self.height <= 0:
            self.print_error('Invalid height: %s' % colour_text(self.height))
            good = False

        # Confirm that no weird width values were given.
        if self.width <= 0:
            self.print_error('Invalid width: %s' % colour_text(self.width))
            good = False

        if self.args.ec2_key_file:
            good = self.resolve_ec2() and good
        else:
            try:
                socket.gethostbyname(self.server)
            except socket.gaierror:
                self.print_error('Unable to resolve server address: %s' % colour_text(self.server, COLOUR_BLUE))
                good = False

        return good

    def resolve_ec2(self):
        '''Use the provided server label as a guide for finding a Windows-based EC2 instance.'''

        label = self.server # Record the server as it was before we started resolving.
        print_notice('Identifying an EC2 instance from label: %s' % colour_text(label))

        good = True
        try:
            import boto3
        except ImportError:
            self.print_error('%s module is not installed, required for EC2 lookups' % colour_text('boto3'))
            good = False

        try:
            import Crypto.Cipher
            import Crypto.PublicKey
        except ImportError:
            self.print_error('%s module is not installed, required for EC2 lookups' % colour_text('pycrypto'))
            good = False

        if not os.path.isfile(self.args.ec2_key_file):
            self.print_error('No such file for use as EC2 key: %s' % colour_text(self.args.ec2_key_file, COLOUR_GREEN))
            good = False

        if not good:
            return False

        client = boto3.client('ec2')

        raw_instances = []

        # Tried to do this in a one-liner, but it was getting very hard to read.
        try:
            response = client.describe_instances()
        except client.exceptions.ClientError as e:
            print_exception(e)
            return False

        for sublist in [cluster for cluster in [r['Instances'] for r in [rl for rl in response['Reservations']]]]:
            raw_instances += [EC2InventoryItem(i) for i in sublist]

        instances = [i for i in raw_instances if i.is_running and i.is_windows]

        if self.args.verbose:
            print_notice('Potential Windows instances:')
            for instance in instances:
                print('\t',instance)
            print_notice('Non-windows instances (not considered):')
            for instance in [i for i in raw_instances if i.is_running and not i.is_windows]:
                print('\t',instance)
            print_notice('Non-running instances (not considered):')
            for instance in [i for i in raw_instances if not i.is_running]:
                print('\t',instance)

        check = lambda ec2: label in (ec2.ip_public, ec2.ip_internal, ec2.instance_id, ec2.name)
        matches = [i for i in instances if check(i)]

        if not matches:
            print_error('Unable to resolve label to a running EC2 Windows instance: %s' % colour_text(label))
            return False

        cipher = self.ec2_cipher
        if not cipher:
            return False # Immediately return, error messages handled within self.ec2_cipher

        # Need to pull the encrypted password and decrypt it
        found = False
        for instance in matches:
            display_data = {
                'id': colour_text(instance.instance_id),
                'name': colour_text(instance.name or 'Unnamed'),
                'path': colour_text(self.args.ec2_key_file, COLOUR_GREEN)
            }

            self.__stored_server = instance.ip_internal
            if not self.ec2_prioritize_internal and instance.ip_public:
                self.__stored_server = instance.ip_public
            password_data = client.get_password_data(InstanceId = instance.instance_id)
            raw_password = base64.b64decode(password_data.get('PasswordData', '').strip())
            if not raw_password:
                print_error('Unable to get encrypted password data from instance: \'%(id)s\' (%(name)s)' % display_data)
                continue

            self.__stored_password = cipher.decrypt(raw_password, None)
            if self.__stored_password:
                found = True
                break

            print_error('Unable to decode encrypted password data from instance \'%(id)s\' (%(name)s), decryption key is probably be incorrect. File: %(path)s' % display_data)

        if not found:
            print_error('Unable to decode encrypted password data from any candidate instance.')

        return found

    def run(self, args_list):
        '''Central run method.'''
        if not self.process_args(args_list):
            return 1

        self.print_summary()

        return self.run_rdp()

    def run_rdp(self):
        '''Directly run xfreerdp'''
        time_start = time.time()

        try:
            if self.args.verbose:
                print(' '.join(self.get_command(True)))
            p = subprocess.Popen(self.get_command(), stdout=sys.stdout, stderr=sys.stderr)

            # Run until the process ends.
            p.communicate()
            exit_code = p.returncode
        except KeyboardInterrupt:
            p.kill()
            exit_code = 130
        except OSError as e:
            print_error('OSError: %s' % e)
            exit_code = 1

        time_end = time.time()
        time_diff = time_end - time_start

        if (time_diff) > 60:
            # Print a summary of time for any session duration over a minute
            #  (this amount of time implies a connection that didn't just
            #   die from xfreerdp timing out when trying to connect)
            print_notice('RDP Session Duration: %s' % colour_text(self.translate_seconds(time_diff)))

        return exit_code

    def translate_seconds(self, duration):
        '''Translate seconds to something more human-readable.'''
        modules = [
            ('seconds', 60),
            ('minutes',60),
            ('hours',24),
            ('days',7),
            ('weeks',52),
            ('years',100)
        ]

        num = max(0, int(duration))

        if not num:
            # Handle '0' input.
            return '0 %s' % modules[0][0]

        times = []
        for i in range(len(modules)):

            noun, value = modules[i]
            mod_value = num % value

            if mod_value == 1:
                noun = re.sub('s$', '', noun)

            if mod_value:
                times.append('%s %s' % (mod_value, noun))

            num = int(num / value)
            if not num:
                break # No more modules to process

        if len(times) == 1:
            return ' '.join(times)
        elif len(times) == 2:
            return ', '.join(reversed(times))
        else:
            # Oxford comma
            d = ', and '
            s = d.join(reversed(times))
            sl = s.split(d, len(times) - 2)
            return ', '.join(sl)

    user = property(__get_user)

if __name__ == '__main__':
    try:
        rdp = RdpWrapper()
        exit_code = rdp.run(sys.argv[1:])
    except KeyboardInterrupt:
        exit_code = 130
    exit(exit_code)
