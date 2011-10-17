import lindenip
import logging
import cgi
import os

from google.appengine.api import urlfetch
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import relations

relationtypes = ['owns', 'secowns']#valid relation types.  For the sake of consistency
                                    #let's keep only active verbs in this list

from model import AppSettings
import model

sharedpass = AppSettings.get_or_insert("sharedpass", value="sharedpassword").value
cmdurl = AppSettings.get_or_insert("cmdurl", value="http://yourcmdapp.appspot.com").value

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


def RequestName(key):
    URL = "%s/Key2Name/" % AlarmUrl()
    logging.info('Key request send for %s to URL %s' % (key, URL))
    rpc = urlfetch.create_rpc()
    message = key
    # send the request to an SL object
    urlfetch.make_fetch_call(rpc, URL, payload=message, method="POST")



class SetName(webapp.RequestHandler):
    def post(self):
        #check that we're coming from an LL ip
        if not lindenip.inrange(os.environ['REMOTE_ADDR']):
            self.error(403)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            lines = self.request.body.split('\n')
            params = {}
            for line in lines:
                params[line.split('=')[0]] = line.split('=')[1]
            logging.info('Info receided from SL, now storing %s with key %s' % (params['name'], params['key']))
            relations.update_av(params['key'], params['name'])


class GetName2Key(webapp.RequestHandler):
    def get(self):
        if (self.request.headers['sharedpass'] == sharedpass):
            key = cgi.escape(self.request.get('key'))
            logging.info('Key2name request for %s' % (key))
            name = relations.key2name(key)
            if name:
                logging.info('Resolved as %s' % (name))
                self.response.out.write(name)
                self.response.set_status(200)#accepted
            else:
                logging.warning('Could not be resolved! Sending request now to inworld item.')
                RequestName(key)
                self.response.out.write('')
                self.response.set_status(202)#accepted
        else:
            self.error(403)
            logging.error('wrong shared password expecting %s received %s ip address' % (sharedpass,self.request.headers['sharedpass'],os.environ['REMOTE_ADDR']))


class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.out.write('hello world')

application = webapp.WSGIApplication(
    [
     (r'/.*?/getname',GetName2Key),
     (r'/.*?/setname',SetName),
     ('/.*', MainPage)
     ],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()