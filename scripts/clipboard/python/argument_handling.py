#!/usr/bin/env python

###########################################

# Common Argument Handling Structure
# My own implementation of an argparse-like structure to add args and
#   build a help menu that I have a bit more control over.
#
# Note: These functions assume that my common message functions are also being used.
#       If this is not the case or if the functions are in a different module:
#          * Adjust print_foo functions.
#          * Adjust colour_text() calls.
#          * Adjust all mentions of COLOUR_* variables.

from __future__ import print_function
import getopt, os, re, sys

MASK_OPT_TYPE_LONG = 1
MASK_OPT_TYPE_ARG = 2

OPT_TYPE_FLAG = 0
OPT_TYPE_SHORT = MASK_OPT_TYPE_ARG
OPT_TYPE_LONG_FLAG = MASK_OPT_TYPE_LONG
OPT_TYPE_LONG = MASK_OPT_TYPE_LONG | MASK_OPT_TYPE_ARG

TITLE_HELP = 'help'

class ArgHelper:

    def __init__(self):
        self.args = {}
        self.defaults = {}
        self.raw_args = {}
        self.operands = []

        self.operand_text = None

        self.errors = []
        self.validators = []

        self.opts = {OPT_TYPE_FLAG: {}, OPT_TYPE_SHORT: {}, OPT_TYPE_LONG: {}, OPT_TYPE_LONG_FLAG: {}}
        self.opts_by_label = {}

        self.add_opt(OPT_TYPE_FLAG, 'h', TITLE_HELP, description='Display a help menu and then exit.')

    def __contains__(self, arg):
        return arg in self.args

    def __getitem__(self, arg, default = None):
        opt = self.opts_by_label.get(arg)

        if not opt:
            # There was no registered option.
            #   Giving give the args dictionary an attempt in case
            #   something like a validator went and added to it.
            return self.args.get(arg)
        if opt.multiple:
            default = []

        # Silly note: Doing a get() out of a dictionary when the stored
        #   value of the key is None will not fall back to default
        value = self.args.get(arg)
        if value is None:
            if opt.environment:
                value = os.environ.get(opt.environment, self.defaults.get(arg))
            else:
                value = self.defaults.get(arg)

        if value is None:
            return default
        return value

    def __setitem__(self, key, value):
        self.args[key] = value

    def add_opt(self, opt_type, flag, label, description = None, required = False, default = None, default_colour = None, default_announce = False, environment = None, converter=str, multiple = False, strict_single = False):

        if opt_type not in self.opts:
            raise Exception('Bad option type: %s' % opt_type)

        has_arg = opt_type & MASK_OPT_TYPE_ARG

        prefix = '-'
        match_pattern = '^[a-z0-9]$'
        if opt_type & MASK_OPT_TYPE_LONG:
            prefix = '--'
            match_pattern = '^[a-z0-9\-]+$' # ToDo: Improve on this regex?

        arg = prefix + flag

        # Check for errors. Developer errors get intrusive exceptions instead of the error list.
        if not label:
            raise Exception('No label defined for flag: %s' % arg)
        if not flag:
            raise Exception('No flag defined for label: %s' % label)
        if not opt_type & MASK_OPT_TYPE_LONG and len(flag) - 1:
            raise Exception('Short options must be 1-character long.') # A bit redundant, but more informative
        if not re.match(match_pattern, flag, re.IGNORECASE):
            raise Exception('Invalid flag value: %s' % flag) # General format check
        for g in self.opts:
            if opt_type & MASK_OPT_TYPE_LONG == g & MASK_OPT_TYPE_LONG and arg in self.opts[g]:
                raise Exception('Flag already defined: %s' % label)
        if label in self.opts_by_label:
            raise Exception('Duplicate label (new: %s): %s' % (arg, label))
        if multiple and strict_single:
            raise Exception('Cannot have an argument with both "multiple" and "strict_single" set to True.')
        # These do not cover harmless checks on arg modifiers with flag values.

        obj = OptArg(self)
        obj.opt_type = opt_type
        obj.label = label
        obj.required = required and opt_type & MASK_OPT_TYPE_ARG
        obj.default = default
        obj.default_colour = default_colour
        obj.default_announce = default_announce
        obj.environment = environment
        obj.multiple = multiple
        obj.description = description
        obj.converter = converter
        obj.has_arg = has_arg
        obj.strict_single = strict_single

        self.opts_by_label[label] = self.opts[opt_type][arg] = obj
        if not has_arg: default = False
        elif multiple: default = []
        self.defaults[label] = default

    add_validator = lambda s, fn: s.validators.append(fn)

    def _get_opts(self):
        s = ''.join([k for k in sorted(self.opts[OPT_TYPE_FLAG])])
        s += ''.join(['%s:' % k for k in sorted(self.opts[OPT_TYPE_SHORT])])
        return s.replace('-', '')

    def _get_opts_long(self):
        l = ['%s=' % key for key in sorted(self.opts[OPT_TYPE_LONG].keys())] + sorted(self.opts[OPT_TYPE_LONG_FLAG].keys())
        return [re.sub('^-+', '', i) for i in l]

    def convert_value(self, raw_value, opt):

        value = None
        try:
            value = opt.converter(raw_value)
        except:
            pass

        if value is None:
            self.errors.append('Unable to convert %s to %s: %s' % (colour_text(opt.label), opt.converter.__name__, colour_text(raw_value)))

        return value

    get = __getitem__

    def hexit(self, exit_code = 0):

        s = './%s' % os.path.basename(sys.argv[0])
        lines = []
        for label, section in [('Flags', OPT_TYPE_FLAG), ('Options', OPT_TYPE_SHORT), ('Long Flags', OPT_TYPE_LONG_FLAG), ('Long Options', OPT_TYPE_LONG)]:

            if not self.opts[section]: continue

            lines.append('%s:' % label)
            for f in sorted(self.opts[section].keys()):
                obj = self.opts[section][f]
                s+= obj.get_printout_usage(f)
                lines.append(obj.get_printout_help(f))

        if self.operand_text: s += ' %s' % self.operand_text

        _print_message(COLOUR_PURPLE, 'Usage', s)
        for l in lines: print(l)

        if exit_code >= 0: exit(exit_code)

    def last_operand(self, default = None):
        if not len(self.operands):
            return default
        return self.operands[-1]

    def load_args(self, cli_args = []):
        if cli_args == sys.argv:
            cli_args = cli_args[1:]

        if not cli_args:
            return True

        try:
            output_options, self.operands = getopt.gnu_getopt(cli_args, self._get_opts(), self._get_opts_long())
        except Exception as e:
            self.errors.append('Error parsing arguments: %s' % str(e))
            return False

        for opt, optarg in output_options:
            found = False
            for has_arg, opt_type_tuple in [(True, (OPT_TYPE_SHORT, OPT_TYPE_LONG)), (False, (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG))]:
                if found:
                    break
                for opt_key in opt_type_tuple:
                    if opt in self.opts[opt_key]:
                        found = True
                        obj = self.opts[opt_key][opt]
                        if has_arg:
                            if obj.label not in self.raw_args:
                                self.raw_args[obj.label] = []
                            self.raw_args[obj.label].append(optarg)
                        else:
                            # Flag, single-argument
                            self.args[obj.label] = True
        return True

    def process(self, args = [], exit_on_error = True, print_errors = True):

        validate = self.load_args(args)

        if self[TITLE_HELP]: self.hexit(0)

        if validate: self.validate()

        if self.errors:
            if print_errors:
                for e in self.errors: print_error(e)
            if exit_on_error: exit(1)

        return not self.errors

    def set_operand_help_text(self, text):
        self.operand_text = text

    def validate(self):
        for key in self.raw_args:

            obj = self.opts_by_label[key]

            if not obj.has_arg: self.args[obj.label] = True

            if not obj.multiple:

                if obj.strict_single and len(self.raw_args[obj.label]) > 1:
                    self.errors.append('Cannot have multiple %s values.' % colour_text(obj.label))

                else:

                    value = self.convert_value(self.raw_args[obj.label][-1], obj)
                    if value is not None: self.args[obj.label] = value

            elif obj.multiple:
                self.args[obj.label] = []
                for i in self.raw_args[obj.label]:

                    value = self.convert_value(i, obj)
                    if value is not None: self.args[obj.label].append(value)

            elif self.raw_args[obj.label]:

                value = self.convert_value(self.raw_args[obj.label][-1], obj)
                if value is not None: self.args[obj.label] = value

        for o in [self.opts_by_label[o] for o in self.opts_by_label if self.opts_by_label[o].required and o not in self.raw_args]:
            if not o.environment or not os.environ.get(o.environment):
                self.errors.append('Missing %s value.' % colour_text(o.label))
        for v in self.validators:
            r = v(self)
            if r:
                if isinstance(r, list): self.errors.extend(r) # Append all list items
                else: self.errors.append(r) # Assume that this is a string.

class OptArg:

    def __init__(self, args):
        self.opt_type = 0
        self.args = args

    is_flag = lambda s: s.opt_type in (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG)

    def get_printout_help(self, opt):

        desc = self.description or 'No description defined'

        if self.is_flag(): s = '  %s: %s' % (opt, desc)
        else: s = '  %s <%s>: %s' % (opt, self.label, desc)

        if self.environment:
            s += ' (Environment Variable: %s)' % colour_text(self.environment)

        if self.default_announce:
            # Manually going to defaults table allows this core module
            # to have its help display reflect retroactive changes to defaults.
            s += ' (Default: %s)' % colour_text(self.args.defaults.get(self.label), self.default_colour)
        return s

    def get_printout_usage(self, opt):

        if self.is_flag(): s = opt
        else: s = '%s <%s>' % (opt, self.label)

        if self.required: return ' %s' % s
        else: return ' [%s]' % s
