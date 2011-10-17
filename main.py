#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details



import wsgiref.handlers

from google.appengine.ext import webapp
    
class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('this is the main app')
        #self.response.out.write(cgi.escape(self.request.get('vidid')))

def main():
    application = webapp.WSGIApplication([('/', MainPage),
                                       ],
                                       debug=True)
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
