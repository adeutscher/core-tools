#!/usr/bin/python

from __future__ import print_function
import argparse, getpass, hashlib, json, os, re, subprocess, sys

#
# Common Colours and Message Functions
###

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

def parse_args(raw_args):

    parser = argparse.ArgumentParser(description='Dotfile updater')
    description_pre = 'pre'
    description_post = '''
Configuration example:

{
    "files": [
        {
            "id": "bashrc-five",
            "path_in": "./blocks/block-bashrc-five",
            "path_out": "~/.bashrc",
            "weight": 5
        },
        {
            "id": "bashrc-four",
            "path_in": "./blocks/block-bashrc-four",
            "path_out": "~/.bashrc",
            "weight": 4
        },
        {
            "id": "bashrc-work",
            "path_in": "./blocks/block-bashrc-work",
            "path_out": "~/.bashrc",
            "tags": ["work"],
            "weight": 50
        },

    ],
    "variables": {
        "foo": "bar"
    }
}

Token Substitution:

  This script has 3 styles of token substitution:

    #[token]#: Substitute from environment variables.
    #<token>#: Substitute from predefined variables (see below)
    #{token}#: Substitute from variables defined in the "variables" section of the configuration file.

Predefined Variables:

  The following are predefined variables that can be subbed as tokens with the phrasing '#<token>#':

    * dir   : Directory path of the script.
    * home  : User's home directory (using '~' will also be resolved)
    * uid   : UID of current user
    * user  : Username of current user

File Configuration:

  Each object entry in Files can have the following properties:
    id           : Unique identifier for the block
    comment      : Mark the start of a comment in destination file. Default: #
    path_in      : Path to input file where raw block can be found
    path_out     : Path to output file that block shall be placed in
    script_check : Path to script to check whether or not a block should be included.
                    The script must return an exit code of 0 in order to input the block.
    script_in    : Path to script to generate content. Incompatible with path_in.
    tags         : List of strings to tag block by. If a block has a tag, then at least one tag provided in arguments must match.
    weight       : Weighting of block. The greater the value, the lower down in the file the block will be.
'''

    parser = argparse.ArgumentParser(description=description_pre, epilog=description_post, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-c', action='append', default=[], dest='config', help='Configuration JSON')
    parser.add_argument('-d', dest='dir', help='Set directory for the sake of relative paths.')
    parser.add_argument('--script-dir', action='store_true', dest='chdir', help='Change directory to that of the script for the sake of relative paths.')
    parser.add_argument('-t', action='append', default=[], dest='tags', help='Tags to activate conditional blocks. A block with tags must have at least one tag matched with this argument in order to be inserted.')
    parser.add_argument('-v', action='store_true', dest='verbose', help='Verbose mode')

    g_args = parser.add_argument_group('Manual Block Options', description='Options for defining a block with command line arguments.')
    g_args.add_argument('--comment', dest='comment', help='Mark the start of a comment in destination file. Default: #')
    g_args.add_argument('-i', dest='id', help='Argument block identifier.')
    g_args.add_argument('-f', dest='path_in', help='Input file.')
    g_args.add_argument('-o', dest='path_out', help='Output file.')
    g_args.add_argument('-s', dest='script_in', help='Content generation script.')
    g_args.add_argument('-w', dest='weight', help='Weighting of argument block. The greater the value, the lower down in the file the block will be.')
    g_args.add_argument('--ignore-config-blocks', action='store_true', dest='ignore_config_blocks', help='Do not load blocks stored in configuration files.')

    args = parser.parse_args(raw_args)

    script_dir = os.path.dirname(os.path.realpath(sys.argv[0]))

    if args.dir and args.chdir and os.path.dirname(args.dir) != script_dir:
        # Avoid conflicts, but forgive if the manual directory is the same as the script directory.
        errors.append('Cannot navigate to both the script directory and a manual directory.')
    elif args.dir:
        manual_dir = os.path.realpath(args.dir)

        if not os.path.isdir(args.dir):
            errors.append('Directory does not exist: %s' % colour_text(args.dir, COLOUR_GREEN))
        else:
            os.chdir(manual_dir)
    elif args.chdir:
        os.chdir(script_dir)

    errors = []
    variables = {}

    tags = []
    for t in args.tags:
        for tt in t.split(','):
            if tt and tt not in tags:
                tags.append(tt)

    updater_args = {
        'tags': tags
    }

    updater = DotFileUpdater(**updater_args)
    config_blocks = []

    if args.comment:
        updater.comment = args.comment
    updater.verbose = args.verbose

    sysvars = {
        'dir': script_dir,
        'home': os.path.expanduser('~'),
        'uid': os.getuid(),
        'user': getpass.getuser()
    }
    updater.load_system_variables(sysvars)

    for c in args.config:
        # Loop through configuration files the first time for all variables.
        if not os.path.isfile(c):
            print(os.getcwd(), c)
            errors.append('No such config file: ' + colour_text(c, COLOUR_GREEN))
            continue

        with open(c) as cf:
            try:
                config = json.load(cf)
            except json.decoder.JSONDecodeError:
                errors.append('Could not parse JSON file: ' + colour_text(c, COLOUR_GREEN))
                continue

            comment = config.get('comment')
            if comment and type(comment) is str:
                updater.comment = comment

            updater.load_variables(config.get('variables'))

            if not args.ignore_config_blocks:
                _config_blocks = config.get('files')
                if _config_blocks:
                    config_blocks.append((c, _config_blocks))

    for c, cf in config_blocks:
        errors += updater.load_files(cf, c)

    if args.script_in or args.path_in or args.path_out:
        file_args = {
            'parent': updater,
            'id': args.id,
            'path_in': args.path_in,
            'path_out': args.path_out,
            'script_in': args.script_in,
            'comment': updater.comment,
            'weight': args.weight or 0
        }

        errors += updater.load_file(**file_args)

    if updater.blocks_count == 0:
        errors.append('No blocks specified for substitution.')

    return (updater, errors)

def resolve(raw_content, data, pattern):

    if type(raw_content) is not str:
        raw_content = str(raw_content)

    tokens = {}
    unresolved = []
    content = raw_content

    # Get all raw tokens
    marker = 0
    while True:
        m = re.search(pattern, content[marker:])

        if not m:
            break

        k = m.group(1) or '' # Shorthand

        if k in tokens:
            obj = tokens[k]
        else:
            # First instance of a token
            obj = lambda: None
            obj.full = m.group(0)
            obj.count = 0

            tokens[k] = obj

        obj.count += 1

        marker += m.span(0)[1]

    for token_raw in tokens:
        resolved = False

        for token in token_raw.split(','):
            if not token:
                continue # Empty, bad previous resolution?
            if token in data:
                resolved = True
                content = content.replace(tokens[token_raw].full, data[token])

        if not resolved:
            unresolved.append((token_raw, tokens[token_raw].full, tokens[token_raw].count))

    if unresolved:
        print(content, unresolved)
        print(data)
    return (content, unresolved)

def run_script(script_path, get_content = True):

    args = {
    }

    if get_content:
        args['stdout'] = subprocess.PIPE

    process = subprocess.Popen([os.path.realpath(script_path)], **args)
    process.wait()
    output = ''
    if process.stdout:
        raw_output = process.stdout.read()
        if sys.version_info.major >= 3:
            output = str(raw_output, 'utf-8')
        else:
            output = str(raw_output)
    return (process.returncode, output)

class DotFileUpdater:

    DEFAULT_COMMENT = '#'

    def __get_blocks_count(self):
        return len(self.__blocks)

    def __get_comment(self):
        return self.__comment or self.DEFAULT_COMMENT

    def __get_debug(self):
        return self.__debug

    def __get_environ(self, value):
        return self.__environ

    def __get_file(self, item, fallback_comment):
        if item.path_out in self.__files:
            return self.__files[item.path_out]
        args = {
            'parent': self,
            'path': item.path_out,
            'comment': item.comment or fallback_comment
        }
        f = DotFileUpdaterFile(**args)
        self.__files[item.path_out] = f
        return f

    def __init__(self, **kwargs):

        self.__comment = None

        self.debug = False
        self.verbose = False

        self.environ = kwargs.get('environ', os.environ)
        self.tags = kwargs.get('tags', [])

        self.__blocks = []
        self.__files = {}
        self.__system_variables = {}
        self.__variables = {}

    def __set_comment(self, value):
        self.__comment = value

    def __set_debug(self, value):
        self.__debug = value

    def __set_environ(self, value):
        self.__environ = value

    def add_system_variable(self, key, value):
        # Add values to variable list
        self.__system_variables[key], errors = self.resolve(value)
        return errors

    def add_variable(self, key, value):
        # Add values to variable list
        self.__variables[key], errors = self.resolve(value)
        return errors

    blocks_count = property(__get_blocks_count)

    comment = property(__get_comment, __set_comment)

    debug = property(__get_debug, __set_debug)

    def load_file(self, **kwargs):
        self.__blocks.append(DotFileUpdaterItem(**kwargs))
        return self.__blocks[-1].get_errors()

    def load_files(self, data, path_config):

        errors = []

        if type(data) is not list:
            return errors

        num = 0
        for f in [f for f in data if type(f) is dict]:

            file_args = {
                'parent': self,
                'path_config': path_config,
                'path_config_count': num,
                'id': f.get('id'),
                'path_in': f.get('path_in'),
                'path_out': f.get('path_out'),
                'script_check': f.get('script_check'),
                'script_in': f.get('script_in'),
                'comment': f.get('comment') or self.comment,
                'weight': f.get('weight') or 0
            }

            tags = f.get('tags')
            if type(tags) is list:
                file_args['tags'] = [t for t in tags if type(t) is str]

            self.load_file(**file_args)

            num += 1

        return errors

    def load_variables(self, data):
        if type(data) is not dict:
            return

        accepted_types = [int, str]
        if sys.version_info.major < 3:
            # JSON data is loaded as unicode-type in Python2
            accepted_types.append(unicode)

        for k in data:
            print(type(data[k]))
            if type(data[k]) in accepted_types:
                # Is of an accepted type.
                self.add_variable(k, data[k])
            # Ignoring nesting for the moment.


    def load_system_variables(self, data):
        if type(data) is not dict:
            return

        for k in data:
            if type(data[k]) not in [int, str]:
                # Not a string or number, ignore nesting for the moment
                continue

            self.add_system_variable(k, data[k])

    def resolve(self, raw_content):

        resolved_sysvars, unresolved_sysvars = resolve(raw_content, self.__system_variables, '#\<([^}]+)?\>#')
        if unresolved_sysvars and not self.debug:
            for label, full, count in unresolved_sysvars:
                resolved_sysvars = resolved_sysvars.replace(full, '')

        resolved_os, unresolved_os = resolve(resolved_sysvars, self.environ, r'#\[([^\]]+)?\]#')
        if unresolved_os and not self.debug:
            for label, full, count in unresolved_os:
                resolved_os = resolved_os.replace(full, '')

        resolved_vars, unresolved_vars = resolve(resolved_os, self.__variables, '#{([^}]+)?}#')
        if unresolved_vars and not self.debug:
            for label, full, count in unresolved_vars:
                resolved_vars = resolved_vars.replace(full, '')

        # The returned list of unresolved items should be from both sources
        return os.path.expanduser(resolved_vars), unresolved_sysvars + unresolved_os + unresolved_vars

    def run(self):

        for item in self.__blocks:

            if self.verbose:

                identifier = '%s (%s)' % (item.id, colour_text(item.path_in, COLOUR_GREEN))

                if item.is_wanted(self.tags):
                    print('Block', identifier, '->', colour_text(item.path_out, COLOUR_GREEN))
                else:
                    print('Block skipped: ', identifier)

            # Load up the current file.
            current_file = self.__get_file(item, self.comment)
            current_file.add_item(item)

        for k in self.__files:
            self.__files[k].write()

    def set_comment(self, value):
        # Chainable version of regular comment setter.
        self.comment = value
        return self

    def set_environ(self, value):
        # Chainable version of regular environ setter.
        self.environ = value
        return self

class DotFileUpdaterBlock:
    def __get_end(self):
        return self.__end

    def __get_start(self):
        return self.__start

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.checksum = kwargs.get('checksum')
        self.__end = kwargs.get('end')
        self.__start = kwargs.get('start')
        self.weight = kwargs.get('weight')

    def __set_end(self, value):
        self.__end = value

    def __set_start(self, value):
        self.__start = value

    end = property(__get_end, __set_end)
    start = property(__get_start, __set_start)

class DotFileUpdaterFile:
    def __init__(self, **kwargs):

        self.__is_modified = False
        self.__is_valid = True

        self.__comment = kwargs.get('comment')
        self.__parent = kwargs.get('parent')
        self.__path = kwargs.get('path')

        self.__new = not os.path.isfile(self.__path)

        # Get lines
        if self.__new:
            # If the file is new, just add an empty list
            self.__lines = []
        else:
            # If existing file, then grab lines from file

            with open(self.__path, 'r') as f:
                self.__lines = [re.sub(r'\r?\n?$', '', l) for l in f.readlines()]

        self.__recalc_blocks()

    def __is_modified(self):
        return self.__is_modified

    def __is_valid(self):
        return self.__is_valid

    def __is_verbose(self):
        return self.__parent.verbose

    def __recalc_blocks(self):
        self.__blocks = []

        i = 0

        target_id = None
        checksum = None
        weight = 0

        while i < len(self.__lines):
            line = self.__lines[i] # Shorthand

            if line.startswith(self.__comment):
                # We only care about content that starts with a comment.

                words = line.replace('\t', ' ').split(' ')

                if target_id is None:
                    # Seeking the start of a block
                    m = [w for w in words if w.startswith('marker:') and w != 'marker:']
                    if m:
                        target_id = ':'.join(m[-1].split(':')[1:]).strip()
                        start = i

                        # Also look for sub-items on the marker line
                        m = [w for w in words if w.startswith('checksum:') and w != 'checksum:']
                        if m:
                            checksum = ':'.join(m[-1].split(':')[1:]).strip()

                        m = [w for w in words if w.startswith('weight:') and w != 'weight:']
                        if m:
                            weight = int(m[-1].split(':')[1])
                else:
                    # Seeking the end of a target block
                    end = None
                    m = [w for w in words if w.startswith('end:') and w != 'end:']
                    if m:
                        end = ':'.join(m[-1].split(':')[1:]).strip()

                        if end != target_id:
                            print('%s: Found the start of "%s" block before the end of the "%s" block' % (colour_text(self.__path, COLOUR_GREEN), target_id, end))
                            self.__is_valid = False
                            return False
                        else:
                            block_args = {
                                'id' : target_id,
                                'checksum': checksum,
                                'weight': weight,
                                'start': start,
                                'end': i
                            }

                            self.__blocks.append(DotFileUpdaterBlock(**block_args))

                            target_id = checksum = None

            i += 1 # Next line

        # If we finished the loop without finding the end of an ID, then the file is invalid
        if target_id is not None:
            print('%s: Did not find the end of "%s" block.' % (colour_text(self.__path, COLOUR_GREEN), target_id))
            return False
        return True

    def add_item(self, item):

        checksum = item.get_checksum()
        unchanged = False
        old_start = None
        old_weight = None

        if item.script_in:
            identifier = '%s (generated by %s):' % (item.id, colour_text(item.script_in, COLOUR_GREEN))
        else:
            identifier = '%s (%s):' % (item.id, colour_text(item.path_in, COLOUR_GREEN))

        for i in [b for b in self.__blocks if b.id == item.id]:
            # Does a block with this ID currently exist?

            if i.checksum == checksum:
                # The block does not need updating
                unchanged = True
                continue

            #  If changed, then remove content and recalc blocks.
            #    We will be replacing it with an update below
            #    In the edge-case that the same block ID exists in multiple places,
            #      all non-matching blocks will be removed. This shouldn't happen unless
            #      someone has gone and manually messed with a file.

            self.__is_modified = True
            to_remove = i.end - i.start

            old_start = i.start
            old_weight = i.weight
            while to_remove >= 0:
                self.__lines.pop(i.start)
                to_remove -= 1

            if not self.__recalc_blocks():
                return False

        display_out = colour_text(item.path_out, COLOUR_GREEN)

        if unchanged:
            print('No chanes to %s content in %s' % (colour_text(item.id), display_out))
            return True

        if old_start is not None and item.weight == old_weight:
            # If an instance was removed and the weight of the new config is unchanged
            #   from the removed instance, then insert the new content exactly where
            #   we found the old content

            print(identifier, 'Replacing block in-place in %s.' % display_out)

            return self.insert_content(item, old_start, False)

        # Try to get the latest item in the file of equal weight
        #   If found, then insert the new block immediately after the old block, recalculate blocks, and return

        items = [b for b in self.__blocks if b.weight == item.weight] # Assuming that ordering is already handled
        if items:
            # Insert after last item of equal weight
            print(identifier, 'Inserting block after the last block of equal weight in %s.' % display_out)
            return self.insert_content(item, items[-1].end + 1)

        # Try to get the latest item in the file of lesser weight
        #   If found, then insert the new block immediately after the old block, recalculate blocks, and return
        items = [b for b in self.__blocks if b.weight < item.weight] # Assuming that ordering is already handled
        if items:
            # Insert after last item of lesser weight
            print(identifier, 'Inserting block after the last block of lesser weight in %s.' % display_out)
            return self.insert_content(item, items[-1].end + 1)

        # Try to get the latest item in the file of greater weight
        #   If found, then insert the new block immediately before the heavier block block, recalculate blocks, and return
        items = [b for b in self.__blocks if b.weight > item.weight] # Assuming that ordering is already handled
        if items:
            # Insert before first item of greater weight
            print(identifier, 'Inserting block before the first block of equal weight in %s.' % display_out)
            return self.insert_content(item, items[0].start)

        # If none of the other insertion methods were valid, then append the data to the end of the list.
        print(identifier, 'Appending block to the end of %s.' % display_out)

        return self.insert_content(item)

    def insert_content(self, item, start_raw = None, padding = True):

        self.__is_modified = True

        start = start_raw
        if start is None:
            # If no start was given, append the list
            start = len(self.__lines)

        content, errors = self.__parent.resolve(item.get_content())
        for token, raw, count in errors:
            print('%s: Could not resolve token: %s' % (colour_text(self.__path, COLOUR_GREEN, raw)))
        lines = content.split('\n')

        display = {
            'comment': self.__comment,
            'id': item.id,
            'checksum': item.get_checksum(),
            'weight': item.weight
        }

        lines.insert(0, '') # Post-header line
        lines.insert(0, '%(comment)s marker:%(id)s checksum:%(checksum)s weight:%(weight)d' % display) # Insert header
        if padding:
            # Add extra newlines
            lines.insert(0, '')

        lines.append('') # Pre-footer line
        lines.append('%(comment)s end:%(id)s' % display)
        if padding:
            # Add extra newlines for a fresh insertion
            lines.append('')

        while lines:
            # Insert lines to target - starting from the end so that they are in the right order
            self.__lines.insert(start, lines.pop())

        return self.__recalc_blocks()

    is_modified = property(__is_modified)
    is_valid = property(__is_valid)
    is_verbose = property(__is_verbose)

    def write(self):
        if not self.is_modified:

            if self.is_verbose:
                print('File not modified: %s' % colour_text(self.__path, COLOUR_GREEN))

            return # No changes to write to the file.

        # Confirm directory
        d = os.path.dirname(self.__path)
        if d and not os.path.isdir(d):
            os.makedirs(d)

        print('Saving changes to file: %s' % colour_text(self.__path, COLOUR_GREEN))
        with open(self.__path, 'w') as f:
            f.write('\n'.join(self.__lines))

class DotFileUpdaterItem:

    def __get_path_in(self):
        resolved, errors = self.__parent.resolve(self.__path_in or '')
        # Ignore errors, assumed to have been cleared by error checking.
        return resolved

    def __get_path_out(self):
        resolved, errors = self.__parent.resolve(self.__path_out or '')
        # Ignore errors, assumed to have been cleared by error checking.
        return resolved

    def __get_script_check(self):
        resolved, errors = self.__parent.resolve(self.__script_check or '')
        # Ignore errors, assumed to have been cleared by error checking.
        return resolved

    def __get_script_in(self):
        resolved, errors = self.__parent.resolve(self.__script_in or '')
        # Ignore errors, assumed to have been cleared by error checking.
        return resolved

    def __get_weight(self):
        return self.__weight or 0

    def __init__(self, **kwargs):

        self.__content = None

        self.__parent = kwargs.get('parent')
        self.__path_config = kwargs.get('path_config')
        self.__path_config_count = kwargs.get('path_config_count')

        self.id, unresolved = self.__parent.resolve(kwargs.get('id', ''))
        self.comment = kwargs.get('comment')
        self.__path_in = kwargs.get('path_in', '')
        self.__path_out = kwargs.get('path_out', '')
        self.tags = kwargs.get('tags', [])

        self.__script_check = kwargs.get('script_check', '')
        self.__script_in = kwargs.get('script_in', '')

        self.__weight = kwargs.get('weight')

    def get_checksum(self):

        if sys.version_info.major >= 3:
            content = bytes(self.get_content(), 'utf-8')
        else:
            content = bytes(self.get_content())

        hash_func = hashlib.md5()
        hash_func.update(content)
        return hash_func.hexdigest()

    def get_content(self):

        if self.__content is not None:
            # Use cached content
            return self.__content
        if self.script_in:
            exit_code, self.__content = run_script(self.script_in, True)
            if exit_code != 0:
                raise Exception('Input script failed (returncode %d): %s' % (exit_code, colour_text(self.script_in, COLOUR_GREEN)))
        elif self.path_in == '-':
            self.__content = sys.stdin.read()
        else:
            with open(self.path_in) as f:
                self.__content = f.read()

        return self.__content

    def get_errors(self):

        errors = []
        if self.__path_config:
            label = '%s (File %s): ' % (colour_text(self.__path_config, COLOUR_GREEN), colour_text(self.__path_config_count))
        else:
            label = 'Arguments: '

        if not self.id:
            errors.append(label + 'No ID specified')


        if self.__script_in and self.__path_in:
            errors.append(label + 'Cannot have both an input script and an input file at the same time.')
        elif self.path_in == '-':
            pass
        elif self.__script_in:
            resolved, errors_sub = self.__parent.resolve(self.__script_in or '')
            for token, raw, count in errors_sub:
                e = 'Unable to resolve token in script_in:' + colour_text(raw)
                if count > 1:
                    e += ' (%s instances)' % colour_text(count)
                errors.append(label + e)
            if not errors_sub and not os.path.isfile(resolved):
                errors.append('Input script does not exist: ' + colour_text(resolved, COLOUR_GREEN))
        elif not self.__path_in:
            errors.append(label + 'No input path specified.')
        else:
            resolved, errors_sub = self.__parent.resolve(self.__path_in or '')
            for token, raw, count in errors_sub:
                e = 'Unable to resolve token in path_in:' + colour_text(raw)
                if count > 1:
                    e += ' (%s instances)' % colour_text(count)
                errors.append(label + e)
            if not errors_sub and not os.path.isfile(resolved):
                errors.append('Input file does not exist: ' + colour_text(resolved, COLOUR_GREEN))

        if not self.__path_out:
            errors.append(label + 'No output path specified.')
        else:
            resolved, errors_sub = self.__parent.resolve(self.__path_out or '')
            for token, raw, count in errors_sub:
                e = 'Unable to resolve token in path_out:' + colour_text(raw)
                if count > 1:
                    e += ' (%s instances)' % colour_text(count)
                errors.append(label + e)
            # Note: It's alright if the output file does not exist yet.

        if self.__script_check:
            resolved, errors_sub = self.__parent.resolve(self.__script_check or '')
            for token, raw, count in errors_sub:
                e = 'Unable to resolve token in script_check:' + colour_text(raw)
                if count > 1:
                    e += ' (%s instances)' % colour_text(count)
                errors.append(label + e)
            if not errors_sub and not os.path.isfile(resolved):
                errors.append('Check script does not exist: ' + colour_text(resolved, COLOUR_GREEN))

        return errors

    def is_wanted(self, request_tags):
        # Sources of authority
        sources = []

        if self.tags:
            # Could do this in a more compact way, but it would make for a more monstrous line
            wanted = False
            for t in request_tags:
                if t in self.tags:
                    wanted = True
                    break
            sources.append(wanted) # Decision of tag matching

        if self.script_check:
            exit_code, content = run_script(self.script_check, False)
            print(content)
            sources.append(exit_code == 0)

        # Either no sources saying no, or all sources say 'yes'
        return not sources or len([s for s in sources if s]) == len(sources)

    path_in = property(__get_path_in)
    path_out = property(__get_path_out)
    script_check = property(__get_script_check)
    script_in = property(__get_script_in)

    weight = property(__get_weight)

def main(raw_args):
    updater, errors = parse_args(raw_args)

    if errors:
        for e in errors:
            print(e)
        exit(1)

    exit_code = updater.run()
    exit(exit_code)

if __name__ == '__main__':
    main(sys.argv[1:])
