#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import os
import lindenip
import logging
import string
import wsgiref.handlers

from google.appengine.api import urlfetch
from google.appengine.ext import webapp




class GetGroupName(webapp.RequestHandler):
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        else:
            groupKey = self.request.get('group')
            uplook_url = 'http://world.secondlife.com/group/%s' % groupKey
            answer = urlfetch.fetch(uplook_url, method="GET", follow_redirects=True)
            if answer.status_code == 200:
                body = answer.content
                if 'AccessDenied' in body:
                    logging.info ('Group not found: %s' % groupKey)
                    self.response.out.write('X')
                else:
                    startpos = string.find(body,"<title>") + 7
                    endpos = string.find(body,"</title>")

                    groupname = body[startpos:endpos]
                    logging.info ('Group name for %s resolved: %s' % (groupKey, groupname))
                    self.response.out.write(groupname)

            else:
                logging.info ('Error on group lookup answer: %d' % answer.status_code)
                self.response.out.write('X')



def main():
    application = webapp.WSGIApplication([
                                        (r'/.*?/GetGroupName',GetGroupName)
                                        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()