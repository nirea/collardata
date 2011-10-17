#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import os
import lindenip
import distributors
import logging
import tools
import model


import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.api import memcache


class Deliver(webapp.RequestHandler):
    def post(self):
        #check linden IP  and allowed avs
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not distributors.Distributor_authorized(self.request.headers['X-SecondLife-Owner-Key']):
            logging.info("Illegal attempt to request an item from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
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
                    logging.error('Error, freebie %s not found. Requested by %s using %s.' % (name, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                    self.error(403)
                    return
                # Support new 3.7x collars that have no version in the name.
                if item['version'] == 'NOVERSION':
                    name_version = name
                else:
                    name_version = "%s - %s" % (name, item['version'])
                rcpt = str(params['rcpt'])
                if item['baseprice'] > 0:
                    self.response.out.write("NSO %s" % (name))
                    logging.error('Rejecting request: Regquesting a paid item using the free url by %s, vendor %s located in %s at %s. Item:%s Rcpt:%s' % 
                              (self.request.headers['X-SecondLife-Owner-Name'],
                               self.request.headers['X-SecondLife-Object-Name'],
                               self.request.headers['X-SecondLife-Region'],
                               self.request.headers['X-SecondLife-Local-Position'],
                               name,
                               rcpt
                               ))
                    return
                
                if tools.enqueue_delivery(item['giver'], rcpt, name_version, self.request.host_url):
                    self.response.out.write('%s|%s' % (rcpt, name_version))
                    count_token = 'item_count_%s' % name
                    memcache.incr(count_token, initial_value=0)
                else:
                    logging.error('Enqueing failed for vendor %s, queue entry: %s|%s' % (item['giver'], rcpt, name_version))
                    self.error(403)
            except KeyError:
                logging.error('Key error for vendor %s, queue entry: %s|%s' % (item['giver'], rcpt, name_version))
                self.error(403)


class AddDist(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            #add distributor
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]
            logging.info('Distributor added: %s (%s)' % (params['name'], params['key']))
            distributors.Distributor_add(params['key'], params['name'])
            self.response.out.write('Added distributor %s' % params['name'])

class RemDist(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            #add distributor
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]
            logging.info('Distributor removed: %s (%s)' % (params['name'], params['key']))
            distributors.Distributor_delete(params['key'], params['name'])
            self.response.out.write('Removed Distributor %s' % params['name'])

class AddContrib(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            #add distributor
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]
            logging.info('Contributor added: %s (%s)' % (params['name'], params['key']))
    
            distributors.Contributor_add(params['key'], params['name'])
            self.response.out.write('Added contributor %s' % params['name'])

class RemContrib(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            #add distributor
            #populate a dictionary with what we've been given in post
            #should be newline-delimited, token=value
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]
            logging.info('Contributor removed: %s (%s)' % (params['name'], params['key']))
            distributors.Contributor_delete(params['key'], params['name'])
            self.response.out.write('Removed Contributor %s' % params['name'])



def main():
    application = webapp.WSGIApplication([
                                        (r'/.*?/deliver',Deliver),
                                        (r'/.*?/adddist',AddDist),
                                        (r'/.*?/remdist',RemDist),
                                        (r'/.*?/addcontrib',AddContrib),
                                        (r'/.*?/remcontrib',RemContrib)
                                        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
