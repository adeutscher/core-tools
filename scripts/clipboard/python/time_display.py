#!/usr/bin/python

import re
import unittest

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
            noun = re.sub("s$", "", noun)

        if mod_value:
            times.append("%s %s" % (mod_value, noun))

        num = int(num / value)
        if not num:
            break # No more modules to process

    if len(times) == 1:
        return " ".join(times)
    elif len(times) == 2:
        return ", ".join(reversed(times))
    else:
        # Oxford comma
        d = ", and "
        s = d.join(reversed(times))
        sl = s.split(d, len(times) - 2)
        return ", ".join(sl)

# Test methods to demonstrate/confirm
class TimeDisplayTests(unittest.TestCase):

    def __test_unit(self, unit, multiplier, increment):
        '''Central method for testing only one unit'''
        self.assertEqual('1 %s' % unit, translate_seconds(multiplier))
        for i in range(2,increment-1):
            self.assertEqual('%d %ss' % (i, unit), translate_seconds(i * multiplier))
        self.assertNotEqual('%d %ss' % (increment, unit), translate_seconds(increment * multiplier))

    def test_combo_oxford_a(self):
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('4 hours, 5 minutes, and 52 seconds', translate_seconds(hours + minutes + seconds))

    def test_combo_oxford_b(self):
        years = 3 * 52 * 7 * 24 * 60 * 60
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('3 years, 4 hours, 5 minutes, and 52 seconds', translate_seconds(years + hours + minutes + seconds))

    def test_combo_oxford_c(self):
        years = 3 * 52 * 7 * 24 * 60 * 60
        weeks = 42 * 7 * 24 * 60 * 60
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('3 years, 42 weeks, 4 hours, 5 minutes, and 52 seconds', translate_seconds(years + weeks + hours + minutes + seconds))

    def test_combo_two_values_a(self):
        hours = 4 * 60 * 60
        minutes = 5 * 60

        self.assertEqual('4 hours, 5 minutes', translate_seconds(hours + minutes))

    def test_combo_two_values_b(self):
        days = 4 * 24 * 60 * 60
        seconds = 22

        self.assertEqual('4 days, 22 seconds', translate_seconds(days + seconds))

    def test_only_days(self):
        self.__test_unit('day', 60 * 60 * 24, 7)

    def test_only_hours(self):
        self.__test_unit('hour', 60 * 60, 24)

    def test_only_minutes(self):
        self.__test_unit('minute', 60, 60)

    def test_only_seconds(self):
        self.__test_unit('second', 1, 60)

    def test_zero_seconds(self):
        self.assertEqual('0 seconds', translate_seconds(0))

if __name__ == '__main__':
    suite = unittest.TestSuite()
    for method in [m for m in dir(TimeDisplayTests) if m.startswith('test_')]:
      suite.addTest(TimeDisplayTests(method))
    unittest.TextTestRunner(verbosity = 2).run(suite)
