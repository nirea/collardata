from google.appengine.api import memcache
from google.appengine.api import urlfetch
import logging
import alarm
import yaml

from model import Deliver, FreebieItem

def enqueue_delivery(giver, rcpt, objname, redirecturl):
    #check memcache for giver's queue
    token = "deliveries_%s" % giver
    deliveries = memcache.get(token)
    if deliveries is None:
        #if not, create new key and save
        memcache.set(token, [[objname, rcpt]])
        return True
    else:
        if len(deliveries) > 200:
            logging.error('Queue for %s hosting %s is too long, data not stored' % (giver, objname))
            alarm.SendAlarm('Vendor', giver, True, 'Vendor queue for %s hosting %s is too long, data not stored. Please make sure to check the object and the database usage!' % (giver, objname), redirecturl)
            return False
        else:
            if len(deliveries) > 50:
                logging.warning('Queue for %s hosting %s is getting long (%d entries)' % (giver, objname, len(deliveries)))
            logging.info('queue for %s is %s' % (giver, deliveries))
            deliveries.append([objname, rcpt])#yes I really mean append.  this is a list of lists
            memcache.set(token, deliveries)
            return True

def remove_item_url(name, deliver):
    item = FreebieItem.gql("WHERE freebie_name = :1", name).get()
    if item is None:
        #could not find item to look up its deliverer.  return an error
        logging.info("Removing %s deliver from %s but item is not found." % (deliver, name)) #return None
    else:
        logging.info("Removing %s deliver from %s" % (deliver, name))
        item.givers.remove(deliver)
        item.put()
        token = 'item_%s' % name
        token2 = 'paid_item_%s' % name
        data = yaml.safe_dump({
                               "name":name,
                               "version":item.freebie_version, 
                               "giver":item.freebie_giver, 
                               "givers":item.givers, 
                               "designer_key":item.designer_key, 
                               "designer_cut":item.designer_cut, 
                               "baseprice":item.baseprice
                               })
        if item.baseprice == 0:
            memcache.set(token, data)
        memcache.set(token2, data)

def httpin_delivery(self, rcpt, objname, recordid):
    name = objname
    item = get_item(name, True)
    if item is None:
        #could not find item to look up its deliverer.  return an error
        logging.error('Error, Paid item %s not found yet was found before. Requested by %s using %s.' % (name, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
        self.error(403)
        return
    name_version = "%s - %s" % (name, item['version'])
    if item['givers'] == []:
        logging.error('Error, Paid item %s does not have http urls.' % (name))
        self.error(403)
        return
    givers = item['givers']
    #need to add a way to rotate the urls
    url_token = 'url_%s' % name
    url = ''
    url_num = 0
    for _i in range(3):
        #will move the code here to compact it instead of the else and ifs
        url_num = memcache.incr(url_token, initial_value=0)
        url_num = url_num % ((len(givers)))
        url_cached = True
        count_token = 'item_count_%s' % name
        memcache.incr(count_token, initial_value=0)
        deliv_url_token = 'deliv_url_%s' % givers[url_num]
        cacheddist = memcache.get(deliv_url_token)
        if cacheddist is None:
            deliv = Deliver.get_by_key_name("Deliv:%s" % givers[url_num])
            if deliv is None:
                #could not find item deliverer.
                remove_item_url(name, givers[url_num])
                continue
            else:
                url_cached = False
                url = deliv.url
                memcache.set(deliv_url_token, deliv.url)
        else:
            url = cacheddist
        logging.debug("Tring to send %s to %s using deliver %s" % (name, rcpt, givers[url_num]))
        result = urlfetch.fetch(url, method="POST", payload="%s|%s" % (name_version, rcpt) , headers={}, deadline = 10)
        if result.content == "sent":
            #record = Purchases(purchaser = rcpt, item = name, seller = self.request.headers['X-SecondLife-Owner-Key'], item_reciver = 'request', loc = '%s %s' % (self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']), vender_name = self.request.headers['X-SecondLife-Object-Name'], amount_paid = paid)
            #have the vendor transfer the money
            return 'sent|%s|%s|%s' % (rcpt, name_version, recordid)#do we need all of this?
        elif result.status_code == 410:
            #the item is not in that box remove the box from that item
            remove_item_url(name, givers[url_num])
        elif result.status_code == 404:
            if url_cached:
                deliv = Deliver.get_by_key_name("Deliv:%s" % givers[url_num])
                if deliv is None:
                    #check for no results.
                    remove_item_url(name, givers[url_num])
                elif url != deliv.url:
                    #try again as the url was out of date
                    url_cached = False
                    memcache.set(deliv_url_token, deliv.url)
                    url = deliv.url
                else:
                    remove_item_url(name, givers[url_num])
            else:
                remove_item_url(name, givers[url_num])
        else:
            logging.error('Error, item %s did not get sent by %s may try again. Status %s Message from vendor: %s' % (name_version, givers[url_num], result.status_code, result.content))
    else:
        logging.error('Error, Paid item %s did not get sent. Status %s Message from vendor: %s' % (name_version, result.status_code, result.content))
        self.error(403)

def get_item(name, paid):
    if (paid):
        token = 'paid_item_%s' % name
    else:
        token = 'item_%s' % name
    cacheditem = memcache.get(token)
    if cacheditem is None:
        if (paid):
            itemlookup = FreebieItem.gql("WHERE freebie_name = :1", name).get()
        else:
            itemlookup = FreebieItem.gql("WHERE freebie_name = :1 and cost = 0", name).get()
        if itemlookup is None:
            #could not find item to look up its deliverer.  return an error
            return None
        else:
            item = {
                   "name":name,
                   "version":itemlookup.freebie_version, 
                   "giver":itemlookup.freebie_giver, 
                   "givers":itemlookup.givers, 
                   "designer_key":itemlookup.designer_key, 
                   "designer_cut":itemlookup.designer_cut, 
                   "baseprice":itemlookup.baseprice
                   }
            memcache.set(token, yaml.safe_dump(item))
    else:
        #pull the item's details out of the yaml'd dict
        item = yaml.safe_load(cacheditem)
    return item
