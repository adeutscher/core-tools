#!/usr/bin/python

import common, unittest

mod = common.load('update_dotfile', common.TOOLS_DIR + '/scripts/system/update_dotfile.py')

'''
Tests involving the resolve method of the DotFileUpdater class.
'''
class DotFileUpdaterResolveTests(common.TestCase):
    def setUp(self):
        self.updater = mod.DotFileUpdater(environ={})

    '''
    Confirm that trying to load a non-dictionary into system variables won't blow things up.
    '''
    def test_load_nondict_sysvar(self):
        self.updater.load_system_variables('not-dictionary')

    '''
    Confirm that trying to load a non-dictionary into custom variables won't blow things up.
    '''
    def test_load_nondict_variables(self):
        self.updater.load_variables('not-dictionary')

    '''
    Confirm what happens on a partial success with a missing custom variable.
    '''
    def test_partial_custom(self):

        raw = ' #{token}# #[token]# '

        environ = {
            'token': 'A'
        }
        self.updater.set_environ(environ)

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual('  A ', content)

        # Failed to resolve OS token
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual('#{token}#', unresolved_raw)
        self.assertEqual('token', unresolved_label)

    '''
    Confirm what happens on a partial success with a missing custom variable.
    '''
    def test_partial_custom_debug(self):

        raw = ' #{token}# #[token]# '

        environ = {
            'token': 'A'
        }
        self.updater.debug = True
        self.updater.set_environ(environ)

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' #{token}# A ', content)

        # Failed to resolve OS token
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual('#{token}#', unresolved_raw)
        self.assertEqual('token', unresolved_label)

    '''
    Confirm what happens on a partial success with a missing environment variable.
    '''
    def test_partial_os(self):

        raw = ' #{token}# #[token]# '


        self.updater.add_variable('token', 'B')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' B  ', content)

        # Failed to resolve OS token
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual('#[token]#', unresolved_raw)
        self.assertEqual('token', unresolved_label)

    '''
    Confirm what happens on a partial success with a missing environment variable.
    '''
    def test_partial_os_debug(self):

        raw = ' #{token}# #[token]# '

        self.updater.debug = True
        self.updater.add_variable('token', 'B')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' B #[token]# ', content)

        # Failed to resolve OS token
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual('#[token]#', unresolved_raw)
        self.assertEqual('token', unresolved_label)

    '''
    Confirm what happens on a partial success with a missing system variable.
    '''
    def test_partial_sysvar(self):

        raw = ' #{token}# #<token># '


        self.updater.add_variable('token', 'B')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' B  ', content)

        # Failed to resolve OS token
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual('#<token>#', unresolved_raw)
        self.assertEqual('token', unresolved_label)

    '''
    Confirm what happens on a partial success with a missing system variable.
    '''
    def test_partial_sysvar_debug(self):

        raw = ' #{token}# #<token># '

        self.updater.debug = True
        self.updater.add_variable('token', 'B')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' B #<token># ', content)

        # Failed to resolve OS token
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual('#<token>#', unresolved_raw)
        self.assertEqual('token', unresolved_label)

    '''
    Basic success test of all 3 types of token.
    '''
    def test_success_all(self):

        raw = ' #{one}# #[two]# #<three># '

        environ = {
            'two': '2'
        }
        self.updater.set_environ(environ).add_variable('one', '1')
        self.updater.load_system_variables({'three': 3})

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' 1 2 3 ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

    '''
    Demonstrate using a fallback variable value
    '''
    def test_success_fallback(self):

        raw = ' #{one}# #{two,fallback}# #{fallback,two}# '

        self.updater.add_variable('one', '1')
        self.updater.add_variable('fallback', 'final')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' 1 final final ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

    '''
    Demonstrate using a fallback variable value, with the first value being a server name that is not set.
    '''
    def test_success_fallback_os(self):

        raw = ' #{one}# #{#[hostname]#,fallback}# #{fallback,two}# '

        data = {
            'hostname': 'the-server'
        }
        self.updater.environ = data
        self.updater.add_variable('one', '1')
        self.updater.add_variable('fallback', 'default')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' 1 default default ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

    '''
    Demonstrate using a fallback variable value, with the first value being a server name that is not set.
    '''
    def test_success_fallback_os(self):

        raw = ' #{one}# #{#[hostname]#,fallback}# #{fallback,two}# '

        data = {
            'hostname': 'the-server'
        }
        self.updater.environ = data
        self.updater.add_variable('one', '1')
        self.updater.add_variable('fallback', 'default')
        self.updater.add_variable('the-server', 'special-value')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' 1 special-value default ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

    '''
    Success check that confirms that no token type is drawing from the wrong source
    '''
    def test_success_mix(self):

        raw = ' #{token}# #[token]# '

        environ = {
            'token': 'A'
        }
        self.updater.set_environ(environ).add_variable('token', 'B')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' B A ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

    '''
    Basic success test of specifically using an environment variable.
    '''
    def test_success_type_os(self):

        raw = ' #[token]# '

        self.updater.set_environ({'token': 'value-subbed'})

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' value-subbed ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

    '''
    Basic success test of specifically using a sysvar.
    '''
    def test_success_type_sysvar(self):

        raw = ' #<token># '

        self.updater.add_system_variable('token', 'value-subbed')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' value-subbed ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

    '''
    Basic success test of specifically set variables.
    '''
    def test_success_type_var(self):

        raw = ' #{token}# '

        self.updater.add_variable('token', 'value-subbed')

        content, unresolved = self.updater.resolve(raw)

        self.assertEqual(' value-subbed ', content)

        # No unresolved items
        self.assertEmpty(unresolved)

'''
Low-level tests of resolve() function.
'''
class ResolveTests(common.TestCase):

    def test_substitute_curly_success_full(self):
        pattern = r'#{([^}]+)}#'

        raw = ' #{abc}# '

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = mod.resolve(raw, data, pattern)

        # Resolved all items
        self.assertEmpty(unresolved)

        self.assertEqual(' Substituted ', content)

    def test_substitute_curly_success_partial_1(self):
        pattern = r'#{([^}]+)}#'

        raw = ' #{abc}# #{nope}#'

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = mod.resolve(raw, data, pattern)

        self.assertEqual(' Substituted #{nope}#', content)

        # Failed to resolve one item
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual(1, unresolved_count)
        self.assertEqual(unresolved_label, 'nope')

    def test_substitute_curly_success_partial_2(self):
        pattern = r'#{([^}]+)}#'

        raw = ' #{nope}# #{abc}# '

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = mod.resolve(raw, data, pattern)

        self.assertEqual(' #{nope}# Substituted ', content)

        # Failed to resolve one item
        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual(1, unresolved_count)
        self.assertEqual(unresolved_label, 'nope')

    def test_substitute_square_success_full(self):
        pattern = r'#\[([^\]]+)\]#'

        raw = ' #[abc]# '

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = mod.resolve(raw, data, pattern)

        # Didn't fail to resolve any items
        self.assertEmpty(unresolved)
        self.assertEqual(' Substituted ', content)

    def test_substitute_square_success_partial_1(self):
        pattern = r'#\[([^\]]+)\]#'

        raw = ' #[abc]# #[nope]#'

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = mod.resolve(raw, data, pattern)

        self.assertEqual(' Substituted #[nope]#', content)

        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual(1, unresolved_count)
        self.assertEqual(unresolved_label, 'nope')

    def test_substitute_square_success_partial_2(self):
        pattern = r'#\[([^\]]+)\]#'

        raw = ' #[nope]# #[abc]# '

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = mod.resolve(raw, data, pattern)

        self.assertEqual(' #[nope]# Substituted ', content)

        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual(1, unresolved_count)
        self.assertEqual(unresolved_label, 'nope')
