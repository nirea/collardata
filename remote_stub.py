#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

# stub to prevent a ton of unneeded error messages in the appengine log

import os
import lindenip
import logging

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from model import AvTokenValue

class MainPage(webapp.RequestHandler):
    def get(self):
        #check linden ip
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            av = self.request.headers['X-SecondLife-Owner-Key']
            record = AvTokenValue.gql("WHERE av = :1 AND token = 'owner'", av).get()
            if record is not None:
                owner = record.value.split(",")[0]
                logging.warning('Remote disabled for %s' %  self.request.headers['X-SecondLife-Owner-Name'])
                self.response.out.write("remoteoff|%s" % owner)
            else:
                self.response.out.write("remoteoff|%s" % av)
                logging.warning('Remote disabled for selfowned %s' %  self.request.headers['X-SecondLife-Owner-Name'])

    def put(self):
        #check linden IP
        self.response.out.write("")

application = webapp.WSGIApplication(
    [('.*', MainPage)
     ],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()