import logging
from google.appengine.ext import db
from google.appengine.api import memcache

#only nandana singh and athaliah opus are authorized to add distributors
adminkeys = ['2cad26af-c9b8-49c3-b2cd-2f6e2d808022',
              '98cb0179-bc9c-461b-b52c-32420d5ac8ef',
              'dbd606b9-52bb-47f7-93a0-c3e427857824',
              '8487a396-dc5a-4047-8a5b-ab815adb36f0',
              'b6a9c46a-f74d-4e38-82ed-ab6be71c5c3f',
              'ff64c30a-198a-4415-8a33-7315fe74e160',
              'a23ebb7f-64b2-4af2-9fa9-16b2f3fecd34',
              'a6d249c9-0aa4-440b-98a6-c92d4bafafac']

class Av(db.Model):
    id = db.StringProperty()
    name = db.StringProperty()

class Relation(db.Model):
    subj_id = db.StringProperty()
    type = db.StringProperty()
    obj_id = db.StringProperty()

class AvTokenValue(db.Model):
    av = db.StringProperty()
    token = db.StringProperty()
    value = db.TextProperty()
    
class AvData(db.Expando):
    lastupdate = db.DateTimeProperty(auto_now=True)

class AppSettings(db.Model):
    #token = db.StringProperty(multiline=False)
    value = db.StringProperty(multiline=False)

class Contributor(db.Model):
    avname = db.StringProperty()
    avkey = db.StringProperty()

class Distributor(db.Model):
    avname = db.StringProperty()
    avkey = db.StringProperty()
    max_discount = db.IntegerProperty(required=False, default=0)
    commission = db.IntegerProperty(required=False, default=0)

class FreebieItem(db.Model):
    freebie_name = db.StringProperty(required=True)
    freebie_version = db.StringProperty(required=True)
    freebie_giver = db.StringProperty(required=True)
    givers = db.ListProperty(unicode, required=True)
    freebie_owner = db.StringProperty(required=False)
    freebie_timedate = db.DateTimeProperty(required=False)
    freebie_location = db.StringProperty(required=False)
    freebie_texture_key = db.StringProperty(required=False)
    freebie_texture_serverkey = db.StringProperty(required=False)
    freebie_texture_update = db.IntegerProperty(required=False)
    tags = db.ListProperty(unicode)
    baseprice = db.IntegerProperty(required=False, default=0)
    designer_key = db.StringProperty(required=False)
    designer_cut = db.IntegerProperty(required=False, default=0)
    count = db.IntegerProperty(required=True, default=0)

class Deliver(db.Model):
    url = db.StringProperty(required=True, indexed=False)
    owner = db.StringProperty(required=False)
    timedate = db.DateTimeProperty(required=False)
    location = db.StringProperty(required=False)

class FreebieDelivery(db.Model):
    giverkey = db.StringProperty(required=True)
    rcptkey = db.StringProperty(required=True)
    itemname = db.StringProperty(required=True)#in form "name - version"

class VendorInfo(db.Model):
    vkey = db.StringProperty(required=True)
    owner = db.StringProperty(required=True)
    slurl = db.StringProperty(required=True, indexed=False)
    sim = db.StringProperty(required=False, indexed=False)
    parcel = db.StringProperty(required=True)
    agerating = db.StringProperty(required=True)
    lastupdate = db.IntegerProperty(required=True)
    public = db.IntegerProperty(required=True)
    
class Purchases(db.Model):
    time = db.DateTimeProperty(auto_now_add=True)
    purchaser = db.StringProperty(required=True)
    item = db.StringProperty(required=True)
    seller = db.StringProperty(required=True)
    item_reciver = db.StringProperty(required=True)
    loc = db.StringProperty(required=True)
    vender_name = db.StringProperty(required=True)
    amount_paid = db.IntegerProperty(required=True)
    accounted = db.StringProperty(required=False, default="-1")
    notes = db.StringProperty(required=False, indexed=False)    
    
class Dispersals(db.Expando):
    time = db.DateTimeProperty(auto_now_add=True, auto_now=False)
    dispersed = db.StringProperty()
    
    

def GenericStorage_Store(generic_token, generic_value):
    memtoken = "genstore_%s" % generic_token
    record = AppSettings.get_by_key_name(generic_token)
    if record is None:
        AppSettings(key_name=generic_token, value = generic_value).put()
    else:
        record.value = generic_value
        record.put()
    memcache.set(memtoken, generic_value)
    logging.info("Generic token '%s' saved, Value: %s" % (generic_token,generic_value))

def GenericStorage_Get(generic_token):
    memtoken = "genstore_%s" % generic_token
    value = memcache.get(memtoken)
    if value is None:
        record = AppSettings.get_by_key_name(generic_token)
        if record is not None:
            value = record.value
            logging.info("Generic token '%s' retrieved from DB, Value: %s" % (generic_token,value))
            return value
        else:
            logging.info("Generic token '%s' not found" % (generic_token))
            return ''
    else:
        logging.info("Generic token '%s' retrieved from Memcache, Value: %s" % (generic_token,value))
        return value

def GenericStorage_GetOrPutDefault(generic_token, default):
    memtoken = "genstore_%s" % generic_token
    value = memcache.get(memtoken)
    if value is None:
        record = AppSettings.get_by_key_name(generic_token)
        if record is not None:
            value = record.value
            logging.info("Generic token '%s' retrieved from DB, Value: %s" % (generic_token,value))
            return value
        else:
            logging.info("Generic token '%s' not found putting in '%s'" % (generic_token, default))
            AppSettings(key_name=generic_token, value = default).put()
            memcache.set(memtoken, default)
            return default
    else:
        logging.info("Generic token '%s' retrieved from Memcache, Value: %s" % (generic_token,value))
        return value

