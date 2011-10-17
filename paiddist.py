#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

from google.appengine.api import memcache, urlfetch, taskqueue
from google.appengine.api.datastore import _ToDatastoreError
from google.appengine.ext import db, webapp
from google.appengine.runtime import DeadlineExceededError
from model import Purchases, AppSettings, Distributor, Dispersals
import cgi
import distributors
import lindenip
import logging
import model
import os
import sys
import tools
import wsgiref.handlers
import yaml




moneyRcpt = AppSettings.get_or_insert("moneyRcpt", value="00000000-0000-0000-0000-000000000000").value
dispersalMsgs = {"seller":"commission from vendors", "designer":"designer cut", "maintainer":"maintainer stipend"}



def DisperseurlUrl():
    theurl=memcache.get('disperseurl')
    if theurl is None:
        disperse = AppSettings.get_by_key_name("disperseurl")
        if disperse is None:
            return ''
        else:
            memcache.set('disperseurl', disperse.value)
            return disperse.value
    else:
        return theurl

class Deliver(webapp.RequestHandler):
    def post(self):
        #check linden IP  and allowed avs
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.Distributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
            logging.warning("Illegal attempt to request an item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
        elif not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance to %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.response.out.write('Currently down for maintenance')
        else:
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]

            try:
                name = params['objname']
                item = tools.get_item(name, True)
                if item is None:
                    #could not find item to look up its deliverer.  return an error
                    logging.error('Error, Paid item %s not found. Requested by %s using %s.' % (name, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(403)
                    return
                name_version = "%s - %s" % (name, item['version'])
                rcpt = str(params['rcpt'])
                paid = int(params['paid'])
                baseprice = int(item['baseprice'])
                if paid >= baseprice:
                    pass
                else:
                    token = 'Distributor_%s' % self.request.headers['X-SecondLife-Owner-Key']
                    cacheditem = memcache.get(token)
                    if cacheditem is None:
                        dist = Distributor.gql("WHERE avkey = :1", self.request.headers['X-SecondLife-Owner-Key']).get()
                        dist_info = {"max_discount":dist.max_discount, "commission":dist.commission}
                        memcache.set(token, yaml.safe_dump(dist_info))
                    else:
                        #pull the item's details out of the yaml'd dict
                        dist_info = yaml.safe_load(cacheditem)
                    disprice = baseprice * (100-dist_info['max_discount'])/100.0
                    if paid < disprice:
                        if paid < (disprice - 50):
                            logging.error('Rejecting request: Wrong price by %s, vendor %s located in %s at %s. Item:%s Item Price:%s Price Paid:%s Max Discount:%s%%' % 
                              (self.request.headers['X-SecondLife-Owner-Name'],
                               self.request.headers['X-SecondLife-Object-Name'],
                               self.request.headers['X-SecondLife-Region'],
                               self.request.headers['X-SecondLife-Local-Position'],
                               name,
                               baseprice,
                               paid,
                               dist_info['max_discount']
                               ))
                            self.error(403)
                            self.response.out.write('Wrong amount Item:%s Item Price:%s Price Paid:%s Max Discount:%s%%' % 
                              (name,
                               baseprice,
                               paid,
                               dist_info['max_discount']
                               ))
                            return
                        else:
                            logging.warning('Under Paid Item accepting: Wrong price by %s, vendor %s located in %s at %s. Item:%s Item Price:%s Price Paid:%s Max Discount:%s' % 
                              (self.request.headers['X-SecondLife-Owner-Name'],
                               self.request.headers['X-SecondLife-Object-Name'],
                               self.request.headers['X-SecondLife-Region'],
                               self.request.headers['X-SecondLife-Local-Position'],
                               name,
                               baseprice,
                               paid,
                               ))
                            
                    
                #need to record record here
                record = Purchases(purchaser = rcpt, item = name, seller = self.request.headers['X-SecondLife-Owner-Key'], item_reciver = 'request', loc = '%s %s' % (self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']), vender_name = self.request.headers['X-SecondLife-Object-Name'], amount_paid = paid)
                record.put()
                #have the vendor transfer the money
                self.response.out.write('pay|%s|%s|%s|%s|%s' % (moneyRcpt, paid, rcpt, name, record.key().id()))#do we need all of this?
            except KeyError:
                logging.error('Key error for paid Post vendor  %s, queue entry: %s|%s   %s' % (item['giver'], rcpt, name_version, sys.exc_info()))
                self.error(403)
    def put(self):
        #check linden IP  and allowed avs
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.Distributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
            logging.info("Illegal attempt to request an item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
        elif not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance to %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.response.out.write('Currently down for maintenance')
        else:
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]

            try:
                recordID = int(params['id'])
                record = Purchases.get_by_id(recordID)
                if record is None:
                    #could not find item to look up its deliverer.  return an error
                    logging.error('Error, Paid record %s not found. Requested by %s using %s.' % (recordID, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(403)
                    return
                #else:
                record.item_reciver = record.purchaser
                record.accounted = "0"
                record.put()
                rcpt = record.purchaser
                name = record.item
                self.response.out.write(tools.httpin_delivery(self, rcpt, name, record.key().id()))
            except KeyError:
                logging.error('Key error for paid PUT vendor tran id %s, queue entry: %s|%s   %s' % (recordID, rcpt, name, sys.exc_info()))
                self.error(403)

class GiftDeliver(webapp.RequestHandler):
    def post(self):
        #check linden IP  and allowed avs
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
#        elif not distributors.Distributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
#            logging.info("Illegal attempt to request an item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
#            self.error(403)
        elif not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance to %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.response.out.write('Currently down for maintenance')
        else:
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]

            try:
                name = params['objname']
                item = tools.get_item(name, True)
                if item is None:
                    #could not find item to look up its deliverer.  return an error
                    logging.error('Error, Paid item %s not found. Requested by %s using %s.' % (name, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(403)
                    return
                name_version = "%s - %s" % (name, item['version'])
                rcpt = self.request.headers['X-SecondLife-Owner-Key']
                paid = int(params['paid'])
                baseprice = int(item['baseprice'])
                if paid >= baseprice:
                    pass
                else:

                            logging.error('Rejecting request: Wrong price by %s, gift vendor %s located in %s at %s. Item:%s Item Price:%s Price Paid:%s' % 
                              (self.request.headers['X-SecondLife-Owner-Name'],
                               self.request.headers['X-SecondLife-Object-Name'],
                               self.request.headers['X-SecondLife-Region'],
                               self.request.headers['X-SecondLife-Local-Position'],
                               name,
                               baseprice,
                               paid
                               ))
                            self.error(403)
                            return  
                #need to record record here
                record = Purchases(purchaser = rcpt, item = name, seller = self.request.headers['X-SecondLife-Owner-Key'], item_reciver = 'gift request', loc = '%s %s' % (self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']), vender_name = self.request.headers['X-SecondLife-Object-Name'], amount_paid = paid)
                record.put()
                #have the vendor transfer the money
                self.response.out.write('pay|%s|%s|%s|%s|%s' % (moneyRcpt, paid, rcpt, name, record.key().id()))#do we need all of this?
            except KeyError:
                logging.error('Key error for paid Post gift vendor  %s, queue entry: %s|%s   %s' % (item['giver'], rcpt, name_version, sys.exc_info()))
                self.error(403)
    def put(self):
        #check linden IP  and allowed avs
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
#        elif not distributors.Distributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
#            logging.info("Illegal attempt to request an item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
#            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance to %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.response.out.write('Currently down for maintenance')
        else:
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]

            try:
                recordID = int(params['id'])
                record = Purchases.get_by_id(recordID)
                if record is None:
                    #could not find item to look up its deliverer.  return an error
                    logging.error('Error, Paid record %s not found. Requested by %s using %s.' % (recordID, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(403)
                    return
                #else:
                record.item_reciver = 'gift'
                record.accounted = "0"
                record.put()
                self.response.out.write('confirmed|||%s' % (recordID))
            except KeyError:
                logging.error('Key error for paid PUT gift vendor %s, queue entry: %s|%s   %s' % (self.request.headers['X-SecondLife-Object-Key'], record.item_reciver, recordID, sys.exc_info()))
                self.error(403)

class GiftReceive(webapp.RequestHandler):
    def put(self):
        #check linden IP  and allowed avs
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
#        elif not distributors.Distributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
#            logging.info("Illegal attempt to request an item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
#            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance to %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.response.out.write('Currently down for maintenance')
        else:
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]
            try:
                recordID = int(params['id'])
                record = Purchases.get_by_id(recordID)
                if record is None:
                    #could not find item to look up its deliverer.  return an error
                    logging.error('Error, Paid record %s not found. Requested by %s using %s.' % (recordID, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(404)
                    return
                elif record.item_reciver == 'gift':
                    record.item_reciver = self.request.headers['X-SecondLife-Owner-Key']
                    record.put()
                    logging.debug('Paid record %s updated to show rcpt is %s.' % (recordID, self.request.headers['X-SecondLife-Owner-Name']))
                    rcpt = record.item_reciver
                    name = record.item
                    self.response.out.write('rcpt set|||%s' % (recordID))
                else:
                    logging.error('Error, Paid record %s not found. Requested by %s using %s.' % (recordID, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(403)
            except KeyError:
                logging.error('Key error for paid PUT gift receive vendor %s, queue entry: %s|%s   %s' % (self.request.headers['X-SecondLife-Object-Key'], rcpt, recordID, sys.exc_info()))
                self.error(403)
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
#        elif not distributors.Distributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
#            logging.info("Illegal attempt to request an item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
#            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            #should be newline-delimited, token=value
#            lines = self.request.body.split('\n')
#            params = {}
#            for line in lines:
#                params[line.split('=')[0]] = line.split('=')[1]
            try:
                recordID = int(self.request.get('id'))
                record = Purchases.get_by_id(recordID)
                if record is None:
                    #could not find item to look up its deliverer.  return an error
                    logging.error('Error, Paid record %s not found. Requested by %s using %s.' % (recordID, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(404)
                    return
                elif record.item_reciver == self.request.headers['X-SecondLife-Owner-Key']:
                    rcpt = record.item_reciver
                    name = record.item
                    self.response.out.write(tools.httpin_delivery(self, rcpt, name, record.key().id()))
                else:
                    logging.error('Error, Paid record %s found but requested by %s using %s and it is set for %s.' % (recordID, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], record.item_reciver))
                    self.error(403)
            except KeyError:
                logging.error('Key error for paid PUT gift receive vendor %s, queue entry: %s|%s   %s' % (self.request.headers['X-SecondLife-Object-Key'], rcpt, name, sys.exc_info()))
                self.error(403)        

def GetDispersals(id):
    record = Dispersals.get_by_id(id)
    list = record.people_to_pay
    if list.startswith("STARTED"):
        raise db.Rollback
    else:
        list = "STARTED\n" + list
        record.people_to_pay = list
        record.put()
        return record

class SetDisperseURL(webapp.RequestHandler):
    def post(self):
        #check linden IP  and allowed avs
        logging.info('Disperse URL')
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            logging.warning("Illegal attempt to set disperse URL from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
        else:
            disperseurl = self.request.body
            disperse = AppSettings(key_name="disperseurl", value=disperseurl)
            disperse.put()
            memcache.set('disperseurl', disperseurl)
            logging.info('Disperse URL set to %s' % disperseurl)
            self.response.out.write('Added')

class Disperse(webapp.RequestHandler):
    def put(self):
        if not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance")
            self.response.out.write('Currently down for maintenance')
        else:
            id = int(cgi.escape(self.request.get('id')))
            record = db.run_in_transaction(GetDispersals, id)
            if record is None:
                #has already started
                logging.warning("Dispersal %s has already been started" % id)
            else:
                dispersal_list = record.people_to_pay.split("\n")
                url = DisperseurlUrl()
                first = dispersal_list.pop(0)
                logging.info("Starting Dispersal %s" % id)
                if first != "STARTED":
                    logging.critical("Dispersal %s has not been marked STARTED" % id)
                    dispersal_list.insert(0,first)
                try:
                    for line in dispersal_list[:]:
                        who = line.split("_")[0]
                        message = dispersalMsgs.get(line.split("_")[1])
                        amount = getattr(record, line, 0)
                        result = urlfetch.fetch(url, method="POST", payload="%s|%s|%s" % (who, message, amount) , headers={}, deadline = 10)
                        if result.content.split("|")[0] == "paid":
                            logging.info("%s was paid %s for %s" % (who, amount, message))
                            dispersal_list.remove(line)
                        elif result.status_code == 404:
                            urltemp = DisperseurlUrl()
                            if url == urltemp:
                                logging.warning("Dispersal %s was stoped at %s due to a bad url: %s" % (id, line, url))
                                self.response.set_status(503)
                                self.response.headders['Retry-After'] = 120
                                record.people_to_pay = "\n".join(dispersal_list)
                                record.put()
                            else:
                                url = urltemp
                                result = urlfetch.fetch(url, method="POST", payload="%s|%s|%s" % (who, message, amount) , headers={}, deadline = 10)
                                if result.content.split("|")[0] == "paid":
                                    logging.info("%s was paid %s for %s" % (who, amount, message))
                                    dispersal_list.remove(line)
                                elif result.status_code == 404:
                                    logging.warning("Dispersal %s was stoped at %s due to a bad url: %s" % (id, line, url))
                                    self.response.set_status(503)
                                    self.response.headders['Retry-After'] = 120
                                    record.people_to_pay = "\n".join(dispersal_list)
                                    record.put()
                                else:
                                    logging.error("Dispersal %s had a problem with %s. Status:%s Body%s" % (id, line, result.status_code, result.content))
                        else:
                            logging.error("Dispersal %s had a problem with %s. Status:%s Body%s" % (id, line, result.status_code, result.content))
                    record.people_to_pay = "\n".join(dispersal_list)
                    record.put()
                except (DeadlineExceededError, _ToDatastoreError, db.Timeout ):
                    record.people_to_pay = "\n".join(dispersal_list)
                    record.put()
                    taskqueue.add(url='/paiddist/disperse?id=%s' % (record.key().id()), headers={}, queue_name='Disperse', method='PUT')
                    



class ReDeliverTermList(webapp.RequestHandler):
    def post(self):
        #check linden IP  and allowed avs`
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.Contributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
            logging.info("Illegal attempt to request a list from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
        elif not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance to %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.response.out.write('Currently down for maintenance')
        else:
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]

            try:
                rcpt = str(params['rcpt'])
                query = Purchases.all()
                query.filter('item_reciver =', rcpt)
                items = []
                for item in query:
                    items= items + [item.item]
                result = "%s\n%s" % (rcpt, "\n".join(set(items)))
                logging.info ('Sent paid items list for %s' % rcpt)
                self.response.out.write(result)
            except KeyError:
                logging.error('Key error for paid resender list vendor %s, queue entry: %s|%s   %s' % (self.request.headers['X-SecondLife-Object-Key'], rcpt, lines, sys.exc_info()))
                self.error(403)

class ReDeliver(webapp.RequestHandler):
    def post(self):
        #check linden IP  and allowed avs
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.Contributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
            logging.info("Illegal attempt to request redeliver from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
#don't need this for redelivery
#        elif not db.WRITE_CAPABILITY.is_enabled():
#            self.response.set_status(503)
#            self.response.headders['Retry-After'] = 120
#            logging.info("Told that the db was down for maintenance to %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
#            self.response.out.write('Currently down for maintenance')
        else:
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]

            try:
                rcpt = str(params['rcpt'])
                item_name = params['objname']
                query = Purchases.all(keys_only=True)
                query.filter('item_reciver =', rcpt)
                query.filter('item =', item_name)
                if query.count(1):
                    self.response.out.write(tools.httpin_delivery(self, rcpt, item_name, ""))
#                    token = 'paid_item_%s' % item_name
#                    cacheditem = memcache.get(token)
#                    if cacheditem is None:
#                        paiditem = FreebieItem.gql("WHERE freebie_name = :1", item_name).get()
#                        if paiditem is None:
#                            #could not find item to look up its deliverer.  return an error
#                            logging.error('Error, Paid item %s not found yet was found before. Requested by %s using %s.' % (item_name, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
#                            self.error(503)
#                            return
#                        else:
#                            item = {"name":paiditem.freebie_name, "version":paiditem.freebie_version, "giver":paiditem.freebie_giver, "givers":paiditem.givers, "giver":paiditem.freebie_giver, "baseprice":paiditem.baseprice}
#                            memcache.set(token, yaml.safe_dump(item))
#                    else:
#                        #pull the item's details out of the yaml'd dict
#                        item = yaml.safe_load(cacheditem)
#                    name_version = "%s - %s" % (item_name, item['version'])
#                    if item['givers'] == []:
#                        logging.error('Error, Paid item %s does not have http urls.' % (name))
#                        self.error(503)
#                        return
#                    urls = item['givers']
#                    #need to add a way to rotate the urls
#                    url_token = 'url_%s' % item_name
#                    url_num = memcache.incr(url_token, initial_value=0)
#                    url_num = url_num % ((len(urls)/2))
#                    
#                    count_token = 'item_count_%s' % item_name
#                    memcache.incr(count_token, initial_value=0)
#                    #need to send itme here
#                    result = urlfetch.fetch(urls[url_num*2-1], method="POST", payload="%s|%s" % (name_version, rcpt) , headers={}, deadline = 10)
#                    if result.content == "sent":
#                        self.response.out.write('sent|%s|%s' % (rcpt, name_version))#do we need all of this?
#                    else:
#                        url_num = memcache.incr(url_token, initial_value=0)
#                        url_num = url_num % ((len(urls)/2))
#                        #need to send itme here
#                        result = urlfetch.fetch(urls[url_num*2-1], method="POST", payload="%s|%s" % (name_version, rcpt) , headers={}, deadline = 10)
#                        if result.content == "sent":
#                            self.response.out.write('sent|%s|%s' % (rcpt, name_version))#do we need all of this?
#                        else:
#                            logging.error('Error, Paid item %s did not get sent. Status %s Message from vendor: %s' % (name_version, result.status_code, result.content))
#                            self.error(503)
                else:
                    logging.error('Error, %s has no record of paid item %s yet redelvier requested it.' % (rcpt, item_name))
                    self.error(404)
            except KeyError:
                logging.error('Key error for paid redeliver vendor %s, queue entry: %s|%s   %s' % (self.request.headers['X-SecondLife-Object-Key'], rcpt, item_name, sys.exc_info()))
                self.error(403)                

def main():
    application = webapp.WSGIApplication([
                                        (r'/.*?/deliver',Deliver),
                                        (r'/.*?/disperse',Disperse),
                                        (r'/.*?/urlset',SetDisperseURL),
                                        (r'/.*?/giftdeliver',GiftDeliver),
                                        (r'/.*?/giftreceive',GiftReceive),
                                        (r'/.*?/redeliver',ReDeliver),
                                        (r'/.*?/redelivertermlist',ReDeliverTermList)
                                        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()