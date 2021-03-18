#!/usr/bin/env python

import common

class ArgumentHandlingTests(common.TestCase):

    def setUp(self):
        self.mod = common.load('argument_handling', common.TOOLS_DIR + '/scripts/clipboard/python/argument_handling.py')
        self.mod.colour_text = lambda m,c = None: m
        self.mod._print_message = lambda c,h,m: self.lines.append(('[%s] %s' % (h, m)).strip())
        self.mod.COLOUR_PURPLE = '-purple-'

        self.lines = []
        self.mod.print = lambda l: self.lines.append(l.strip())

        self.errors = []
        self.mod.print_error = lambda e: self.errors.append(e.strip())

    def test_bool_flag_false(self):

        for name in ['bool', 'other-value']:
            args = self.mod.ArgHelper()
            args.add_opt(self.mod.OPT_TYPE_FLAG, 'b', name, 'A boolean flag.')

            args.process([])
            self.assertFalse(args[name])
            self.assertFalse(name in args)

            self.assertEmpty(self.errors)
            self.assertEmpty(self.lines)

    def test_bool_flag_true(self):

        for name in ['bool', 'other-value']:
            args = self.mod.ArgHelper()
            args.add_opt(self.mod.OPT_TYPE_FLAG, 'b', name, 'A boolean flag.')

            args.process(['-b'])
            self.assertTrue(args[name])
            self.assertTrue(name in args)

            self.assertEmpty(self.errors)
            self.assertEmpty(self.lines)

    def test_bool_longflag_false(self):

        for flag in ['long', 'another']:
            for name in ['bool', 'other-value']:
                args = self.mod.ArgHelper()
                args.add_opt(self.mod.OPT_TYPE_LONG_FLAG, 'b', name, 'A boolean flag.')

                args.process([])
                self.assertFalse(args[name])

                self.assertEmpty(self.errors)
                self.assertEmpty(self.lines)

    def test_bool_longflag_true(self):
        for flag in ['long', 'another']:
            for name in ['bool', 'other-value']:
                args = self.mod.ArgHelper()
                args.add_opt(self.mod.OPT_TYPE_LONG_FLAG, flag, name, 'A boolean flag.')

                args.process(['--' + flag])
                self.assertTrue(args[name])

                self.assertEmpty(self.errors)
                self.assertEmpty(self.lines)

    def test_int_value_conversion(self):

        for label in ['int-value', 'another-value']:
            for i in ['nope', 'not-a-number']:

                self.errors = []

                args = self.mod.ArgHelper()
                args.add_opt(self.mod.OPT_TYPE_SHORT, 'a', label, 'An example integer that takes an argument.', converter=int, default = 0)

                with self.assertRaises(SystemExit) as ex:
                    args.process(['-a', i])
                self.assertEqual(ex.exception.code, 1)

                e = self.assertSingle(self.errors)
                self.assertEqual('Unable to convert %s to int: %s' % (label, i), e)

                self.assertEmpty(self.lines)

    def test_error_single(self):
        for label in ['string-single', 'other']:

            self.errors = []

            args = self.mod.ArgHelper()
            args.add_opt(self.mod.OPT_TYPE_SHORT, 's', label, 'A short arg that insists on a single argument.', strict_single = True)

            with self.assertRaises(SystemExit) as ex:
                args.process(['-s', 'a', '-s', 'b'])
            self.assertEqual(ex.exception.code, 1)

            e = self.assertSingle(self.errors)
            self.assertEqual('Cannot have multiple %s values.' % label, e)
            self.assertEmpty(self.lines)

    def test_help_exit(self):

        for code in [0,1,2]:

            args = self.mod.ArgHelper()

            with self.assertRaises(SystemExit) as ex:
                args.hexit(code)
            self.assertEqual(code, ex.exception.code)

            self.assertStartsWith('[Usage] ', self.lines[0])
            self.assertEndsWith('[-h]', self.lines[0])
            self.assertEqual('-h: Display a help menu and then exit.', self.lines[-1])

    def test_help_exit_default(self):



        args = self.mod.ArgHelper()

        with self.assertRaises(SystemExit) as ex:
            args.hexit()
        self.assertEqual(0, ex.exception.code)

        self.assertStartsWith('[Usage] ', self.lines[0])
        self.assertEndsWith('[-h]', self.lines[0])
        self.assertEqual('-h: Display a help menu and then exit.', self.lines[-1])

    def test_help_no_exit(self):

        args = self.mod.ArgHelper()
        args.hexit(-1)

        self.assertStartsWith('[Usage] ', self.lines[0])
        self.assertEndsWith('[-h]', self.lines[0])
        self.assertEqual('-h: Display a help menu and then exit.', self.lines[-1])

    def test_int_value_multi(self):

        for case in [
            [1,2,3,4],
            [2],
            [5,6,7],
            [1,1,2,2]
        ]:
            opts = []
            for c in case:
                opts.extend(['-i', str(c)])
            self.assertEqual(len(case) * 2, len(opts))

            args = self.mod.ArgHelper()
            args.add_opt(self.mod.OPT_TYPE_SHORT, 'i', 'int-multiple', 'An example integer that takes multiple values.', converter=int, multiple = True)

            args.process(opts)
            value = args['int-multiple']
            self.assertTrue(type(value) is list)
            self.assertEqual(len(case), len(value))
            for c in case:
                self.assertContains(c, value)
            self.assertEqual(case, value)

    def test_int_value_multi_empty(self):

        args = self.mod.ArgHelper()
        args.add_opt(self.mod.OPT_TYPE_SHORT, 'i', 'int-multiple', 'An example integer that takes multiple values.', converter=int, multiple = True)

        args.process([])
        value = args['int-multiple']
        self.assertTrue(type(value) is list)
        self.assertEmpty(value)

    def test_int_value_single(self):

        args = self.mod.ArgHelper()
        args.add_opt(self.mod.OPT_TYPE_SHORT, 'a', 'int-value', 'An example integer that takes an argument.', converter=int, default = 0)

        for i in [5, 2, 1, -2]:
            args.process(['-a', str(i)])
            self.assertEqual(i, args['int-value'])

        self.assertEmpty(self.errors)
        self.assertEmpty(self.lines)

    def test_int_value_single_default(self):

        for d in [0,2,3,4]:
            args = self.mod.ArgHelper()
            args.add_opt(self.mod.OPT_TYPE_SHORT, 'a', 'int-value', 'An example integer that takes an argument.', converter=int, default = d)

            args.process([])
            self.assertEqual(d, args['int-value'])

            self.assertEmpty(self.errors)
            self.assertEmpty(self.lines)

    def test_int_value_overwrite(self):

        args = self.mod.ArgHelper()
        args.add_opt(self.mod.OPT_TYPE_SHORT, 'a', 'int-value', 'An example integer that takes an argument.', converter=int, default = 0)

        for i in [5, 2, 1, -2]:
            args.process(['-a', '0', '-a', str(i)])
            self.assertEqual(i, args['int-value'])

        self.assertEmpty(self.errors)
        self.assertEmpty(self.lines)

    def test_int_value_single_nodefault(self):

        args = self.mod.ArgHelper()
        args.add_opt(self.mod.OPT_TYPE_SHORT, 'a', 'int-value', 'An example integer that takes an argument.', converter=int)

        args.process([])
        self.assertNone(args['int-value'])

        self.assertEmpty(self.errors)
        self.assertEmpty(self.lines)

    def test_string_plus_operands(self):
        for operands in [['aaa','bbb','ccc']]:
            for value in ['a','b','c','d']:
                for flag in ['a','b','c','d']:
                    for label in ['a','b','c','d']:
                        args = self.mod.ArgHelper()
                        args.add_opt(self.mod.OPT_TYPE_SHORT, flag, label, 'A string value.')

                        args.process(operands + ['-' + flag, value])

                        self.assertEqual(value, args[label])
                        self.assertEqual(operands, args.operands)

                        self.assertEqual(operands[-1], args.last_operand('DEFAULT'))

                        self.assertEmpty(self.errors)
                        self.assertEmpty(self.lines)

    def test_string_plus_operands_default(self):
        for default in ['DEFAULT', 'another-default']:
            for value in ['a','b','c','d']:
                for flag in ['a','b','c','d']:
                    for label in ['a','b','c','d']:
                        args = self.mod.ArgHelper()
                        args.add_opt(self.mod.OPT_TYPE_SHORT, flag, label, 'A string value.')

                        args.process(['-' + flag, value])

                        self.assertEqual(value, args[label])

                        self.assertEqual(default, args.last_operand(default))

                        self.assertEmpty(self.errors)
                        self.assertEmpty(self.lines)

    def test_string(self):
        for value in ['a','b','c','d']:
            for flag in ['a','b','c','d']:
                for label in ['a','b','c','d']:
                    args = self.mod.ArgHelper()
                    args.add_opt(self.mod.OPT_TYPE_SHORT, flag, label, 'A string value.')

                    args.process(['-' + flag, value])
                    self.assertEqual(value, args[label])

                    self.assertEmpty(self.errors)
                    self.assertEmpty(self.lines)

    def test_string_long(self):
        for value in ['a','b','c','d']:
            for flag in ['a','b','c','d','aa','bb','cc','dd']:
                for label in ['a','b','c','d']:
                    args = self.mod.ArgHelper()
                    args.add_opt(self.mod.OPT_TYPE_LONG, flag, label, 'A string value.')

                    args.process(['--' + flag, value])
                    self.assertEqual(value, args[label])

                    self.assertEmpty(self.errors)
                    self.assertEmpty(self.lines)
