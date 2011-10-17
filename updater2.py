#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details


import cgi
import logging
import os

import lindenip
import distributors

import wsgiref.handlers

from google.appengine.ext import webapp
from google.appengine.ext import db

null_key = "00000000-0000-0000-0000-000000000000"

class FreebieItem2(db.Model):
    name = db.StringProperty(required=True)
    version = db.StringProperty(required=True)
    giver = db.StringProperty(required=True)
    creator = db.StringProperty(required=True)#key of object creator and dist box owner
    
class FreebieDelivery(db.Model):
    giverkey = db.StringProperty(required=True)
    rcptkey = db.StringProperty(required=True)
    itemname = db.StringProperty(required=True)#in form "name - version"

class Check(webapp.RequestHandler):
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:        
            #self.request.headers
            #look for an item with the requested name
            name = cgi.escape(self.request.get('object'))    
            version = cgi.escape(self.request.get('version'))
            creator = cgi.escape(self.request.get('creator'))
                         
            items = FreebieItem2.gql("WHERE name = :1 AND creator = :2", name, creator)
            item = items.get()   
            if item is None:
                self.error(404)#not found
            elif creator is None:
                self.error(400)#invalid request
            else:
                if float(version) < float(item.version):
                    #get recipient key from http headers or request
                    rcpt = self.request.headers['X-SecondLife-Owner-Key']
                    
                    #enqueue delivery, if queue does not already contain this delivery
                    name_version = "%s - %s" % (name, item.version)
                    delivery = FreebieDelivery(giverkey = item.giver, rcptkey = rcpt, itemname = name_version)
                    delivery.put()
                    self.response.set_status(202)#accepted
                else:
                    self.response.set_status(204)#no content  

class UpdateItem(webapp.RequestHandler):
    def get(self):
        #check the big secret key    
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.authorized(self.request.headers['X-SecondLife-Owner-Key']):
            self.error(403)
        else:
            self.response.headers['Content-Type'] = 'text/plain'            
            name = cgi.escape(self.request.get('object'))    
            version = cgi.escape(self.request.get('version'))
            giverkey = self.request.headers['X-SecondLife-Object-Key']
            creator = self.request.headers['X-SecondLife-Owner-Key']
            
            #look for an existing item with that name
            items = FreebieItem2.gql("WHERE name = :1 AND creator = :2", name, creator)
            item = items.get()
            if item is None:            
                newitem = FreebieItem2(name = name, version = version, giver = giverkey, creator = creator)
                newitem.put()
            else:
                item.version = version
                item.giver = giverkey
                item.creator = creator
                item.put()
            self.response.set_status(202)#accepted
        
class DeliveryQueue(webapp.RequestHandler):
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.authorized(self.request.headers['X-SecondLife-Owner-Key']):
            self.error(403)
        else:        
            #get the deliveries where giverkey = key provided (this way we can still have multiple givers)
            giverkey = self.request.headers['X-SecondLife-Object-Key']
            pop = cgi.escape(self.request.get('pop'))#true or false.  if true, then remove items from db on returning them
            
            
            deliveries = FreebieDelivery.gql("WHERE giverkey = :1", giverkey)
            #write each out in form <objname>|receiverkey
            response = ""
            for delivery in deliveries:
                #make sure the response is shorter than 2048.  If longer, then stop looping and set last line to "more", so giver will know to request again
                if len(response) > 2000:
                    response += "\nmore"
                    break
                else:
                    response += "%s|%s\n" % (delivery.itemname, delivery.rcptkey)
                    #delete from datastore
                    if pop == 'true':
                        delivery.delete()
            self.response.out.write(response)        

def main():
    application = webapp.WSGIApplication([(r'/.*?/check',Check),
                                        (r'/.*?/givercheckin',UpdateItem),
                                        (r'/.*?/deliveryqueue',DeliveryQueue)                                       
                                        ],
                                       debug=True)
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
