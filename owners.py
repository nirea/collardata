#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import os
import lindenip
import logging
import relations

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class GetSubs(webapp.RequestHandler):
    def get(self):
        #check that we're coming from an LL ip
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            av = self.request.headers['X-SecondLife-Owner-Key']
            avname = self.request.headers['X-SecondLife-Owner-Name']
            if avname != "(Loading...)":
                relations.update_av(av, avname)            
            #get all relations for which av is owner or secowner
            subdict = {}
            ownersubs = relations.getby_subj_type(av, 'owns')
            for sub in ownersubs:
                id = sub.obj_id
                if id not in subdict:
                    subdict[id] = relations.key2name(id)
                else:
                    #delete duplicates
                    sub.delete()
                
            secownersubs = relations.getby_subj_type(av, 'secowns')
            for sub in secownersubs:
                id = sub.obj_id
                if id not in subdict:#since you can be both an owner and a secowner, ignore those here already in the owner list
                    subdict[id] = relations.key2name(id)
                    
            out = ''
            for sub in subdict:
                out += '%s,%s,' % (sub, subdict[sub])
            self.response.out.write(out.rstrip(','))
                            
        
class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.out.write('hello world')
                
application = webapp.WSGIApplication(
    [
     (r'/.*?/getsubs',GetSubs),
     ('/.*', MainPage)  
     ], 
    debug=True) 

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()        