#!/usr/bin/env python

import common, unittest

class TimeDisplayTests(unittest.TestCase):

    def __test_unit(self, unit, multiplier, increment):
        '''Central method for testing only one unit'''
        self.assertEqual('1 %s' % unit, self.mod.translate_seconds(multiplier))
        for i in range(2,increment-1):
            self.assertEqual('%d %ss' % (i, unit), self.mod.translate_seconds(i * multiplier))
        self.assertNotEqual('%d %ss' % (increment, unit), self.mod.translate_seconds(increment * multiplier))

    def setUp(self):
        self.mod = common.load('time_display', common.TOOLS_DIR + '/scripts/clipboard/python/time_display.py')

    def test_combo_oxford_a(self):
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('4 hours, 5 minutes, and 52 seconds', self.mod.translate_seconds(hours + minutes + seconds))

    def test_combo_oxford_b(self):
        years = 3 * 52 * 7 * 24 * 60 * 60
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('3 years, 4 hours, 5 minutes, and 52 seconds', self.mod.translate_seconds(years + hours + minutes + seconds))

    def test_combo_oxford_c(self):
        years = 3 * 52 * 7 * 24 * 60 * 60
        weeks = 42 * 7 * 24 * 60 * 60
        hours = 4 * 60 * 60
        minutes = 5 * 60
        seconds = 52

        self.assertEqual('3 years, 42 weeks, 4 hours, 5 minutes, and 52 seconds', self.mod.translate_seconds(years + weeks + hours + minutes + seconds))

    def test_combo_two_values_a(self):
        hours = 4 * 60 * 60
        minutes = 5 * 60

        self.assertEqual('4 hours, 5 minutes', self.mod.translate_seconds(hours + minutes))

    def test_combo_two_values_b(self):
        days = 4 * 24 * 60 * 60
        seconds = 22

        self.assertEqual('4 days, 22 seconds', self.mod.translate_seconds(days + seconds))

    def test_only_days(self):
        self.__test_unit('day', 60 * 60 * 24, 7)

    def test_only_hours(self):
        self.__test_unit('hour', 60 * 60, 24)

    def test_only_minutes(self):
        self.__test_unit('minute', 60, 60)

    def test_only_seconds(self):
        self.__test_unit('second', 1, 60)

    def test_zero_seconds(self):
        self.assertEqual('0 seconds', self.mod.translate_seconds(0))
