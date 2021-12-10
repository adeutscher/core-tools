#!/usr/bin/env python3

from argparse import ArgumentParser
from base64 import b64decode
from functools import cache
from re import match, sub
from socket import gaierror, gethostbyname
from subprocess import DEVNULL as devnull, PIPE as pipe, Popen as run_cmd
from sys import argv, stderr, stdout
from threading import Thread, Lock
from time import time

import logging
import os


def _build_logger(label, err=None, out=None):
    obj = logging.getLogger(label)
    obj.setLevel(logging.DEBUG)
    # Err
    err_handler = logging.StreamHandler(err or stderr)
    err_filter = logging.Filter()
    err_filter.filter = lambda record: record.levelno >= logging.WARNING
    err_handler.addFilter(err_filter)
    obj.addHandler(err_handler)
    # Out
    out_handler = logging.StreamHandler(out or stdout)
    out_filter = logging.Filter()
    out_filter.filter = lambda record: record.levelno < logging.WARNING
    out_handler.addFilter(out_filter)
    obj.addHandler(out_handler)
    return obj


def _collect_password(self, prompt):
    temp = ''
    while not temp.strip():
        temp = getpass.getpass('%s: ' % prompt)
    return temp


def _colour_text(text, colour=None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return f'{colour}{text}{COLOUR_OFF}'


def _confirm_requirements(**kwargs):

    good = True

    if kwargs.get('ec2'):
        good, _ = _get_ec2_client()
        good_2, _ = _get_ec2_cipher()
        good = good and good_2

    return good


def _enable_colours(force=None):
    global COLOUR_BOLD
    global COLOUR_BLUE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_OFF
    if force == True or (force is None and stdout.isatty()):
        # Colours for standard output.
        COLOUR_BOLD = '\033[1m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_BOLD = ''
        COLOUR_BLUE = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_OFF = ''


def _get_command_new(resolution, display=False, **kwargs):
    '''Get command string for new-style xfreerdp switches.'''

    target, user, password = resolution

    # Static switches
    cmd = 'xfreerdp +auto-reconnect +clipboard +compression +heartbeat /compression-level:2'
    switches = cmd.split(' ')

    if kwargs.get('legacy_security'):
        switches.append('/sec:rdp')

    if kwargs.get('ignore_certs'):
        switches.append('/cert:ignore')

    if kwargs.get('audio'):
        switches.extend(['/sound', '/microphone'])

    # Display size
    switches.append('/h:%d' % kwargs['height'])
    switches.append('/w:%d' % kwargs['width'])
    # Domain/Password/User
    if kwargs.get('domain'):
        switches.append('/d:%s' % kwargs.get('domain'))

    if password:
        if display:
            switches.append('/p:%s' % _colour_text(''.rjust(len(password), '*')))
        else:
            switches.append('/p:%s' % password)

    switches.append('/u:%s' % (user or os.getlogin()))
    # Server address
    switches.append('/v:%s' % target)

    return switches


def _get_command_old(resolution, display=None, **kwargs):
    '''Get command string for old-style xfreerdp switches.
    The old style of switches probably aren't in use anymore,
    but it's a short and straightforward method.

    This entire script came about because I didn't want to juggle
    switches between a machine with the old style and a script with
    the new one.'''

    target, user, password = resolution

    # Static switches
    cmd = 'xfreerdp --plugin cliprdr'
    switches = cmd.split(' ')

    # RDP Security Switch
    if kwargs.get('legacy_security'):
        switches.extend('--sec rdp'.split(' '))

    # Display size
    switches.extend(['-g', self.geometry])
    # Domain/Password/User
    if kwargs.get('domain'):
        switches.extend(['-d', kwargs.get('domain')])

    if password:
        if display:
            switches.extend(['-p', _colour_text(''.rjust(len(self.password), '*'))])
        else:
            switches.extend(['-p', password])
    switches.extend(['-u', user or os.getlogin()])
    # Server address
    switches.append(target)

    return switches


def _get_ec2_cipher(key_path=None):

    try:
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.PublicKey import RSA
    except ModuleNotFoundError as e:
        _logger.error(str(e))
        return False, None

    if key_path is None:
        # Short-circuit when confirming requirements
        # If we got here, then the Crypto components imported successfully.
        return True, None

    with open(key_path, 'r') as handle:
        key = RSA.importKey(handle.read())
    return True, PKCS1_v1_5.new(key)


def _get_ec2_client():
    try:
        from boto3 import client
    except ModuleNotFoundError as e:
        _logger.error(str(e))
        return False, None

    return True, client('ec2')


@cache
def _is_installed():
    # Credit: 'Jay': https://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    is_exe = lambda p: os.path.isfile(p) and os.access(p, os.X_OK)

    for path in os.environ.get('PATH', '').split(os.pathsep):
        if is_exe(os.path.join(path.strip('"'), 'xfreerdp')):
            return True
    return False


@cache
def _is_new_rdp():
    try:
        p = run_cmd(['xfreerdp'], stdout=pipe, stderr=devnull)

        # Read the first 10 lines for the usage summary.
        # Not counting on it being on a specific line within self.
        i = 0
        for line in p.stdout.readlines():
            i += 1
            if i > 10:
                break
            if bytes('[/v:<server>[:port]]', 'utf-8') in line:
                return True
                break
    except OSError:
        # Since we are already checking for xfreerdp, this probably will not come up.
        # This is mostly here because I was doing some initial development on a machine without xfreerdp.
        pass
    return False


def _parse_args(args_list):

    # Defaults
    DEFAULT_HEIGHT = 900
    DEFAULT_WIDTH = 1600
    # Environment Variables
    ENV_DOMAIN = 'RDP_DOMAIN'
    ENV_USER = 'RDP_USER'
    ENV_HEIGHT = 'RDP_HEIGHT'
    ENV_WIDTH = 'RDP_WIDTH'
    ENV_RDP_INTERNAL = 'RDP_EC2_USE_INTERNAL'
    ENV_EC2_KEY_DIRECTORY = 'EC2_KEY_DIRECTORY'

    def validate_int(value_raw, label, expr=lambda i: i > 0, msg=None):
        try:
            value_parsed = int(value_raw)
            if expr(value_parsed):
                return True, value_parsed
        except ValueError:
            pass  # Fall through to failure-handling
        _logger.error(msg or 'Invalid %s: %s' % (label, value_raw))
        return False, None

    good = True

    if not _is_installed():
        _logger.error('Command is not installed: %s' % _colour_text('xfreerdp'))
        good = False

    # Define/use parser
    ###

    parser = ArgumentParser(description='xfreerdp wrapper')
    parser.add_argument('server', help='Server address')
    parser.add_argument(
        '-v', dest='verbose', action='store_true', help='Verbose output'
    )

    # RDP options
    g_rdp = parser.add_argument_group('rdp options')
    g_rdp.add_argument(
        '-a', dest='audio', action='store_true', help='Enable audio I/O for session.'
    )
    g_rdp.add_argument('-g', dest='geometry', help='Specify geometry ( WxH )')
    g_rdp.add_argument(
        '-i',
        dest='ignore_certs',
        action='store_true',
        help='Ignore certificate validation',
    )
    g_rdp.add_argument(
        '-s',
        dest='legacy_security',
        action='store_true',
        help='Use legacy RDP security mode',
    )
    g_rdp.add_argument(
        '--height', dest='height', help='RDP window height (overrides -g)'
    )
    g_rdp.add_argument('--width', dest='width', help='RDP window width (overrides -g)')

    # User options
    g_user = parser.add_argument_group('user options')
    g_user.add_argument(
        '-d', dest='domain', default=os.environ.get(ENV_DOMAIN), help='User domain name'
    )
    g_user.add_argument(
        '-P', dest='password_prompt', action='store_true', help='Prompt for password'
    )
    g_user.add_argument('-p', dest='password', help='RDP password')
    g_user.add_argument('-u', dest='user', help='Username (default: user)')

    # EC2 Options
    g_ec2 = parser.add_argument_group('ec2 options')
    g_ec2.add_argument(
        '-e',
        dest='ec2',
        action='store_true',
        help='Mark that the target is an EC2 instance.',
    )
    g_ec2.add_argument(
        '-k', dest='ec2_key_file', help='Path to EC2 key file. (implies -e)'
    )
    g_ec2.add_argument(
        '--key-directory',
        dest='ec2_key_directory',
        help='If using EC2, look in this directory for keys. (implies -e if used manually)',
    )
    g_ec2.add_argument(
        '--ec2-internal',
        dest='ec2_prioritize_internal',
        action='store_true',
        help='Use internal EC2 IP. Set %s=1 to make this standard.' % ENV_RDP_INTERNAL,
    )
    g_ec2.add_argument(
        '--ec2-password-only',
        dest='ec2_password_only',
        action='store_true',
        help='Fetch and print EC2 password. Useful for use with Remote Desktop programs other than xfreerdp. (implies -e)',
    )

    parsed_args = parser.parse_args(args_list)

    # Argument details
    ###

    # Arguments dictionary with basic fields.
    args = {
        # Target
        'server': parsed_args.server,
        # Misc
        'verbose': parsed_args.verbose,
        # RDP Options
        'audio': parsed_args.audio,
        'ignore_certs': parsed_args.ignore_certs,
        'legacy_security': parsed_args.legacy_security,
        'height': DEFAULT_HEIGHT,
        'width': DEFAULT_WIDTH,
        # User Options
        'domain': parsed_args.domain,
        'user_manual': parsed_args.user is not None,
        # EC2 Options
        'ec2': parsed_args.ec2
        or parsed_args.ec2_key_file is not None
        or parsed_args.ec2_key_directory is not None
        or parsed_args.ec2_password_only,
        'ec2_key_file': parsed_args.ec2_key_file,
        'ec2_key_directory': parsed_args.ec2_key_directory
        or os.environ.get(ENV_EC2_KEY_DIRECTORY, ''),
        'ec2_password_only': parsed_args.ec2_password_only,
        'ec2_prioritize_internal': parsed_args.ec2_prioritize_internal
        or len(os.environ.get(ENV_RDP_INTERNAL, '')) > 0,
    }

    # Details for user options
    ###

    # Set password
    if parsed_args.password_prompt:
        args['password'] = _collect_password('Enter password')
    else:
        args['password'] = parsed_args.password

    args['user'] = parsed_args.user or os.environ.get(ENV_USER)

    # Set/validate geometry
    if parsed_args.geometry:
        # Parse geometry
        if match('^\s*\d+x\d+\s*$', parsed_args.geometry):
            parts = parsed_args.geometry.strip().split('x')
            args['width'] = int(parts[0])
            args['height'] = int(parts[1])
        else:
            _logger.error(f'Invalid geometry: {parsed_args.geometry}')
            good = False

    # Set/validate height after geometry
    if parsed_args.height:
        good_value, args['height'] = validate_int(parsed_args.height)
        good = good and good_value

    # Set/validate width after geometry
    if parsed_args.width:
        good_value, args['width'] = validate_int(parsed_args.width)
        good = good and good_value

    # Details for EC2 options
    ###

    if args['ec2'] and not (parsed_args.ec2_key_file or args['ec2_key_directory']):
        _logger.error('Using EC2, but no key file or key directory was provided.')
        good = False

    if parsed_args.ec2_key_file and not os.path.isfile(parsed_args.ec2_key_file):
        _logger.error(f'Key file not found: {parsed_args.ec2_key_file}')
        good = False

    if parsed_args.ec2_key_directory and not os.path.isdir(
        parsed_args.ec2_key_directory
    ):
        _logger.error(f'Key directory not found: {parsed_args.ec2_key_directory}')
        good = False

    return good, args


def _print_summary(resolution, **kwargs):
    '''Output a summary of what xfreerdp will be doing.'''

    target, user, has_password = resolution

    if kwargs['domain']:
        user = '%s\%s' % (kwargs['domain'], user)

    display_values = {
        'server': _colour_text(target, COLOUR_BLUE),
        'geometry': _colour_text('%sx%s' % (kwargs['width'], kwargs['height'])),
        'user': _colour_text(user or kwargs['user'] or os.getlogin()),
    }

    if kwargs['server'] != target:
        display_values['server'] = '(%s) %s' % (
            _colour_text(kwargs['server']),
            display_values['server'],
        )

    if kwargs['ec2_password_only']:
        message = 'Getting credentials for %(server)s'
    else:
        # Standard message
        message = 'Connecting to %(server)s (display: %(geometry)s) as %(user)s'

        if has_password:
            message += ' with a password'

    message += '.'

    _logger.info(message % display_values)

    if not kwargs['ec2_password_only']:

        if kwargs.get('legacy_security'):
            _logger.warning('Using legacy security mode.')

        if kwargs.get('ignore_certs'):
            _logger.warning('Ignoring certificate validation.')

    if kwargs['ec2'] and not kwargs['user_manual']:
        # 'administrator' user is assumed, unless overridden a username argument
        _logger.warning(
            '"%(user)s" user is assumed for connecting to an EC2 instance.'
            % display_values
        )


def _resolve_ec2_target(**kwargs):
    '''Use the provided server label as a guide for finding a Windows-based EC2 instance.'''

    label = kwargs.get(
        'server'
    )  # Record the server as it was before we started resolving.
    verbose = kwargs.get('verbose')

    _logger.info(f'Identifying an EC2 instance from label: {_colour_text(label)}')

    _, client = _get_ec2_client()

    # Tried to do this in a one-liner, but it was getting very hard to read.
    reservations = []
    response = {'NextToken': None}
    while 'NextToken' in response:
        try:
            request = {}
            if response.get('NextToken'):
                request['NextToken'] = response['NextToken']
            response = client.describe_instances(**request)
            reservations.append(response.get('Reservations', []))
        except client.exceptions.ClientError as e:
            _logger.error(str(e))
            return False, None, None, None

    # This could be done in one line, but it was a nightmare to debug.
    raw_instances = []
    for reservation in reservations:
        for reservation_items in reservation:
            raw_instances.extend(
                [EC2InventoryItem(item) for item in reservation_items['Instances']]
            )

    instances = list(
        filter(lambda item: item.is_running and item.is_windows, raw_instances)
    )

    if verbose:
        _logger.info('Potential Windows instances:')
        for instance in instances:
            _logger.info(f'\t{instance}')
        _logger.info('Non-windows instances (not considered):')
        for instance in [
            item for item in raw_instances if item.is_running and not item.is_windows
        ]:
            _logger.info(f'\t{instance}')
        _logger.info('Non-running instances (not considered):')
        for instance in [i for i in raw_instances if not i.is_running]:
            _logger.info(f'\t{instance}')

    check = lambda ec2: label in (
        ec2.ip_public,
        ec2.ip_internal,
        ec2.instance_id,
        ec2.name,
    )
    matches = [i for i in instances if check(i)]

    if not matches:
        _logger.error(
            f'Unable to resolve label to a running EC2 Windows instance: {_colour_text(label)}'
        )
        return False, None, None, None

    # Need to pull the encrypted password and decrypt it
    found = False
    for instance in matches:
        display_data = {
            'id': _colour_text(instance.instance_id),
            'name': _colour_text(instance.name or 'Unnamed'),
        }

        password = None
        if not kwargs.get('password'):
            # No manual password was entered, so try to extract from EC2

            password_data = client.get_password_data(InstanceId=instance.instance_id)
            raw_password = b64decode(password_data.get('PasswordData', '').strip())
            if not raw_password:
                print_error(
                    'Unable to get encrypted password data from instance: \'%(id)s\' (%(name)s)'
                    % display_data
                )
                continue

            key_path = kwargs['ec2_key_file']

            if not key_path and kwargs['ec2_key_directory']:
                key_path_noext = key_path = os.path.join(
                    kwargs['ec2_key_directory'], instance.key
                )
                if not os.path.isfile(key_path):
                    key_path += '.pem'

            if not key_path:
                _logger.error(f'No key path available for key: {instance.key}')
                continue
            if not os.path.isfile(key_path):
                _logger.error(f'Key not found: {instance.key}')
                continue

            cipher_good, cipher = _get_ec2_cipher(key_path)
            if not cipher_good:
                continue

            display_data['path'] = key_path

            password = cipher.decrypt(raw_password, None)

            if not password:
                _logger.error(
                    'Unable to decode encrypted password data from instance \'%(id)s\' (%(name)s), decryption key is probably be incorrect. File: %(path)s'
                    % display_data
                )
                continue

            password = str(password, 'utf-8')

        found = True

        if not kwargs['ec2_prioritize_internal'] and instance.ip_public:
            target = instance.ip_public
        else:
            target = instance.ip_internal
        break

    if not found:
        _logger.error(
            'Unable to decode encrypted password data from any candidate instance.'
        )

    if kwargs.get('user_manual', False):
        user = kwargs['user']
    else:
        user = 'administrator'

    return found, target, user, password


def _resolve_target(**kwargs):
    if kwargs['ec2']:
        return _resolve_ec2_target(**kwargs)

    try:
        target = gethostbyname(kwargs['server'])
        good = True
    except gaierror:
        _logger.error(
            'Unable to resolve server address: %s'
            % _colour_text(parsed_args.server, COLOUR_BLUE)
        )
        good = False
    return good, target, kwargs['user'], kwargs['password']


def _translate_seconds(duration):
    '''Translate seconds to something more human-readable.'''
    modules = [
        ('seconds', 60),
        ('minutes', 60),
        ('hours', 24),
        ('days', 7),
        ('weeks', 52),
        ('years', 100),
    ]

    num = max(0, int(duration))

    if not num:
        # Handle empty
        return f'0 {modules[0][0]}'

    times = []
    for i in range(len(modules)):

        noun, value = modules[i]
        mod_value = num % value

        if mod_value == 1:
            noun = sub('s$', '', noun)

        if mod_value:
            times.append(f'{mod_value} {noun}')

        num = int(num / value)
        if not num:
            break  # No more modules to process

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


'''Represents an EC2 instance'''


class EC2InventoryItem:
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

    def __str__(self):

        display_values = {
            'id': _colour_text(self.instance_id),
            'state': _colour_text(self.state, self.__colour_state()),
            'name': _colour_text(self.name or '<Unnamed>', self.__colour_host()),
            'ip-internal': _colour_text(self.ip_internal, COLOUR_BLUE),
            'ip-public': _colour_text(self.ip_public, COLOUR_BLUE),
            'key': _colour_text(self.key),
        }

        return '[%(id)s][%(state)s]: %(name)s' % display_values

    @property
    def is_running(self):
        return self.state == 'running'

    @property
    def is_windows(self):
        return self.platform == 'windows'


def main(args_raw):
    good, args = _parse_args(args_raw)
    # Confirm requirements that aren't needed for default usage.
    good = _confirm_requirements(**args) and good

    good_resolution, target, user, password = _resolve_target(**args)
    good = good and good_resolution

    if not good:
        exit(1)

    _print_summary((target, user, password is not None), **args)

    if args.get('ec2_password_only'):
        _logger.info(f'User: {user or os.getlogin()}')
        _logger.info(f'Password: {password}')
        exit(0)

    if _is_new_rdp():
        cmd_func = _get_command_new
    else:
        cmd_func = _get_command_old
    switches = cmd_func((target, user, password), **args)

    # Run RDP
    time_start = time()

    try:
        if args.get('verbose'):
            print(' '.join(cmd_func((target, user, password), True, **args)))
        p = run_cmd(switches, stdout=stdout, stderr=stderr)

        # Run until the process ends.
        p.communicate()
        exit_code = p.returncode
    except KeyboardInterrupt:
        p.kill()
        exit_code = 130
    except OSError as e:
        print_error('OSError: %s' % e)
        exit_code = 1

    time_end = time()
    time_diff = time_end - time_start

    if (time_diff) > 60:
        # Print a summary of time for any session duration over a minute
        #  (this amount of time implies a connection that didn't just
        #   die from xfreerdp timing out when trying to connect)
        _logger.info(
            'RDP Session Duration: %s' % _colour_text(self.translate_seconds(time_diff))
        )

    exit(exit_code)


_enable_colours()
_logger = _build_logger('rdp')
if __name__ == '__main__':  # pragma: no cover
    try:
        main(argv[1:])
    except KeyboardInterrupt:
        exit(130)
