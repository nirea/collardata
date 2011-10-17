# Cleo: I suggest to remove comment starting with Cleo


#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import logging
from google.appengine.runtime import DeadlineExceededError
from google.appengine.api.datastore import _ToDatastoreError
#from google.appengine.api.datastore import taskqueue_service_pb
#from google.appengine.api.labs.taskqueue.taskqueue_service_pb import TaskQueueAddRequest


relationtokens = {"owner":"owns", "secowners":"secowns"}#watch for these being saved, and make relations for them

allowed_quota=2048; # maximum allowed amount of data per user, might need to be adopted for 3.4 if we offer storage of bigger values via separate script

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import taskqueue

from model import AvTokenValue, AvData, Av

alltoken = "_all"

class Loader(webapp.RequestHandler):
    def post(self):
        lastav = self.request.get('lastav')
        logging.info('lastav:%s' % (lastav))
        q = Av.gql('WHERE id > :1 Order by id', lastav)
        try:
            for result in q:
                taskqueue.add(url='/convert', params={'av': result.id}, queue_name='SlowConvert')
                lastav = result.id
        except (DeadlineExceededError, _ToDatastoreError, db.Timeout ):
            taskqueue.add(url='/convert/loader?lastav=%s' % (lastav), headers={'lastav': lastav}, queue_name='Loader', method='PUT')
            logging.info('lastav:%s' % (lastav))
    def get(self):
        self.post()
    def put(self):
        self.post()

class CleanLoader(webapp.RequestHandler):
    def post(self):
        q = AvData.all()
        cursor = self.request.get('cursor')
        if (cursor):
            logging.info('cursor:%s' % (cursor))
            q.with_cursor(cursor)
        try:
            for result in q:
                lastav = result.key().id_or_name()
                if result.dynamic_properties() == []:
                    result.delete()
                    logging.info('deleted:%s' % (lastav))
        except (DeadlineExceededError, _ToDatastoreError, db.Timeout ):
            cursor = q.cursor()
            taskqueue.add(url='/convert/cleanloader?cursor=%s' % (cursor), headers={'cursor': cursor}, queue_name='Loader', method='PUT')
            logging.info('lastav:%s cursor:%s' % (lastav, cursor))
    def get(self):
        self.post()
    def put(self):
        self.post()

class Convert(webapp.RequestHandler):
    def post(self):
        av = self.request.get('av')
        data = AvData.get_or_insert(key_name="Data:"+av)
        query = AvTokenValue.gql("WHERE av = :1", av)
        if query.count(1) > 0:
            for record in query:
                if record.value != "leasher,00000000-0000-0000-0000-000000000000":
                    setattr(data, record.token, record.value)
            data.put()
            for record in query:
                record.delete()
        name = Av.get_by_key_name("Av:"+av)
        if name is None:
            namequery = Av.gql("WHERE id = :1", av)
            count = namequery.count()
            if count == 0:#doesn't exist. save
                logging.error("key %s has no record in Av. While converting", av)
            elif count == 1:#already exists.  just update the name
                avname = namequery.get()
                if avname:
                    Av(key_name="Av:"+av, id = av, name = avname.name).put()
                    avname.delete()
            else:#there's more than one record.  delete them all and just save one
                #this should never happen
                logging.error("key %s had more than one record in Av.", av)
                avname = ""
                for record in namequery:
                    avname = record.name
                    record.delete()
                Av(key_name="Av:"+av, id = av, name = avname)


application = webapp.WSGIApplication(
    [(r'/.*?/loader', Loader),
     (r'/.*?/cleanloader', CleanLoader),
      ('/.*', Convert)],
    debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
