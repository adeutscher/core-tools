#!/usr/bin/env python

import common, unittest
import io, json, os
from tempfile import TemporaryDirectory as tempdir

class BaseUpdateTestCase(common.TestCase):
    def setUp(self):
        self.mod = common.load('update_dotfile', common.TOOLS_DIR + '/scripts/system/update_dotfile.py')
        self.updater = self.mod.DotFileUpdater(environ={})
        self.olddir = os.getcwd()

    def tearDown(self):
        os.chdir(self.olddir)

class DotFileUpdaterCommandTests(BaseUpdateTestCase):

    def test_basic_replace(self):
        with tempdir() as td:

            dst = os.path.join(td, 'dst-file')
            src = os.path.join(td, 'src-file')
            contents = 'abcde'
            contents_dst = '1234'

            marker = 'demo-marker'

            with open(src, 'w') as f:
                f.write(contents)

            with open(dst, 'w') as f:
                f.write(contents_dst)

            cmd = ['-o', dst, '-i', marker, '-f', src]
            exit_code = self.mod.main(cmd)
            self.assertEqual(0, exit_code)

            with open(dst, 'r') as f:
                contents_modified = f.read()

            self.assertStartsWith(contents_dst, contents_modified)
            self.assertContains(contents, contents_modified)
            self.assertContains(f'marker:{marker} checksum:', contents_modified)
            self.assertContains(f'end:{marker}', contents_modified)

    def test_config_variable(self):
        with tempdir() as td:

            dst = os.path.join(td, 'dst-file')
            src = os.path.join(td, 'src-file')
            config = os.path.join(td, 'config.json')

            var_key='my_token'
            var_content='the_contents'
            contents = '---#{my_token}#---'
            contents_expected = f'---{var_content}---'
            contents_dst = '1234'

            marker = 'demo-marker'

            with open(src, 'w') as f:
                f.write(contents)

            config_data={'variables': {var_key: var_content}}

            with open(config, 'w') as f:
                json.dump(config_data, f)

            with open(dst, 'w') as f:
                f.write(contents_dst)

            cmd = ['-o', dst, '-i', marker, '-f', src, '-c', config]
            exit_code = self.mod.main(cmd)
            self.assertEqual(0, exit_code)

            with open(dst, 'r') as f:
                contents_modified = f.read()

            self.assertStartsWith(contents_dst, contents_modified)
            self.assertContains(contents_expected, contents_modified)
            self.assertDoesNotContain(var_key, contents_modified)
            self.assertContains(f'marker:{marker} checksum:', contents_modified)
            self.assertContains(f'end:{marker}', contents_modified)

    '''
    Test with stdin, or at least as close to it as we can get.
    '''
    def test_stdin(self):
        with tempdir() as td:

            dst = os.path.join(td, 'dst-file')
            contents = 'abcde'
            contents_dst = '1234'

            marker = 'demo-marker'

            with open(dst, 'w') as f:
                f.write(contents_dst)

            cmd = ['-o', dst, '-i', marker, '-f', '-']
            with io.StringIO(contents) as s:
                kwargs={'stream_input': s}
                exit_code = self.mod.main(cmd, **kwargs)
            self.assertEqual(0, exit_code)

            with open(dst, 'r') as f:
                contents_modified = f.read()

            self.assertStartsWith(contents_dst, contents_modified)
            self.assertContains(contents, contents_modified)
            self.assertContains(f'marker:{marker} checksum:', contents_modified)
            self.assertContains(f'end:{marker}', contents_modified)

class DotFileUpdaterCommandErrorTests(BaseUpdateTestCase):

    def test_config_bad_json(self):
        with tempdir() as td:
            path = os.path.join(td, 'a.json')
            with open(path, 'w') as f:
                f.write('{')
            self.assertEqual(1, self.mod.main(['-c', path]))

    def test_config_no_such_file(self):
        with tempdir() as td:
            path = os.path.join(td, 'a')
            self.assertEqual(1, self.mod.main(['-c', path]))

    '''
    Confirm behavior for running with no arguments.

    The script shouldn't like it, and should return an error.
    '''
    def test_no_args(self):
        self.assertEqual(1, self.mod.main([]))

'''
Tests involving the resolve method of the DotFileUpdater class.
'''
class DotFileUpdaterResolveTests(BaseUpdateTestCase):

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
    def test_success_fallback_os_1(self):

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
    def test_success_fallback_os_2(self):

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
class ResolveTests(BaseUpdateTestCase):

    def test_substitute_curly_success_full(self):
        pattern = r'#{([^}]+)}#'

        raw = ' #{abc}# '

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = self.mod.resolve(raw, data, pattern)

        # Resolved all items
        self.assertEmpty(unresolved)

        self.assertEqual(' Substituted ', content)

    def test_substitute_curly_success_partial_1(self):
        pattern = r'#{([^}]+)}#'

        raw = ' #{abc}# #{nope}#'

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = self.mod.resolve(raw, data, pattern)

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

        content, unresolved = self.mod.resolve(raw, data, pattern)

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

        content, unresolved = self.mod.resolve(raw, data, pattern)

        # Didn't fail to resolve any items
        self.assertEmpty(unresolved)
        self.assertEqual(' Substituted ', content)

    def test_substitute_square_success_partial_1(self):
        pattern = r'#\[([^\]]+)\]#'

        raw = ' #[abc]# #[nope]#'

        data = {
            'abc': 'Substituted'
        }

        content, unresolved = self.mod.resolve(raw, data, pattern)

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

        content, unresolved = self.mod.resolve(raw, data, pattern)

        self.assertEqual(' #[nope]# Substituted ', content)

        unresolved_label, unresolved_raw, unresolved_count = self.assertSingle(unresolved)
        self.assertEqual(1, unresolved_count)
        self.assertEqual(unresolved_label, 'nope')
