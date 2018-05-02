
# Bluetoothctl

This is a reminder of how to manage Bluetooth devices.

## General

In general, remember that `bluetoothctl` is case-sensitive and requires capital letters.

A super-lazy way to bump a lower-case MAC address to upper-case in Python would be:

    python -c "print 'aa:bb:cc:dd:ee:ff'.upper()"

## Initialize

When initializing for the first time in a boot:

    power on
    agent KeyboardOnly
    default-agent

## Connect Device

    scan on
    trust AA:BB:CC:DD:EE:FF
    pair AA:BB:CC:DD:EE:FF
    connect AA:BB:CC:DD:EE:FF

## Disconnect Device

    remove AA:BB:CC:DD:EE:FF
    disconnect AA:BB:CC:DD:EE:FF
