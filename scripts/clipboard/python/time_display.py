#!/usr/bin/env python

import re

def translate_seconds(duration):
    '''Translate seconds to something more human-readable.'''
    modules = [
        ('seconds', 60),
        ('minutes',60),
        ('hours',24),
        ('days',7),
        ('weeks',52),
        ('years',100)
    ]

    num = max(0, int(duration))

    if not num:
        # Handle empty
        return '0 %s' % modules[0][0]

    times = []
    for i in range(len(modules)):

        noun, value = modules[i]
        mod_value = num % value

        if mod_value == 1:
            noun = re.sub('s$', '', noun)

        if mod_value:
            times.append('%s %s' % (mod_value, noun))

        num = int(num / value)
        if not num:
            break # No more modules to process

    if len(times) == 1:
        return ' '.join(times)
    elif len(times) == 2:
        return ', '.join(reversed(times))
    else:
        # Oxford comma
        d = ', and '
        s = d.join(reversed(times))
        sl = s.split(d, len(times) - 2)
        return ', '.join(sl)
