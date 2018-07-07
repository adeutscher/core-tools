
# Programming scripts

Convenience scripts for programming.

## bitmask-helper.py

Print out bitmask values.

Usage examples:

    ./bitmask-helper.py 1234
    ./bitmask-helper.py 0x1234

## format-code.sh

Wrapper around `astyle`.

Usage example:

    ./format-code .c [destination]

Notes:

* Multiple file extensions and paths can be provided in one go.

## translate-binary-to-decimal.py

Usage examle:

    ./translate-binary-to-decimal.py 11011

Note:

* Multiple numbers can be provided in one go.

## translate-hex-to-decimal.py

A lazy wrapper to convert hex from BASH, while printing out the steps involved.

Usage example:

    ./translate-hex-to-decimal.py 0x22

Note:

* Multiple numbers can be provided in one go.
