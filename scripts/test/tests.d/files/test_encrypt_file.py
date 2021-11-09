#!/usr/bin/env python

import common, unittest
import io, os, tempfile, sys

from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend

mod = common.load('encrypt_file', common.TOOLS_DIR + '/scripts/files/encrypt_file.py')

class MockWrapper(mod.CommandWrapper):
    def __init__(self):
        super().__init__()

        self.errors = []
        self.notices = []
        self.environ = {}

    def log_error(self, msg):
        self.errors.append(msg)

    def log_notice(self, msg):
        self.notices.append(msg)

'''
Tests involving my RSA encryption wrapper
'''
class RSAWrapperTests(common.TestCase):

    def setUp(self):
        self.wrapper = MockWrapper()

    def make_keypair(self, directory, label):

        path_private_key = os.path.join(directory, '%s.rsa.private' % label)
        path_public_key = os.path.join(directory, '%s.rsa.public' % label)

        key = rsa.generate_private_key(
            backend=crypto_default_backend(),
            public_exponent=65537,
            key_size=2048
        )

        private_key = key.private_bytes(
            crypto_serialization.Encoding.PEM,
            crypto_serialization.PrivateFormat.PKCS8,
            crypto_serialization.NoEncryption()
        )

        with open(path_private_key, 'wb') as f:
            f.write(private_key)

        public_key = key.public_key().public_bytes(
            crypto_serialization.Encoding.PEM,
            crypto_serialization.PublicFormat.PKCS1
        )

        with open(path_public_key, 'wb') as f:
            f.write(public_key)

        return path_public_key, path_private_key

    def assertFail(self, **kwargs):
        self.assertEqual(1, self.wrapper.run(**kwargs))


    def assertSuccess(self, **kwargs):
        try:
            self.assertEqual(0, self.wrapper.run(**kwargs))
        except:
            print(self.wrapper.errors)
            raise
        self.assertEmpty(self.wrapper.errors)

    def test_check_required_file_fail_no_exist(self):

        label = 'MY LABEL'
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'nope')
            self.assertFalse(self.wrapper.check_required_file(label, path))
        error = self.assertSingle(self.wrapper.errors)
        self.assertStartsWith('%s ' % label, error)
        self.assertContains('does not exist', error)
        self.assertEndsWith(path, error)

    def test_check_required_file_fail_not_provided(self):

        label = 'MY LABEL'
        self.assertFalse(self.wrapper.check_required_file(label, ''))
        error = self.assertSingle(self.wrapper.errors)
        self.assertEqual('%s not provided.' % label, error)

    def test_check_required_file_pass_dash(self):

        self.assertTrue(self.wrapper.check_required_file('moot', '-'))
        self.assertEmpty(self.wrapper.errors)

    def test_error_ambiguous(self):
        run_kwargs = {
            'args': ['-d', '-e']
        }

        self.assertFail(**run_kwargs)
        self.assertContains('Ambiguous arguments, unsure whether we want to encrypt or decrypt.', self.wrapper.errors)

    def test_load_keyfile_private_error(self):

        label = 'mylabel'

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'nope')

            self.assertFalse(self.wrapper.load_keyfile_private(label, path, None))
            error = self.assertSingle(self.wrapper.errors)
            self.assertContains('does not exist', error)
            self.assertEndsWith(path, error)

    def test_load_keyfile_private_error_env(self):

        label = 'mylabel'

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'nope')
            self.wrapper.environ['PRIVATE'] = path

            self.assertFalse(self.wrapper.load_keyfile_private(label, path, 'PRIVATE'))
            error = self.assertSingle(self.wrapper.errors)
            self.assertContains('does not exist', error)
            self.assertContains('environment variable', error)
            self.assertEndsWith(path, error)

    def test_load_keyfile_public_error(self):

        label = 'mylabel'

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'nope')

            self.assertFalse(self.wrapper.load_keyfile_public(label, path, None))
            error = self.assertSingle(self.wrapper.errors)
            self.assertContains('does not exist', error)
            self.assertEndsWith(path, error)

    def test_load_keyfile_public_error_env(self):

        label = 'mylabel'

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, 'nope')
            self.wrapper.environ['PUBLIC'] = path

            self.assertFalse(self.wrapper.load_keyfile_public(label, path, 'PUBLIC'))
            error = self.assertSingle(self.wrapper.errors)
            self.assertContains('does not exist', error)
            self.assertContains('environment variable', error)
            self.assertEndsWith(path, error)

    '''
    Confirm that we can encrypt and decrypt a file using paths using the outermost main() function
    '''
    def test_main_encrypt_and_decrypt(self):

        contents = b"THIS IS MY FILE CONTENT"

        with tempfile.TemporaryDirectory() as td:

            path_raw = os.path.join(td, 'raw')
            path_enc = os.path.join(td, 'enc')
            path_out = os.path.join(td, 'out')

            with open(path_raw, 'wb') as f:
                f.write(contents)

            public, private = self.make_keypair(td, 'test')

            enc_args = ['--public', public, '-i', path_raw, '-o', path_enc]
            self.assertEqual(0, mod.main(enc_args, {}, MockWrapper))
            self.assertEmpty(self.wrapper.errors)
            self.assertEmpty(self.wrapper.notices)

            self.assertTrue(os.path.isfile(path_enc))
            with open(path_enc, 'rb') as stream_enc:
                enc = stream_enc.read()

                self.assertDoesNotContain(contents, enc)

            dec_args = ['--private', private, '-i', path_enc, '-o', path_out]
            self.assertEqual(0, mod.main(dec_args, {}, MockWrapper))
            self.assertEmpty(self.wrapper.errors)
            self.assertEmpty(self.wrapper.notices)

            with open(path_out, 'rb') as stream_out:
                out = stream_out.read()
                self.assertEqual(contents, out)

    def test_main_keyboard_interrupt(self):
        class KeyboardInterruptMockWrapper(MockWrapper):
            def run(self, **kwargs):
                raise KeyboardInterrupt()

        wrapper = KeyboardInterruptMockWrapper()
        self.assertEqual(130, mod.main([], {}, KeyboardInterruptMockWrapper))

    def test_make_keypair(self):

        with tempfile.TemporaryDirectory() as td:
            public, private = self.make_keypair(td, 'test')

            with open(private, 'r') as f:
                contents = f.read()
                self.assertContains('-BEGIN PRIVATE KEY-', contents)

            with open(public, 'r') as f:
                contents = f.read()
                self.assertContains('-BEGIN RSA PUBLIC KEY-', contents)

    def test_run_encrypt_single(self):

        contents = b"THIS IS MY FILE CONTENT"

        with tempfile.TemporaryDirectory() as td:

            path_raw = os.path.join(td, 'raw')
            path_enc = os.path.join(td, 'enc')

            with open(path_raw, 'w') as f:
                f.write(path_raw)

            public, private = self.make_keypair(td, 'test')

            wrapper_kwargs = {
                'args': ['--public', public, '-i', path_raw, '-o', path_enc]
            }

            self.assertSuccess(**wrapper_kwargs)
            self.assertEmpty(self.wrapper.notices)

            self.assertTrue(os.path.isfile(path_enc))
            with open(path_enc, 'rb') as enc_stream:
                enc = enc_stream.read()

                self.assertDoesNotContain(contents, enc)

    def test_run_encrypt_single_dash(self):

        contents = b"THIS IS MY FILE CONTENT"

        self.wrapper.get_stream_length = lambda stream: stream.getbuffer().nbytes

        with tempfile.TemporaryDirectory() as td:
            with io.BytesIO() as stream_raw:
                with io.BytesIO() as stream_enc:

                    stream_raw.write(contents)
                    stream_raw.seek(0, 0)

                    public, private = self.make_keypair(td, 'test')

                    wrapper_kwargs = {
                        'args': ['--public', public, '-i', '-', '-o', '-'],
                        'dashstream_in': stream_raw,
                        'dashstream_out': stream_enc
                    }

                    self.assertSuccess(**wrapper_kwargs)
                    self.assertEmpty(self.wrapper.notices)

                    stream_enc.seek(0, 0)
                    enc = stream_enc.read()

                    self.assertDoesNotContain(contents, enc)

    '''
    Confirm that we can encrypt and decrypt a file using paths.
    '''
    def test_run_encrypt_and_decrypt(self):

        contents = b"THIS IS MY FILE CONTENT"

        with tempfile.TemporaryDirectory() as td:

            path_raw = os.path.join(td, 'raw')
            path_enc = os.path.join(td, 'enc')
            path_out = os.path.join(td, 'out')

            with open(path_raw, 'wb') as f:
                f.write(contents)

            public, private = self.make_keypair(td, 'test')

            enc_kwargs = {
                'args': ['--public', public, '-i', path_raw, '-o', path_enc]
            }
            self.assertSuccess(**enc_kwargs)
            self.assertEmpty(self.wrapper.notices)

            self.assertTrue(os.path.isfile(path_enc))
            with open(path_enc, 'rb') as stream_enc:
                enc = stream_enc.read()

                self.assertDoesNotContain(contents, enc)

            dec_kwargs = {
                'args': ['--private', private, '-i', path_enc, '-o', path_out]
            }
            self.assertSuccess(**dec_kwargs)
            self.assertEmpty(self.wrapper.notices)

            with open(path_out, 'rb') as stream_out:
                out = stream_out.read()
                self.assertEqual(contents, out)

    '''
    Confirm that we can encrypt and decrypt a file using streams.
    '''
    def test_run_encrypt_and_decrypt_dash(self):

        contents = b"THIS IS MY FILE CONTENT"

        self.wrapper.get_stream_length = lambda stream: stream.getbuffer().nbytes

        with tempfile.TemporaryDirectory() as td:
            with io.BytesIO() as stream_raw:
                with io.BytesIO() as stream_enc:
                    with io.BytesIO() as stream_out:

                        stream_raw.write(contents)
                        stream_raw.seek(0, 0)

                        public, private = self.make_keypair(td, 'test')

                        wrapper_kwargs = {
                            'args': ['--public', public, '-i', '-', '-o', '-'],
                            'dashstream_in': stream_raw,
                            'dashstream_out': stream_enc
                        }

                        self.assertSuccess(**wrapper_kwargs)
                        self.assertEmpty(self.wrapper.notices)

                        stream_enc.seek(0, 0)
                        enc = stream_enc.read()
                        stream_enc.seek(0, 0)

                        self.assertDoesNotContain(contents, enc)

                        dec_kwargs = {
                            'args': ['--private', private, '-i', '-', '-o', '-'],
                            'dashstream_in': stream_enc,
                            'dashstream_out': stream_out
                        }
                        self.assertSuccess(**dec_kwargs)
                        self.assertEmpty(self.wrapper.notices)

                        stream_out.seek(0, 0)
                        out = stream_out.read()
                        self.assertEqual(contents, out)

    '''
    Confirm that we can encrypt and decrypt a file using streams and compression options.
    '''
    def test_run_encrypt_and_decrypt_dash_compression(self):

        contents = b"THIS IS MY FILE CONTENT THAT WILL BE COMPRESSED"

        self.wrapper.get_stream_length = lambda stream: stream.getbuffer().nbytes

        for compression in ['--gzip', '--bz2', '--lzma']:
            with tempfile.TemporaryDirectory() as td:
                with io.BytesIO() as stream_raw:
                    with io.BytesIO() as stream_enc:
                        with io.BytesIO() as stream_out:

                            stream_raw.write(contents)
                            stream_raw.seek(0, 0)

                            public, private = self.make_keypair(td, 'test')

                            enc_kwargs = {
                                'args': ['--public', public, '-i', '-', '-o', '-', compression],
                                'dashstream_in': stream_raw,
                                'dashstream_out': stream_enc
                            }

                            self.assertSuccess(**enc_kwargs)
                            self.assertEmpty(self.wrapper.notices)

                            stream_enc.seek(0, 0)
                            enc = stream_enc.read()
                            stream_enc.seek(0, 0)

                            self.assertDoesNotContain(contents, enc)

                            dec_kwargs = {
                                'args': ['--private', private, '-i', '-', '-o', '-'],
                                'dashstream_in': stream_enc,
                                'dashstream_out': stream_out
                            }
                            self.assertSuccess(**dec_kwargs)
                            self.assertEmpty(self.wrapper.notices)

                            stream_out.seek(0, 0)
                            out = stream_out.read()
                            self.assertEqual(contents, out)

    '''
    Confirm that we can encrypt and decrypt a file with public/private key paths set as environment variables.
    '''
    def test_run_encrypt_and_decrypt_dash_environment_keys(self):

        contents = b"THIS IS MY FILE CONTENT"

        self.wrapper.get_stream_length = lambda stream: stream.getbuffer().nbytes

        with tempfile.TemporaryDirectory() as td:
            with io.BytesIO() as stream_raw:
                with io.BytesIO() as stream_enc:
                    with io.BytesIO() as stream_out:

                        stream_raw.write(contents)
                        stream_raw.seek(0, 0)

                        public, private = self.make_keypair(td, 'test')

                        environ = {
                            'RSA_PUBLIC_KEY': public,
                            'RSA_PRIVATE_KEY': private
                        }

                        wrapper_kwargs = {
                            'args': ['-e', '-i', '-', '-o', '-'],
                            'dashstream_in': stream_raw,
                            'dashstream_out': stream_enc,
                            'environ': environ
                        }

                        self.assertSuccess(**wrapper_kwargs)
                        self.assertEmpty(self.wrapper.notices)

                        stream_enc.seek(0, 0)
                        enc = stream_enc.read()
                        stream_enc.seek(0, 0)

                        self.assertDoesNotContain(contents, enc)

                        dec_kwargs = {
                            'args': ['-d', '-i', '-', '-o', '-'],
                            'dashstream_in': stream_enc,
                            'dashstream_out': stream_out,
                            'environ': environ
                        }
                        self.assertSuccess(**dec_kwargs)
                        self.assertEmpty(self.wrapper.notices)

                        stream_out.seek(0, 0)
                        out = stream_out.read()
                        self.assertEqual(contents, out)

    '''
    Confirm that we can encrypt and decrypt a larger file stream.
    This larger file is greater than the size of a single cipherblock.
    '''
    def test_run_encrypt_and_decrypt_dash_large(self):

        contents = b"\nTHIS IS MY FILE CONTENT"
        i = 0
        while i < 10:
            contents += contents
            i += 1

        self.assertTrue(len(contents) > 5000)

        self.wrapper.get_stream_length = lambda stream: stream.getbuffer().nbytes

        with tempfile.TemporaryDirectory() as td:
            with io.BytesIO() as stream_raw:
                with io.BytesIO() as stream_enc:
                    with io.BytesIO() as stream_out:

                        stream_raw.write(contents)
                        stream_raw.seek(0, 0)

                        public, private = self.make_keypair(td, 'test')

                        wrapper_kwargs = {
                            'args': ['--public', public, '-i', '-', '-o', '-'],
                            'dashstream_in': stream_raw,
                            'dashstream_out': stream_enc
                        }

                        self.assertSuccess(**wrapper_kwargs)
                        self.assertEmpty(self.wrapper.notices)

                        stream_enc.seek(0, 0)
                        enc = stream_enc.read()
                        stream_enc.seek(0, 0)

                        self.assertDoesNotContain(contents, enc)

                        dec_kwargs = {
                            'args': ['--private', private, '-i', '-', '-o', '-'],
                            'dashstream_in': stream_enc,
                            'dashstream_out': stream_out
                        }
                        self.assertSuccess(**dec_kwargs)
                        self.assertEmpty(self.wrapper.notices)

                        stream_out.seek(0, 0)
                        out = stream_out.read()
                        self.assertEqual(contents, out)

    '''
    Test that we can convert a condensed hash to a more human readable form
    '''
    def test_translate_digest(self):

        # MD5 Checksum of 'hello-world'
        condensed = b' \x951!\x89u=\xe6\xadG\xdf\xe2\x0c\xbe\x97\xec'
        expected = '2095312189753de6ad47dfe20cbe97ec'

        # If you want to generate something new, do the following:
        # from hashlib import md5
        # m = md5()
        # m.update(b'hello-world')
        # print(m.digest(), m.hexdigest())

        self.assertEqual(expected, mod._translate_digest(condensed))
