#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from model import AvTokenValue, AppSettings
import lindenip
import logging
import os
import relations



g_owner = "owner" #token for owner
g_secowner= "secowners" #tokes for secowner

sharedpass = AppSettings.get_or_insert("sharedpass", value="sharedpassword").value
cmdurl = AppSettings.get_or_insert("cmdurl", value="http://yourcmdapp.appspot.com").value


class MainPage(webapp.RequestHandler):
    def delete(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':#only allow access from sl
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            av = self.request.headers['X-SecondLife-Owner-Key']#get owner av key
            avname = self.request.headers['X-SecondLife-Owner-Name']#get owner av name
            subbie = self.request.path.split("/")[-1] #get key of sub from path
            if avname != "(Loading...)":
                relations.update_av(av, avname)#resolve key 2 name for owner
            logging.info("Remove sub request from %s (%s) for sub (%s)" % (av,avname,subbie))
            answer=0
            # first check if owner
            record = AvTokenValue.gql("WHERE av = :1 AND token = :2", subbie, g_owner).get() # request owner record of subbie
            if record is not None:
                #found a record for that subbie
                if av in record.value:
                    # and the av is stil the owner, so remove it
                    ownerlist=record.value.split(",")
                    owner_index=ownerlist.index(av)
                    del ownerlist[owner_index:owner_index+2]
                    if ownerlist == []:
                        #list is emty, so just delete the record
                        record.delete()
                        logging.info("Remove sub request from %s for %s: Primary owner record deleted" % (avname,subbie))
                    else:
                        #build the new secowner list and save it
                        s=""
                        for x in ownerlist:
                            s += x+","
                        logging.info(s.rstrip(','))
                        # update the records value
                        record.value=s.rstrip(',')
                        # and save it
                        record.put()
                        logging.info("Remove sub request from %s for %s: Primary record updated: %s" % (avname,subbie, record.value))

                    #update the reealtion db
                    relations.delete(av,"owns",subbie)
                    # and prepare the answer for sl
                    answer+=1

            #now we do the same for the secowner
            record = AvTokenValue.gql("WHERE av = :1 AND token = :2", subbie, g_secowner).get() # request owner record of subbie
            if record is not None:
                #found a record for that subbie
                if av in record.value:
                    # and the av is stil the owner, so remove it
                    ownerlist=record.value.split(",")
                    owner_index=ownerlist.index(av)
                    del ownerlist[owner_index:owner_index+2]
                    if ownerlist == []:
                        #list is emty, so just delete the record
                        record.delete()
                        logging.info("Remove sub request from %s for %s: Secower owner record deleted" % (avname,subbie))
                    else:
                        #build the new secowner list and save it
                        s=""
                        for x in ownerlist:
                            s += x+","
                        logging.info(s.rstrip(','))
                        # update the records value
                        record.value=s.rstrip(',')
                        # and save it
                        record.put()
                        logging.info("Remove sub request from %s for %s: Secower record updated: %s" % (avname,subbie, record.value))

                    #update the reealtion db
                    relations.delete(av,"secowns",subbie)
                    # and prepare the answer for sl
                    answer+=2

            # updating relation again due to the bug 716: the relations got not always properly updated, so we need to be sure it happens now
            if ((answer==0)|(answer==2)):
                if (relations.delete(av,"owns",subbie)==1):
                    logging.info("Remove sub request from %s for %s: Not in subbies db, but primary owner relation removed" % (avname,subbie))
                    answer+=1
            if ((answer==0)|(answer==1)):
                if (relations.delete(av,"secowns",subbie)==1):
                    logging.info("Remove sub request from %s for %s: Not in subbies db, but secondary owner relation removed" % (avname,subbie))
                    answer+=2

            # in case the answer is 0, something is wrong and the DBs from cmds and data drifted appart. We send a delete request to cmds, which hopfully fixex it
            if answer==0:
                logging.info('Relation not found, sending safety request to cmds')
                result = urlfetch.fetch(cmdurl + '/relation/?safety/%s/%s' % (subbie, av), method="DELETE", headers={'sharedpass': sharedpass})
                if result.status_code == 202:
                    logging.info('Answer from cmds received: %s' % result.content)
                    answer = int(result.content)
                else:
                    logging.info('Problem with answer from cmds, status %d\n%s' % (result.status_code, result.content))

            #answer to sl so we know what happened
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write("%d" % answer)
            self.response.set_status(200)




application = webapp.WSGIApplication(
    [('/.*', MainPage)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
