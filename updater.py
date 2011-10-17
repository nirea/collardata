#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import cgi
import sys
import os
import logging
import lindenip
import distributors
import wsgiref.handlers
import datetime
import tools
import string

from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import memcache

import yaml

from model import FreebieItem, FreebieDelivery, Deliver

null_key = "00000000-0000-0000-0000-000000000000"

class Check(webapp.RequestHandler):
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            #look for an item with the requested name
            name = cgi.escape(self.request.get('object'))
            version = cgi.escape(self.request.get('version'))
            update = cgi.escape(self.request.get('update'))

            #logging.info('%s checked %s version %s' % (self.request.headers['X-SecondLife-Owner-Name'], name, version))

            item = tools.get_item(name, True)
            if item is None:
                self.response.out.write("NSO %s" % (name))
                return
            if item['baseprice'] > 0:
                    self.response.out.write("NSO %s" % (name))
                    logging.error('Rejecting request: Regquesting a paid item using the update check url by %s, vendor %s located in %s at %s. Item:%s' % 
                              (self.request.headers['X-SecondLife-Owner-Name'],
                               self.request.headers['X-SecondLife-Object-Name'],
                               self.request.headers['X-SecondLife-Region'],
                               self.request.headers['X-SecondLife-Local-Position'],
                               name
                               ))
                    return
            logging.debug('baseprice:%s' % item['baseprice'])
            thisversion = 0.0
            try:
                thisversion = float(version)
            except ValueError:
                avname = self.request.headers['X-SecondLife-Owner-Name']
                logging.error('%s is using %s with bad version "%s" and will be sent an update' % (avname, name, version))

            if thisversion < float(item['version']):
                #get recipient key from http headers or request
                rcpt = self.request.headers['X-SecondLife-Owner-Key']

                #enqueue delivery, if queue does not already contain this delivery
                name_version = "%s - %s" % (name, item['version'])
                if update != "no":
                    if tools.enqueue_delivery(item['giver'], rcpt, name_version, self.request.host_url)==False:
                        self.error(403)
                #queue = FreebieDelivery.gql("WHERE rcptkey = :1 AND itemname = :2", rcpt, name_version)
                #if queue.count() == 0:
                #    delivery = FreebieDelivery(giverkey = item.freebie_giver, rcptkey = rcpt, itemname = name_version)
                #    delivery.put()
                #in the future return null key instead of giver's key
                self.response.out.write("%s|%s - %s" % (null_key, name, item['version']))
            else:
                self.response.out.write('current')

class UpdateItem(webapp.RequestHandler):
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.Contributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
            logging.warning("Illegal attempt to update item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            name = cgi.escape(self.request.get('object'))
            version = cgi.escape(self.request.get('version'))
            giverkey = self.request.headers['X-SecondLife-Object-Key']
            avname = self.request.headers['X-SecondLife-Owner-Name']
            location = '%s @ %s' % (self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position'])
            timestring = datetime.datetime.utcnow()
            url = cgi.escape(self.request.get('url', default_value='None'))
            if url == 'None':
                giverurl = []
            else:
                giverurl = [unicode(giverkey)]
                deliv_box = Deliver.get_or_insert("Deliv:%s" % giverkey, timedate=0, url='None')
                update_dist = False
                if url != deliv_box.url:
                    update_dist = True
                elif timestring - deliv_box.timedate > datetime.timedelta(0, 60):
                    update_dist = True
                if update_dist:
                    deliv_box.url = url
                    deliv_box.timedate = timestring
                    deliv_box.owner = avname
                    deliv_box.location = location
                    deliv_box.put()
            #look for an existing item with that name
            items = FreebieItem.gql("WHERE freebie_name = :1", name)
            item = items.get()
            if (item == None):
                newitem = FreebieItem(freebie_name = name, freebie_version = version, freebie_giver = giverkey, givers = giverurl, freebie_owner = avname, freebie_timedate = timestring, freebie_location = location)
                newitem.put()
                item = newitem
            elif float(version.strip(string.whitespace+string.letters+"()!@#$%^&*~`")) < float(item.freebie_version.strip(string.whitespace+string.letters+"()!@#$%^&*~`")):
                logging.warning('%s owned by %s tried to save item %s version %s and current version is %s' % (giverkey, avname, name, version, item.freebie_version))
            else:
                if float(version.strip(string.whitespace+string.letters+"()!@#$%^&*~`")) > float(item.freebie_version.strip(string.whitespace+string.letters+"()!@#$%^&*~`")):
                    item.givers = []
                    logging.info("New verision clearing box list")
                item.freebie_version = version
                item.freebie_giver = giverkey
                if giverurl != []:
                    if giverkey in item.givers:
                        #item.givers[item.givers.index(giverkey)+1] = url
                        logging.info("Box in list")
                    else:
                        item.givers[:0] = giverurl
                        logging.info("Adding box")
                elif giverkey in item.givers:
                    index = item.givers.index(giverkey)
                    item.givers[index:index] = []
                    logging.warning("Removing box")
                item.freebie_owner = avname
                item.freebie_timedate = timestring
                item.freebie_location = location
                item.put()
            #update item in memcache
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
            self.response.out.write('saved')
            logging.info('saved item %s version %s by %s with urls %s' % (name, item.freebie_version, avname, item.givers))

class DeliveryQueue(webapp.RequestHandler):
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.Contributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
            logging.warning("Illegal attempt to check for item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
        else:
            #get the deliveries where giverkey = key provided (this way we can still have multiple givers)
            giverkey = self.request.headers['X-SecondLife-Object-Key']
            givername = self.request.headers['X-SecondLife-Object-Name']
            pop = cgi.escape(self.request.get('pop'))#true or false.  if true, then remove items from db on returning them
            avname = self.request.headers['X-SecondLife-Owner-Name']
            logging.info('%s (%s) from %s checked' % (givername, giverkey, avname))

# to enable/disable the update routine fast, only need to update old records
            if (False):
                timestring = datetime.datetime.utcnow()
                location = '%s @ %s' % (self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position'])

                query = FreebieItem.gql("WHERE freebie_giver = :1", giverkey)
                for record in query:
                    record.freebie_owner = avname
                    record.freebie_timedate = timestring
                    record.freebie_location = location
                    record.put()
                    logging.info('Updated %s from %s' % (record.freebie_name, avname))

            #deliveries = FreebieDelivery.gql("WHERE giverkey = :1", giverkey)
            token = "deliveries_%s" % giverkey
            deliveries = memcache.get(token)
            if deliveries is not None:
                response = ""
                #take the list of lists and format it
                #write each out in form <objname>|receiverkey, one per line
                out = '\n'.join(['|'.join(x) for x in deliveries])
                self.response.out.write(out)
                logging.info('%s got delivery string\n%s' % (givername, out))
                memcache.delete(token)
            else:
                self.response.out.write('')

def main():
  application = webapp.WSGIApplication([(r'/.*?/check',Check),
                                        (r'/.*?/givercheckin',UpdateItem),
                                        (r'/.*?/deliveryqueue',DeliveryQueue)
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
