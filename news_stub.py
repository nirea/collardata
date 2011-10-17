#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

#
#
#
#

##import os
##import logging
##import datetime
##import urllib
##import random
##import lindenip
##import relations

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class NewsCheck(webapp.RequestHandler):    
    # """responds to collars querying for new news items. this par tis not in functin anymore, just keeping a stub to reduce error messages
    def get(self):
        # no need to check ips and i removed the rest to save as much cpu time as possible
        self.response.out.write("")


application = webapp.WSGIApplication(
    [('/.*?/check', NewsCheck)
     ],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()    
