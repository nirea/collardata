#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import IPy
import logging

ranges = {'Production' : (
    "8.2.32.0/22",
    "8.4.128.0/22",
    "8.10.144.0/21",
    "63.210.156.0/22",
    "64.129.40.0/21",
    "64.154.220.0/22",
    "66.150.244.0/23",
    "69.25.104.0/23",
    "72.5.12.0/22",
    "216.82.0.0/18"
    )
}

def inrange(address):
    #Now returns what grid it is on use to be #True if address is in one of LL's IP ranges, else False
    for shard in ranges.iterkeys():
        for range in ranges[shard]:
            if address in IPy.IP(range):
                return shard
    logging.error('non-grid IP request from %s' % (address))
    return None
