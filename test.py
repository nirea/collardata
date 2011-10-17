#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import cgi
import os
import re
import lindenip

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from model import AvTokenValue

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        av = "2cad26af-c9b8-49c3-b2cd-2f6e2d808022"
        query = AvTokenValue.gql("WHERE av = :1", av)
        for record in query:
            self.response.out.write('%s=%s\n' % (record.token, record.value))

application = webapp.WSGIApplication(
    [('/.*', MainPage)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
