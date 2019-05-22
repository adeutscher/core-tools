#!/usr/bin/python

# Silly ping wrapper script.
# As opposed to using flat ping, this will give the user more live
#   statistics without having to Ctrl-C out and reset their counters.
# In particular, I want to know my percentage of dropped pings per-ping.

import re, socket, string, subprocess, sys, time

def ping(server):
    r = {}
    t = time.time()
    p = subprocess.Popen(["ping", "-W1", "-c1", server], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    # Calculate time lazily using python time rather than the time from ping.
    # This might result in some inaccurate numbers, but I think it's minor enough to let slide
    r["time"] = time.time() - t

    l = re.search("^\d+ bytes from.+$", out, re.MULTILINE)
    if l and not p.returncode:
        r["success"] = True
        # Strip out the icmp_seq value because our implementation invokes a new
        #   ping process. icmp_seq will always be '1'.
        r["line"] = re.sub("\s+icmp_seq=\d+", "", l.group(0))
    else:
        r["success"] = False
        r["line"] = "No response from %s" % server

    return r

def stats(server, ip):
    total_pings = 0
    total_success = 0

    time_max = 0
    time_min = 0
    time_avg = 0

    recent_limit = 10

    # Draw a little "heartbeat" chart of how recent pinging is doing.
    chart = ''

    # Current time for final statistics
    t = time.time()

    try:
        while True:
            r = ping(server)

            total_pings += 1
            if r.get("success", False):
                total_success += 1

            time_max = max(time_max, r["time"])
            time_min = min(time_min, r["time"])
            time_avg += ((r["time"] - time_avg) / total_pings)

            # Modify heartbeat chart
            if r["success"]:
                chart += '^'
            else:
                chart += '-'
            chart = chart[max(0, len(chart)-recent_limit):] # Trim chart

            # Padding the count digits to avoid a bunch of relatively rapid format jumps.
            print "[%03d/%03d %6.02f%%][%s]: %s" % (total_success, total_pings, float(total_success) / total_pings * 100, string.ljust(chart, recent_limit, '_'), r["line"])

            time.sleep(max(0, 1-r["time"]))
    except KeyboardInterrupt:
        pass

    if total_pings:

        if server != ip:
            display_server = "%s (%s)" % (server, ip)
        else:
            display_server = ip

        print "\n--- %s ping statistics ---" % display_server
        # ping numbers in ping-like format
        print "%s packets transmitted, %d received, %.02f%% packet loss" % (total_pings, total_success, 100 - float(total_success) / total_pings * 100)
        # rtt stats. I don't worry about this as much as success percentage.
        print "rtt min/avg/max %.03f/%.03f/%.03f" % (time_min, time_avg, time_max)

if len(sys.argv) <= 1:
    print "No server specified."
    exit(1)
addr = sys.argv[-1]
try:
    ip = socket.gethostbyname(addr)
except socket.gaierror:
    print "Unable to resolve address: %s" % addr
    exit(2)
stats(addr, ip)
