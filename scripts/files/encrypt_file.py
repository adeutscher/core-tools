#!/usr/bin/env python

from base64 import b64decode
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from hashlib import md5, sha1, sha256, sha512
import bz2, gzip, lzma
import argparse, os, struct, sys

# Flags for extra info in inner content envelope
FLAG_MD5 = 0x01
FLAG_SHA1 = 0x02
FLAG_SHA256 = 0x04
FLAG_SHA512 = 0x08

# Flags for compression formats
FORMAT_FLAG_GZIP = 0x01
FORMAT_FLAG_BZ2 = 0x02
FORMAT_FLAG_LZMA = 0x04

# Note sizes of hashes
LEN_MD5 = 16
LEN_SHA1 = 20
LEN_SHA256 = 32
LEN_SHA512 = 64

class WriteWrapper(object):
    def __init__(self, dst, cipher, cipher_size):
        self.dst = dst

        self.cipher = cipher
        self.cipher_size = cipher_size

    def write(self, data):

        # Based on formula in https://crypto.stackexchange.com/questions/42097/what-is-the-maximum-size-of-the-plaintext-message-for-rsa-oaep
        # Subtract from the payload for the SHA256 checksum that we're adding in.
        plainSize = int(self.cipher_size - 2 * 160 / 8 - 32)

        while len(data) > 0:
            payload = data[:plainSize]
            data = data[plainSize:]
            cipher = self.cipher.encrypt(
                payload,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            self.dst.write(cipher)

class ReadWrapper(object):
    def __init__(self, src, cipher, cipher_size):
        self.src = src
        self.buffer = b''

        self.cipher = cipher
        self.cipher_size = cipher_size

    def read(self, size):

        while len(self.buffer) < size:
            data = self.src.read(self.cipher_size)
            if len(data) == 0:
                # Done
                break

            plain = self.cipher.decrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            payload = plain
            self.buffer += payload
        output = self.buffer[:size]
        self.buffer = self.buffer[size:]

        return output

def _get_hash_algorithms(flags):

    hashes = []

    # MD5
    if flags & FLAG_MD5:
        hashes.append(md5())
    # SHA1
    if flags & FLAG_SHA1:
        hashes.append(sha1())
    # SHA256
    if flags & FLAG_SHA256:
        hashes.append(sha256())
    # SHA512
    if flags & FLAG_SHA512:
        hashes.append(sha512())

    return hashes

def _read_in_chunks(**kwargs):
    """Read a file in fixed-size chunks (to minimize memory usage for large files).

    Args:
        file_object: An opened file-like object supporting read().
        max_length: Max amount of content to fetch from stream.
        chunk_size: Max size (in bytes) of each file chunk.

    Yields:
        File chunks, each of size at most chunk_size.
    """

    file_object = kwargs.get('file_object')
    chunk_size = kwargs.get('chunk_size', 2 * (2 ** 20))
    max_length = kwargs.get('max_length', -1)

    i = 0
    while max_length < 0 or i < max_length:

        if max_length > 0:
            chunk_size = min(chunk_size, max_length - i)

        chunk = file_object.read(chunk_size)
        i += len(chunk)

        if chunk:
            yield chunk
        else:
            return  # End of file.

def _translate_digest(digest):
    t = '' # Translated
    for d in digest:
        t += (hex(d >> 4) + hex(d & 0xf)).replace('0x', '')
    return t

class CommandWrapper:

    def __init__(self):
        self.cipher = None
        self.cipher_size = 0

    def check_required_file(self, label, path):
        if path == '-':
            # Standard input, automatically accept
            return True

        if not path:
            self.log_error('%s not provided.' % label)
            return False

        response = os.path.isfile(path)
        if not response:
            self.log_error('%s does not exist: %s' % (label, path))
        return response

    def do_pack(self, **kwargs):

        outputstream = kwargs.get('outputstream')
        inputstream = kwargs.get('inputstream')
        length = kwargs.get('length', self.get_stream_length(inputstream))
        flags = kwargs.get('flags', 0)
        format_flags = kwargs.get('format_flags', 0)
        is_rsa = kwargs.get('is_rsa')

        if is_rsa:
            outputstream = WriteWrapper(outputstream, self.cipher, self.cipher_size)

        outputstream.write(struct.pack('i', format_flags))

        if format_flags & FORMAT_FLAG_GZIP:
            outputstream = gzip.GzipFile(fileobj = outputstream, mode = 'wb')

        if format_flags & FORMAT_FLAG_BZ2:
            outputstream = bz2.BZ2File(outputstream, mode = 'wb')

        if format_flags & FORMAT_FLAG_LZMA:
            outputstream = lzma.LZMAFile(outputstream, mode='wb')

        # Write headers
        outputstream.write(struct.pack('Qi', length, flags))

        hashes = _get_hash_algorithms(flags)
        for chunk in _read_in_chunks(file_object = inputstream):
            for h in hashes:
                h.update(chunk)
            outputstream.write(chunk)

        hashchecks = b''
        for checksum in [h.digest() for h in hashes]:
            hashchecks += checksum
        if hashchecks:
            outputstream.write(hashchecks)

    def do_unpack(self, **kwargs):

        outputstream = kwargs.get('outputstream')
        inputstream = kwargs.get('inputstream')
        is_rsa = kwargs.get('is_rsa')

        if is_rsa:
            inputstream = ReadWrapper(inputstream, self.cipher, self.cipher_size)

        d = inputstream.read(4)
        format_flags, = struct.unpack('i', d)

        if format_flags & FORMAT_FLAG_GZIP:
            inputstream = gzip.GzipFile(fileobj = inputstream, mode='rb')

        if format_flags & FORMAT_FLAG_BZ2:
            inputstream = bz2.BZ2File(inputstream, mode='rb')

        if format_flags & FORMAT_FLAG_LZMA:
            inputstream = lzma.LZMAFile(inputstream, mode='rb')

        length, flags = struct.unpack('Qi', inputstream.read(12))

        hashes = _get_hash_algorithms(flags)

        params = {
            'file_object': inputstream,
            'max_length': length
        }
        for chunk in _read_in_chunks(file_object = inputstream, max_length = length):
            for h in hashes:
                h.update(chunk)
            outputstream.write(chunk)
        checksums = [h.digest() for h in hashes]

        # Read stored checksums in wrapper.
        expected = []
        if flags & FLAG_MD5:
            expected.append((LEN_MD5, 'MD5', inputstream.read(LEN_MD5)))
        if flags & FLAG_SHA1:
            expected.append((LEN_SHA1, 'SHA1', inputstream.read(LEN_SHA1)))
        if flags & FLAG_SHA256:
            expected.append((LEN_SHA256, 'SHA256', inputstream.read(LEN_SHA256)))
        if flags & FLAG_SHA512:
            expected.append((LEN_SHA512, 'SHA512', inputstream.read(LEN_SHA512)))

        for length, label, content in expected:
            if len(content) != length:
                estring = 'Was not able to extract %s checksum.' % label
                raise Exception(estring)

        for i in range(len(checksums)):
            length, label, content = expected[i]
            if checksums[i] != content:
                estring = '%s checksum does not match. Expected: %s vs Observed %s' % (label, _translate_digest(content), _translate_digest(checksums[i]))
                raise Exception(estring)

    def get_stream(self, path, mode, dash_stream):

        if dash_stream and path == '-':
            return (dash_stream, False)

        return (open(path, mode), True)

    def get_stream_length(self, stream):
        return os.fstat(stream.fileno()).st_size

    def log_error(self, content):
        print('Error:', content)

    def log_notice(self, content):
        print('Notice:', content)

    def load_keyfile_private(self, label, path_arg, environment_variable):

        path_env = self.environ.get(environment_variable, '')
        path = path_env or path_arg

        if path_env:
            label += ' (via environment variable "%s")' % environment_variable

        if not self.check_required_file(label, path):
            return False

        try:
            with open(path, 'rb') as f:
                self.cipher = serialization.load_pem_private_key(
                     f.read(),
                     password=None,
                 )
                self.cipher_size = int(self.cipher.key_size / 8)
        except ValueError as e:
            return False

        return True

    def load_keyfile_public(self, label, path_arg, environment_variable):

        path_env = self.environ.get(environment_variable, '')
        path = path_env or path_arg
        if path_env:
            label += ' (via environment variable "%s")' % environment_variable

        if not self.check_required_file(label, path):
            return False

        try:
            with open(path, 'rb') as f:
                self.cipher = serialization.load_pem_public_key(
                     f.read()
                 )
                self.cipher_size = int(self.cipher.key_size / 8)
        except ValueError as e:
            return False

        return True

    def run(self, **kwargs):

        self.environ = kwargs.get('environ', os.environ)
        if not self.run_args(kwargs.get('args', [])):
            return 1

        if self.encrypt:
            if self.args.verbose:
                self.log_notice('Encrypting file')

            format_flags = 0
            if self.args.gzip:
                format_flags |= FORMAT_FLAG_GZIP
            if self.args.bz2:
                format_flags |= FORMAT_FLAG_BZ2
            if self.args.lzma:
                format_flags |= FORMAT_FLAG_LZMA

            stream_in, stream_in_closable = self.get_stream(self.args.input, 'rb', kwargs.get('dashstream_in'))
            stream_out, stream_out_closable = self.get_stream(self.args.output, 'wb', kwargs.get('dashstream_out'))

            params = {
                'inputstream': stream_in,
                'outputstream': stream_out,
                'flags': FLAG_MD5 | FLAG_SHA256,
                'format_flags': format_flags,
                'is_rsa': True
            }
            self.do_pack(**params)

            if stream_in_closable:
                stream_in.close()

            if stream_out_closable:
                stream_out.close()

        elif self.decrypt:
            if self.args.verbose:
                self.log_notice('Decrypting file')

            stream_in, stream_in_closable = self.get_stream(self.args.input, 'rb', kwargs.get('dashstream_in'))
            stream_out, stream_out_closable = self.get_stream(self.args.output, 'wb', kwargs.get('dashstream_out'))

            params = {
                'inputstream': stream_in,
                'outputstream': stream_out,
                'is_rsa': True
            }
            self.do_unpack(**params)

            if stream_in_closable:
                stream_in.close()

            if stream_out_closable:
                stream_out.close()

        else:
            self.log_error('Unexpected mode.')
            return 1

        return 0

    def run_args(self, args):
        parser = argparse.ArgumentParser(description='Encryption/Decryption wrapper')
        parser.add_argument('-v', dest='verbose', action='store_true', help='Verbose output')
        # General options
        g_options = parser.add_argument_group('general options')
        g_options.add_argument('-i', dest='input', help='Input file')
        g_options.add_argument('-o', dest='output', help='Output file')

        # Encryption options
        e_options = parser.add_argument_group('encryption options')
        e_options.add_argument('-e', dest='encrypt', action='store_true', help='Encrypt file')
        e_options.add_argument('--public', dest='public_key', help='Public key file to encrypt file with. Alternative environment variable: RSA_PUBLIC_KEY')
        e_options.add_argument('--gzip', dest='gzip', action='store_true', help='Compress raw file with gzip before encrypting.')
        e_options.add_argument('--bz2', dest='bz2', action='store_true', help='Compress raw file with bz2 before encrypting.')
        e_options.add_argument('--lzma', dest='lzma', action='store_true', help='Compress raw file with bz2 before encrypting.')

        # Encryption options
        d_options = parser.add_argument_group('decryption options')
        d_options.add_argument('-d', dest='decrypt', action='store_true', help='Decrypt file')
        d_options.add_argument('--private', dest='private_key', help='Private key file to decrypt input file with. Alternative environment variable: RSA_PRIVATE_KEY')

        self.args = args = parser.parse_args(args)
        good = True

        mode_flags = 0
        if args.decrypt or args.private_key:
            mode_flags |= 1
        if args.encrypt or args.public_key or mode_flags == 0:
            mode_flags |= 2

        good = self.check_required_file('Input file', args.input) and good
        if not args.output:
            self.log_error('No output path provided.')
            good = False

        self.decrypt = self.encrypt = False

        if (mode_flags & 3) == 3:

            self.log_error('Ambiguous arguments, unsure whether we want to encrypt or decrypt.')
            good = False

        elif (mode_flags & 1) == 1:

            self.decrypt = True
            good = self.load_keyfile_private('Private key', args.private_key, 'RSA_PRIVATE_KEY') and good

        elif (mode_flags & 2) == 2:

            self.encrypt = True
            good = self.load_keyfile_public('Public key', args.public_key, 'RSA_PUBLIC_KEY') and good

        return good

def main(args, environ, wrapper_class):
    try:

        wrapper_kwargs = {
            'args': args,
            'dashstream_in': sys.stdin.buffer,
            'dashstream_out': sys.stdout.buffer,
            'environ': environ
        }

        wrapper = wrapper_class()
        return wrapper.run(**wrapper_kwargs)
    except KeyboardInterrupt:
        return 130

if __name__ == '__main__':
    exit(main(sys.argv[1:], os.environ, CommandWrapper))
