#!/usr/bin/python

from __future__ import print_function
import datetime, getopt, os, re, sys

# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message):
    print("%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message))

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

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
    _print_message(COLOUR_RED, "Error", message)

def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ""
    if msg:
        sub_msg = " (%s)" % msg
    print_error("Unexpected %s%s: %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message)

# Argument Handling
###

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

MASK_OPT_TYPE_LONG = 1
MASK_OPT_TYPE_ARG = 2

OPT_TYPE_FLAG = 0
OPT_TYPE_SHORT = MASK_OPT_TYPE_ARG
OPT_TYPE_LONG_FLAG = MASK_OPT_TYPE_LONG
OPT_TYPE_LONG = MASK_OPT_TYPE_LONG | MASK_OPT_TYPE_ARG

TITLE_HELP = "help"

class ArgHelper:

    args = {}
    defaults = {}
    raw_args = {}
    operands = []

    operand_text = None

    errors = []
    validators = []

    opts = {OPT_TYPE_FLAG: {}, OPT_TYPE_SHORT: {}, OPT_TYPE_LONG: {}, OPT_TYPE_LONG_FLAG: {}}
    opts_by_label = {}

    def __init__(self):
        self.add_opt(OPT_TYPE_FLAG, "h", TITLE_HELP, description="Display a help menu and then exit.")

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
            raise Exception("Bad option type: %s" % opt_type)

        has_arg = opt_type & MASK_OPT_TYPE_ARG

        prefix = "-"
        match_pattern = "^[a-z0-9]$"
        if opt_type & MASK_OPT_TYPE_LONG:
            prefix = "--"
            match_pattern = "^[a-z0-9\-]+$" # ToDo: Improve on this regex?

        arg = prefix + flag

        # Check for errors. Developer errors get intrusive exceptions instead of the error list.
        if not label:
            raise Exception("No label defined for flag: %s" % arg)
        if not flag:
            raise Exception("No flag defined for label: %s" % label)
        if not opt_type & MASK_OPT_TYPE_LONG and len(flag) - 1:
            raise Exception("Short options must be 1-character long.") # A bit redundant, but more informative
        if not re.match(match_pattern, flag, re.IGNORECASE):
            raise Exception("Invalid flag value: %s" % flag) # General format check
        for g in self.opts:
            if opt_type & MASK_OPT_TYPE_LONG == g & MASK_OPT_TYPE_LONG and arg in self.opts[g]:
                raise Exception("Flag already defined: %s" % label)
        if label in self.opts_by_label:
            raise Exception("Duplicate label (new: %s): %s" % (arg, label))
        if multiple and strict_single:
            raise Exception("Cannot have an argument with both 'multiple' and 'strict_single' set to True.")
        # These do not cover harmless checks on arg modifiers with flag values.

        obj = OptArg()
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
        if not has_arg:
            default = False
        elif multiple:
            default = []
        self.defaults[label] = default

    def add_validator(self, fn):
        self.validators.append(fn)

    def _get_opts(self):
        s = "".join([k for k in sorted(self.opts[OPT_TYPE_FLAG])])
        s += "".join(["%s:" % k for k in sorted(self.opts[OPT_TYPE_SHORT])])
        return s.replace('-', '')

    def _get_opts_long(self):
        l = ["%s=" % key for key in sorted(self.opts[OPT_TYPE_LONG].keys())] + sorted(self.opts[OPT_TYPE_LONG_FLAG].keys())
        return [re.sub("^-+", "", i) for i in l]

    def convert_value(self, raw_value, opt):
        value = None

        try:
            value = opt.converter(raw_value)
        except:
            pass

        if value is None:
            self.errors.append("Unable to convert %s to %s: %s" % (colour_text(opt.label), opt.converter.__name__, colour_text(raw_value)))

        return value

    get = __getitem__

    def hexit(self, exit_code = 0):

        s = "./%s" % os.path.basename(sys.argv[0])
        lines = []
        for label, section in [("Flags", OPT_TYPE_FLAG), ("Options", OPT_TYPE_SHORT), ("Long Flags", OPT_TYPE_LONG_FLAG), ("Long Options", OPT_TYPE_LONG)]:
            if not self.opts[section]:
                continue

            lines.append("%s:" % label)
            for f in sorted(self.opts[section].keys()):
                obj = self.opts[section][f]
                s+= obj.get_printout_usage(f)
                lines.append(obj.get_printout_help(f))

        if self.operand_text:
            s += " %s" % self.operand_text

        _print_message(COLOUR_PURPLE, "Usage", s)
        for l in lines:
            print(l)

        if exit_code >= 0:
            exit(exit_code)

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
            self.errors.append("Error parsing arguments: %s" % str(e))
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
        validate = True
        if not self.load_args(args):
            validate = False

        if self[TITLE_HELP]:
            self.hexit(0)

        if validate:
            self.validate()

        if self.errors:
            if print_errors:
                for e in self.errors:
                    print_error(e)

            if exit_on_error:
                exit(1)
        return not self.errors

    def set_operand_help_text(self, text):
        self.operand_text = text

    def validate(self):
        for key in self.raw_args:
            obj = self.opts_by_label[key]
            if not obj.has_arg:
                self.args[obj.label] = True
            if not obj.multiple:
                if obj.strict_single and len(self.raw_args[obj.label]) > 1:
                    self.errors.append("Cannot have multiple %s values." % colour_text(obj.label))
                else:
                    value = self.convert_value(self.raw_args[obj.label][-1], obj)
                    if value is not None:
                        self.args[obj.label] = value
            elif obj.multiple:
                self.args[obj.label] = []
                for i in self.raw_args[obj.label]:
                    value = self.convert_value(i, obj)
                    if value is not None:
                        self.args[obj.label].append(value)
            elif self.raw_args[obj.label]:
                value = self.convert_value(self.raw_args[obj.label][-1], obj)
                if value is not None:
                    self.args[obj.label] = value
        for m in [self.opts_by_label[o].label for o in self.opts_by_label if self.opts_by_label[o].required and o not in self.raw_args]:
            self.errors.append("Missing %s value." % colour_text(m))
        for v in self.validators:
            r = v(self)
            if r:
                if isinstance(r, list):
                    self.errors.extend(r) # Append all list items
                else:
                    self.errors.append(r) # Assume that this is a string.

class OptArg:

    opt_type = 0

    def is_flag(self):
        return self.opt_type in (OPT_TYPE_FLAG, OPT_TYPE_LONG_FLAG)

    def get_printout_help(self, opt):

        desc = self.description or "No description defined"

        if self.is_flag():
            s = "  %s: %s" % (opt, desc)
        else:
            s = "  %s <%s>: %s" % (opt, self.label, desc)

        if self.environment:
            s += " (Environment Variable: %s)" % colour_text(self.environment)

        if self.default_announce:
            # Manually going to defaults table allows this core module
            # to have its help display reflect retroactive changes to defaults.
            s += " (Default: %s)" % colour_text(args.defaults.get(self.label), self.default_colour)
        return s

    def get_printout_usage(self, opt):

        if self.is_flag():
            s = opt
        else:
            s = "%s <%s>" % (opt, self.label)
        if self.required:
            return " %s" % s
        else:
            return " [%s]" % s

# Script Class and Functions
###

class LambdaFunction:

    versions = []
    target_version = None

    target_version = "$LATEST"
    latest_version = "$LATEST"

    def __init__(self, name, arn, version):
        self.name = name
        self.arn = arn
        self.version = version

class LambdaAlias:
    def __init__(self, name, version):
        self.name = name
        self.version = version

    def __str__(self):
        return "LambdaAlias: %s (version: %s)" % (self.name, self.version)

class LambdaVersion:
    def __init__(self, name, checksum):
        self.name = name
        self.checksum = checksum

class LambdaPinner():

    def __init__(self):
        self.client = boto3.client('lambda')

    def create_version(self, target):

        # ToDo: Replace with a detailed timestamp (currently running into an odd problem with text validation...)
        desc = args.get(TITLE_DESCRIPTION, "")

        target_checksum = target.versions[target.target_version].checksum
        latest_checksum = target.versions["$LATEST"].checksum

        if target_checksum == latest_checksum:
            # Use checksums that we already had incidentally to see whether or not we need to make a new version.
            print_notice("No changes made to %s since version %s of function %s, so no version was created." % (colour_text("$LATEST"), colour_text(target.latest_version), colour_text(target.arn)))
            return True

        try:
            # Setting target version because any case of setting the target version will be in the context of immediately pinning to that version.
            target.target_version = self.client.publish_version(FunctionName = target.arn, Description = desc)["Version"]
            print_notice("Created a new version for function %s: %s" % (colour_text(target.arn), colour_text(target.target_version)))

            return True
        except Exception as e:
            print_error("Unable to create a version for function '%s': %s" % (target.arn, str(e)))
            return False

    '''
    Set up our functions and do any remaining validation that requires an API call.
    '''
    def get_lambda_functions(self):

        self.targets = {}
        functions = {}

        try:
            for instance in self.client.list_functions()["Functions"]:

                # At this point we only REALLY need the ARN.
                # The name is gravy for orinting content.
                # The version "might be useful later".

                f = LambdaFunction(instance["FunctionName"], instance["FunctionArn"], instance["Version"])

                # Lazy lookup approach: Just store the function info under both its name and its ARN.
                functions[f.arn] = functions[f.name] = f
        except Exception as e:
            print_error("Failed to get cloud functions from AWS: %s" % str(e))
            return False

        # Reminder: 'good' is only used for a true/false check, hence why it's an integer now and a boolean later.
        good = len(functions)

        for f_item in args.operands:

            f = functions.get(f_item)
            if f is None:
                print_error("Could not find function: %s" % colour_text(f_item))
                good = False
                continue
            if f.arn in self.targets:
                continue # All checks for the function have already been done.

            self.targets[f.arn] = f

            # Function exists. Check its aliases.
            while True:
                try:
                    f.aliases = {a["Name"]:LambdaAlias(a["Name"], a["FunctionVersion"]) for a in self.client.list_aliases(FunctionName=f.arn)["Aliases"]}
                except Exception as e:
                    print_error("Unable to retrieve aliases for function '%s': %s" % (colour_text(f.arn), str(e)))
                    good = False
                    break
                f.aliases["__self__"] = LambdaAlias("__self__", f.version) # For convenience, store a 'no alias' under aliases
                alias = f.aliases.get(args[TITLE_ALIAS]) # Convenient shorthand.

                if alias is None:
                    print_error("Unable to find a %s alias for function: %s" % (colour_text(args[TITLE_ALIAS]), f.arn))
                    good = False
                break

            # Alias was found.

            if not args[TITLE_LATEST]:
                # If we are not just pinning to $LATEST, then we need to get versions.
                # $LATEST can be relied upon to exist, so lets save ourselves an API call if we can help it.

                # For pinning the most recent version, we need this to determine the version.
                # For pinning to a specific version, we need this to verify that such a version exists.

                while True:
                    try:
                        # Get all version names. Except for $LATEST, which is so common that it is assumed.
                        f.versions = {v["Version"] : LambdaVersion(v["Version"], v["CodeSha256"]) for v in self.client.list_versions_by_function(FunctionName=f.arn)["Versions"]}
                    except Exception as e:
                        print_error("Unable to retrieve versions for function '%s': %s" % (colour_text(f.arn), str(e)))
                        good = False
                        break

                    if len(f.versions) > 1:
                        f.latest_version = [v for v in f.versions if v != "$LATEST"][-1]
                        if args[TITLE_PIN_RECENT_VERSION]:
                            f.target_version = f.latest_version
                    elif not args[TITLE_CREATE_VERSION] and args[TITLE_PIN_RECENT_VERSION]:
                        # No versions defined, and we won't be making one to pin to the most recent one
                        print_error("No versions defined for function (and we are not creating one in this script): %s" % colour_text(f.arn))
                        good = False

                    if TITLE_VERSION in args:
                        t = args[TITLE_VERSION] # Convenient shorthand
                        if t not in f.versions and t != "$LATEST":
                            print_error("Version '%s' not found for function: %s" % (colour_text(t), colour_text(f.arn)))
                            good = False

                    break

        return good

    def pin_alias(self, target):
        good = True

        c_alias = colour_text("%s:%s" % (target.arn, args[TITLE_ALIAS]))
        c_version = colour_text(target.target_version)

        if target.target_version == target.aliases[args[TITLE_ALIAS]].version:
            print_notice("Function %s is already pinned to version '%s'" % (c_alias, c_version))
            return True

        try:
            self.client.update_alias(FunctionName = target.arn, Name = args[TITLE_ALIAS], FunctionVersion = target.target_version)
            print_notice("Pinned alias %s to version '%s'" % (c_alias, c_version))
        except Exception as e:
            print_error("Unable to pin %s to version '%s': %s" % (c_alias, c_version, str(e)))
            good = False
        return good

    def run(self):
        if not self.get_lambda_functions():
            exit(1)

        good = True
        for key in self.targets:
            target = self.targets[key]

            if args[TITLE_CREATE_VERSION] and not self.create_version(target):
                good = False
                continue

            good = self.pin_alias(target) and good

        return good


def validate_apply_pin_create(self):
    if self[TITLE_CREATE_PIN]:
        self[TITLE_PIN_RECENT_VERSION] = True
        self[TITLE_CREATE_VERSION] = True

def validate_check_alias(self):
    if not self[TITLE_ALIAS]:
        return "No alias specified."

def validate_check_conflicts(self):
    ret = []

    if self[TITLE_PIN_RECENT_VERSION] and self[TITLE_LATEST]:
        ret.append("Cannot pin to both the most recent version and $LATEST.")
    if self[TITLE_LATEST] and TITLE_VERSION in self and self[TITLE_VERSION] != "$LATEST":
        ret.append("Cannot pin to both a specific version and $LATEST")

    # A remaining conflict is "pin to most recent version and a version that is not the most recent version".
    # Technically, we could wait until API checks to see if there's a match, but that would involve a bunch of
    #   edge case handling that I didn't want to deal with. Easier to just tell the user to pick one or the other.

    if self[TITLE_PIN_RECENT_VERSION] and TITLE_VERSION in self:
        ret.append("Cannot pin to both a specific version and the most recent version")

    if self[TITLE_CREATE_VERSION]:
        if self[TITLE_VERSION]:
            ret.append("Cannot create a version while pinning a specific version.")
        if self[TITLE_LATEST]:
            ret.append("Cannot create a version while pinning to $LATEST.")

    # Though this method mostly checks for conflicts, we must also specify at least ONE pin method.
    if not [t for t in [TITLE_VERSION, TITLE_LATEST, TITLE_PIN_RECENT_VERSION] if t in self.args]:
        ret.append("Must specify at least one pinning method (-l, -r, or -v <version>).")

    return ret

def validate_check_function(self):
    if not self.operands:
        return "No function names specified."

def validate_check_version(self):
    v = v_orig = self[TITLE_VERSION]

    if v is None:
        return # The user never asked for a specific version.

    v = v.upper().strip()

    # Give the user the benefit of the doubt by accepting a
    # few alternate words for latest code than $LATEST.
    if v in ("LATEST"):
        v = "$LATEST"

    self[TITLE_VERSION] = v

    ret = []

    if not (re.match("^\d+$", v) or v == "$LATEST"):
        ret.append("Invalid version (pin to an integer or $LATEST): %s" % colour_text(v_orig))

    if len(self.operands) > 1:
        ret.append("Can only specify one function at a time when pinning to a specific version.")


    return ret

# Initialize arguments

TITLE_ALIAS = "alias"
TITLE_CREATE_VERSION = "create-version"
TITLE_PIN_RECENT_VERSION = "pin-recent-version"
TITLE_CREATE_PIN = "create-pin"
TITLE_LATEST = "latest"
TITLE_VERSION = "specific-version"
TITLE_DESCRIPTION = "description"

# This is an example implementation.
# See the add_opt and process methods for a listing of arguments.
args = ArgHelper()
args.add_opt(OPT_TYPE_FLAG, "c", TITLE_CREATE_VERSION, "Create a new version. If $LATEST is already up to date, no error will be thrown.")
args.add_opt(OPT_TYPE_FLAG, "l", TITLE_LATEST, "Pin function to $LATEST")
args.add_opt(OPT_TYPE_FLAG, "p", TITLE_CREATE_PIN, "Attempt to create a new version of function(s), then the latest version. Equivalent to -cr")
args.add_opt(OPT_TYPE_FLAG, "r", TITLE_PIN_RECENT_VERSION, "Attempt to pin the alias(es) new version of function(s) to the most recent version.")
args.add_opt(OPT_TYPE_SHORT, "a", TITLE_ALIAS, "Function alias to pin to. Must exist for all functions being pinned.")
args.add_opt(OPT_TYPE_SHORT, "d", TITLE_DESCRIPTION, "Description for newly-created function versions.")
args.add_opt(OPT_TYPE_SHORT, "v", TITLE_VERSION, "Pin function to a specific version. Can only apply to a single function at a time.")
args.add_validator(validate_apply_pin_create)
args.add_validator(validate_check_function)
args.add_validator(validate_check_alias)
args.add_validator(validate_check_version)
args.add_validator(validate_check_conflicts)
args.set_operand_help_text("function-name [function-name...]")

try:
    import boto3
except ImportError:
    args.errors.append("Could not import %s module." % colour_text("boto3"))

if __name__ == "__main__":
    args.process(sys.argv)

    if not LambdaPinner().run():
        exit(0)
