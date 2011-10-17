
#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details
from google.appengine.api import memcache
import logging
import yaml
import time


#Cleo: not allowed AVs
# depending on the amount of AVs invovled in the attack we might need to change this to a database, i would like to prevent for now to save apptime
blockedkeys = []

# wanr if the token name is longer than this so we can easier discover attack from ALTs
warntokenname = 30
# warn if a value get longer tha this, could happen with textures
warnvalue = 500
# block if the value is longer than this
blockvalue = 500

throttlecap = 20#limit of requests per minute

def validvalue(action,key,name,token,value, headers):
    #True if we think the call is from a non blocked user and vertain treshhold are not meet
    objkey = headers['X-SecondLife-Object-Key']
    objname = headers['X-SecondLife-Object-Name']
    objregion = headers['X-SecondLife-Region']
    objpos = headers['X-SecondLife-Local-Position']

    # first check if Av is in block list. May need to be changed to a table :(
    if key in blockedkeys:
        # log warning
        logging.warning('Illegal %s access by %s.\nToken: %s\nValue: %s\nObjKey: %s\nObjName: %s\nObjRegion: %s\nObjPos: %s' % (action,name,token,value, objkey, objname, objregion, objpos))
        # return false, so access gets blocked


        #query = AvTokenValue.gql("WHERE av = :1", key)
        #record = query.get()
        #record.delete()#delete just 1 record
        #logging.info('deleted %d records belonging to %s' % (1, name))
        return False

    #throttle requests
    #first load the timestamps, which will be saved in memcache as a yaml list
    historykey = '%s_history' % key
    histyaml = memcache.get(historykey)
    now = time.time()
    counter = 0

    if histyaml is not None:
        history = yaml.safe_load(histyaml)
        #throw out any stamps more than a minute old
        for request in history:
            if now - request > 60.0:
                del history[counter]
            counter += 1
        #add this request
        history += [now]
        #if there are more requests than throttlecap in the last minute, log it and return false
        if len(history) > throttlecap:
            logging.warning('%d requests in the last minute by %s.\nToken: %s\nValue: %s\nObjKey: %s\nObjName: %s\nObjRegion: %s\nObjPos: %s' % (len(history),name,token,value, objkey, objname, objregion, objpos))
            return False
    else:
        history = [now]
    #save the new history
    memcache.set(historykey, yaml.safe_dump(history))

    # warn if tokens are longer than the treshhold, not sure if this is needed or about the length yet
    if len(token)>warntokenname:
        # log warning
        logging.warning('Long token %s access from %s, please check.\nToken: %s\nValue: %s' % (action,name,token,value))

    # block if values are longer than the treshhold, not sure if this about the length yet
    # if len(value)>blockvalue:
        # log warning
        # logging.warning('Long value %s access from %s, action blocked.\nToken: %s\nValue: %s' % (action,name,token,value))
        # return false, so access gets blocked
        # return False
    # check as safety if a certain length is exceeded
    elif len(value)>warnvalue:
        # log warning
        logging.warning('Long value %s access from %s, please check.\nToken: %s\nValue: %s' % (action,name,token,value))
    # we seem to have a vaild request
    return True
