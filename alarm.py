#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

from google.appengine.api import memcache, urlfetch
from google.appengine.ext import webapp
from model import AppSettings
import lindenip
import logging
import model
import os
import wsgiref.handlers


alarm_intervall = 600


def AlarmUrl():
    theurl=memcache.get('alarmurl')
    if theurl is None:
        alarm = AppSettings.get_by_key_name("alarmurl")
        if alarm is None:
            return ''
        else:
            memcache.set('alarmurl', alarm.value)
            return alarm.value
    else:
        return theurl


class SetAlarmURL(webapp.RequestHandler):
    def post(self):
        #check linden IP  and allowed avs
        logging.info('Alarm URL')
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            logging.warning("Illegal attempt to set alarm URL from %s, box %s located in %s at %s" % (self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name'], self.request.headers['X-SecondLife-Region'], self.request.headers['X-SecondLife-Local-Position']))
            self.error(403)
        else:
            alarmurl = self.request.body
            alarm = AppSettings(key_name="alarmurl", value=alarmurl)
            alarm.put()
            memcache.set('alarmurl', alarmurl)
            logging.info('Alarm URL set to %s' % alarmurl)
            self.response.out.write('Added')

def SendAlarm(issue, target, admins, message, redirecturl):
    unique = "alarm_%s_%s" % (issue, target)
    # logging.info('Alarm triggered: %s: %s' % (unique, message))
    notified = memcache.get(unique)
    if notified is None:
        memcache.set(unique, "", alarm_intervall)
        URL = AlarmUrl()
        logging.info('Alarm send for %s to URL %s: \n%s' % (unique, URL, message))
        rpc = urlfetch.create_rpc()
        urlfetch.make_fetch_call(rpc, URL, payload=message, method="POST", headers={'issue': issue, 'target': target, 'admins': admins})


## previously needed to bypass a google restriction, app engine code has changed now
##class Redirect(webapp.RequestHandler):
##    def post(self):
##        RedirURL = AlarmUrl()
##        if (RedirURL == ""):
##            logging.error('Alarm was raised, but no alarm URL existed. Message:\n%s' % message)
##        else:
##            # logging.info('Redirecting to %s' % RedirURL)
##            self.redirect(RedirURL, True)

def main():
    application = webapp.WSGIApplication([(r'/.*?/urlset',SetAlarmURL)
                                        ],
                                       debug=True)
    wsgiref.handlers.CGIHandler().run(application)
##(r'/.*?/redirect/',Redirect)

if __name__ == '__main__':
    main()
