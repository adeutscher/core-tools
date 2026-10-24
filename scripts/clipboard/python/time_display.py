#!/usr/bin/env python

import re

def translate_seconds(duration):
    '''Translate seconds to something more human-readable.'''
    # Each module is a unit name (in plural form) and its length in seconds, from largest to smallest.
    # A year is treated as 365 days.
    modules = [
        ('years', 365 * 24 * 60 * 60),
        ('weeks', 7 * 24 * 60 * 60),
        ('days', 24 * 60 * 60),
        ('hours', 60 * 60),
        ('minutes', 60),
        ('seconds', 1)
    ]

    num = max(0, int(duration))

    if not num:
        # Handle empty
        return '0 %s' % modules[-1][0]

    times = []
    for noun, value in modules:

        count, num = divmod(num, value)

        if count == 1:
            noun = re.sub('s$', '', noun)

        if count:
            times.append('%s %s' % (count, noun))

    if len(times) == 1:
        return ' '.join(times)
    elif len(times) == 2:
        return ', '.join(times)
    else:
        # Oxford comma
        d = ', and '
        s = d.join(times)
        sl = s.split(d, len(times) - 2)
        return ', '.join(sl)
