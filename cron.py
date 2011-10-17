#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details
import alarm
import logging
import time
import tools


import yaml
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache
from google.appengine.api import taskqueue


from model import VendorInfo, FreebieItem, Purchases, Dispersals, AppSettings, Distributor

# remove outdated vendors within 36-48 hours
VendorRemoveTimeout = 129600
VendorPageToken = "VendorPage"

class CleanVendors(webapp.RequestHandler):
    def get(self):
        t=int(time.time()) - VendorRemoveTimeout;
        logging.info('CRON CleanVendors: Removing vendors older than %d' % t)
        query = VendorInfo.gql("WHERE lastupdate < :1",  t)
        for record in query:
            logging.info('CRON: Vendor info for %s at %s outdated, removing it' % (record.vkey, record.slurl))
            record.delete()
        memcache.delete(VendorPageToken)
        logging.info('CRON CleanVendors: Finished')

def UpdateRecord(key, token):
    item = db.get(key)
    count = int(memcache.get(token))
    item.count += count
    if count > int(memcache.get(token)):
        raise db.Rollback()
    item.put()
    memcache.decr(token, delta=count)

class AccountNewRecords(webapp.RequestHandler):
    def get(self):
        if not db.WRITE_CAPABILITY.is_enabled():
            self.response.set_status(503)
            self.response.headders['Retry-After'] = 120
            logging.info("Told that the db was down for maintenance")
            self.response.out.write('Currently down for maintenance')
        else:
            t=int(time.time()) - 7200;
            logging.info('CRON AccountNewRecords: totaling funds for after %d' % t)
            dispersal = Dispersals()
            commissions_total = 0
            designer_total = 0
            maintainers_total = 0
            total = 0
            maintainers = AppSettings.get_or_insert("maintainers", value="00000000-0000-0000-0000-000000000000|0").value.split("|")
            people_to_pay = []
            query = Purchases.gql("WHERE accounted = :1",  "0")
            for record in query:
                logging.info('CRON: %s|%s' % (record.key().id(), record.seller))
                total += record.amount_paid
                token = 'Distributor_%s' % record.seller
                cacheditem = memcache.get(token)
                if cacheditem is None:
                    dist = Distributor.gql("WHERE avkey = :1", record.seller).get()
                    dist_info = {"max_discount":dist.max_discount, "commission":dist.commission}
                    memcache.set(token, yaml.safe_dump(dist_info))
                else:
                    #pull the item's details out of the yaml'd dict
                    dist_info = yaml.safe_load(cacheditem)
                if dist_info['commission'] > 0:
                    commission = record.paid_amount*dist_info['commission']/100
                    commissions_total += commission
                    stoken = '%s_seller' % (record.seller)
                    commission_total = commission + getattr(dispersal, stoken, 0)
                    setattr(dispersal, stoken, commission_total)
                    people_to_pay.append(stoken)
                name = record.item
                item = tools.get_item(name, True)
                if item is None:
                    logging.error('Error, Paid item %s not found. Requested by %s using %s.' % (name, self.request.headers['X-SecondLife-Owner-Name'], self.request.headers['X-SecondLife-Object-Name']))
                if item['designer_cut'] > 0:
                    cut = record.paid_amount*item['designer_cut']/100
                    designer_total += cut
                    dtoken = '%s_designer' % (item['designer'])
                    cut_total = cut + getattr(dispersal, dtoken, 0)
                    setattr(dispersal, dtoken, cut_total)
                    people_to_pay.append(dtoken)
            for maintainer, amount in zip(maintainers[::2], maintainers[1::2]):
                cut = total*int(amount)/100
                maintainers_total += cut
                mtoken = '%s_maintainer' % (maintainer)
                setattr(dispersal, mtoken, cut)
                people_to_pay.append(mtoken)
            if query.count(1) > 0:
                if total >= (maintainers_total + designer_total + commissions_total):
                    setattr(dispersal, 'commissions_total', commissions_total)
                    setattr(dispersal, 'designers_total', designer_total)
                    setattr(dispersal, 'maintainers_total', maintainers_total)
                    setattr(dispersal, 'dispersal_total', (maintainers_total + designer_total + commissions_total))
                    setattr(dispersal, 'total', total)
                    setattr(dispersal, 'people_to_pay', "\n".join(people_to_pay))
                    dispersal.put()
                    logging.info('CRON AccountNewRecords: saved')
                    #add right url
                    taskqueue.add(url='/paiddist/disperse?id=%s' % (dispersal.key().id()), headers={}, queue_name='Disperse', method='PUT')
                    for record in query:
                        record.accounted = "1"
                        record.put()
                else:
                    logging.error("CRON AccountNewRecords: total dispersal %s is greater than total paid %s" % (maintainers_total + designer_total + commissions_total, total))
                    redirecturl = "not needed?"
                    alarm.SendAlarm('Dispersal', t, True, "total dispersal %s is greater than total paid %s" % (maintainers_total + designer_total + commissions_total, total), redirecturl)
                    self.error(500)
            else:
                logging.info('CRON AccountNewRecords: No records')
            logging.info('CRON AccountNewRecords: Finished')

class UpdateCount(webapp.RequestHandler):
    def get(self):
        logging.info('CRON UpdateCount')
        query = FreebieItem.all().fetch(1000)
        for record in query:
            count_token = 'item_count_%s' % record.freebie_name
            count = memcache.get(count_token)
            if count is not None:
                if int(count) > 1:
                    db.run_in_transaction(UpdateRecord, record.key(), count_token)
                    logging.info('CRON: Count info for %s  updated with %s new requests' % (record.freebie_name, count))
        logging.info('CRON UpdateCount: Finished')

def profile_main():
    # This is the main function for profiling
    # We've renamed our original main() above to real_main()
    import cProfile, pstats, StringIO
    prof = cProfile.Profile()
    prof = prof.runctx("real_main()", globals(), locals())
    stream = StringIO.StringIO()
    stats = pstats.Stats(prof, stream=stream)
    stats.sort_stats("time")  # time Or cumulative
    stats.print_stats(80)  # 80 = how many to print
    # The rest is optional.
    #stats.print_callees()
    #stats.print_callers()
    
    logging.info("Profile data:\n%s", stream.getvalue())


application = webapp.WSGIApplication([
                                      (r'/.*?/CleanVendors',CleanVendors),
                                      (r'/.*?/AccountNewRecords',AccountNewRecords),
                                      (r'/.*?/UpdateCount',UpdateCount)
                                      ], debug=True)
def real_main():
    #wsgiref.handlers.CGIHandler().run(application)
    run_wsgi_app(application)

main = real_main()
if __name__ == '__main__':
    main

