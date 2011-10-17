#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

from google.appengine.api import memcache
import logging

from model import Distributor, Contributor

def Distributor_authorized(av):
    #True if av is on the authorized distributor list, else False
    token = "dist_auth_%s" % av
    memrecord = memcache.get(token)
    if memrecord is None:
        #dist is not in memcache, check db
        dbrecord = Distributor.gql('WHERE avkey = :1', av).get()
        if dbrecord is None:
            memcache.set(token, False)
            return False
        else:
            memcache.set(token, True)
            return True
    else:
        #dist is in memcache.  check value
        if memrecord:
            return True
        else:
            return False

def Distributor_add(av, name):
    record = Distributor.gql('WHERE avkey = :1', av).get()
    if record is None:
        NewDist = Distributor(avkey = av, avname = name)
        NewDist.put()
    token = "dist_auth_%s" % av
    memcache.set(token, True)

def Distributor_delete(av, name):
    record = Distributor.gql('WHERE avkey = :1', av).get()
    if record is not None:
        record.delete()
    token = "dist_auth_%s" % av
    memcache.delete(token)

def Contributor_authorized(av):
    #True if av is on the authorized distributor list, else False
    token = "contr_auth_%s" % av
    memrecord = memcache.get(token)
    if memrecord is None:
        #dist is not in memcache, check db
        dbrecord = Contributor.gql('WHERE avkey = :1', av).get()
        if dbrecord is None:
            memcache.set(token, False)
            return False
        else:
            memcache.set(token, True)
            return True
    else:
        #dist is in memcache.  check value
        if memrecord:
            return True
        else:
            return False

def Contributor_add(av, name):
    record = Contributor.gql('WHERE avkey = :1', av).get()
    if record is None:
        NewDist = Contributor(avkey = av, avname = name)
        NewDist.put()
    token = "contr_auth_%s" % av
    memcache.set(token, True)

def Contributor_delete(av, name):
    record = Contributor.gql('WHERE avkey = :1', av).get()
    if record is not None:
        record.delete()
    token = "contr_auth_%s" % av
    memcache.delete(token)
