#!/usr/bin/python

import sys, os.path
from base64 import b64decode

try:
    from Crypto.PublicKey import RSA
    from Crypto.Util import asn1
except ImportError:
    print >> sys.stderr, "Could not find pycrypto. Try installing the python-crypto package!"
    exit(1)

if not len(sys.argv) == 3:
    print >> sys.stderr, "Usage: %s 'input-file' 'output-file'" % os.path.basename(sys.argv[0])
    exit(2)

if sys.argv[1] == '-':
    print >> sys.stderr, "Reading file data from stdin"
    inputFile = sys.stdin
# Encryption
else:
    print >> sys.stderr,"Reading file data from '%s'" % sys.argv[1]
    inputFile = open(sys.argv[1],"r")

instaFlush = False
if sys.argv[2] == '-':
    print >> sys.stderr, "Writing file data to stdout."
    outputFile = sys.stdout
    instaFlush = True
else:
    print >> sys.stderr, "Writing file data to '%s'" % sys.argv[2]
    outputFile = open(sys.argv[2],"w")

# Hard-coded public key data.
try:
    # PEM format. Reminder for conversion: cat key.pem | tr -d '\n' , then copy text
    publicKey64 = 'redacted-public-key'
    publicKey = b64decode(publicKey64)
    publicKeyObj = RSA.importKey(publicKey)
    # Reminder: size() returns maximum BITS
    maxKeyBytes = publicKeyObj.size()/8+1
except ValueError as e:
    print "Error loading public key."
    exit(1)

while True:
    dataBlock = inputFile.read(maxKeyBytes)

    if len(dataBlock) == 0:
        # Done
        break
    else:
        cipherBlock = publicKeyObj.encrypt(dataBlock,'k')[0]
        #print >> sys.stderr, "Converted %d of plaintext to %d of ciphertext" % tuple([len(dataBlock), len(cipherBlock)])
        outputFile.write(cipherBlock)

        if instaFlush:
            outputFile.flush()


