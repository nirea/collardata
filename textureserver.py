#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

import os
import lindenip
import logging
import time
import string

import yaml

import wsgiref.handlers
from google.appengine.ext import webapp
from google.appengine.api import memcache

from model import FreebieItem, VendorInfo, Purchases
import model

import distributors




####from google.appengine.tools.appcfg import default

updateTimeout = 180;

def UpdateVendorInfo (vendorkey, vowner, public, sim_id, body):
    logging.info('vendorkey: %s, vowner: %s, public: %s, sim: %s, body: %s' % (vendorkey, vowner, public, sim_id, body))
    db_key = "key_%s" % vendorkey
    t=int(time.time())
    record = VendorInfo.get_by_key_name(db_key)
    sim_id = sim_id[0:string.find(sim_id,'(')]

    if body != "":
        lines = body.split('\n')
        slurl = lines[0]
        parcelName = lines[1]
        parcelRating = lines [2]
    else:
        slurl = ''
        parcelName = ''
        parcelRating = ''

    VendorPageToken = "VendorPage"

    if record is None:
        if public=='1':
            VendorInfo(key_name=db_key, vkey = vendorkey, owner = vowner, slurl = slurl, parcel = parcelName, agerating = parcelRating, lastupdate = t, public = 1, sim = sim_id).put()
            logging.info("Adding vendor %s, now at SLURL %s in sim %s" % (vendorkey, slurl, sim_id))
            memcache.delete(VendorPageToken)


    else:
        if public == '0':
            logging.info("Removing vendor %s as it is set to NON public now" % vendorkey)
            record.delete()
            memcache.delete(VendorPageToken)
        elif record.slurl != slurl:
            record.owner = vowner
            record.slurl = slurl
            record.parcel = parcelName
            record.agerating = parcelRating
            record.lastupdate = t
            record.public = 1
            record.sim = sim_id
            logging.info("Updating info for vendor %s, now at SLURL %s in sim %s" % (vendorkey, slurl, sim_id))
            record.put()
            memcache.delete(VendorPageToken)
        else:
            record.lastupdate = t
            record.public = 1
            logging.info("Updating  timestamp for vendor %s (%d)" % (vendorkey, t))
            record.put()



class StartTextureUpdate(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            t=int(time.time())
            serverkey= self.request.headers['X-SecondLife-Object-Key']
            logging.info('Texture update started from texture server %s at %d' % (serverkey, t))
            # Setting texture time to negative time to signalize texure update is in progress
            currentVersion = int(model.GenericStorage_GetOrPutDefault('TextureTime', '0'))
            if currentVersion < 0:
                if -currentVersion + updateTimeout < t:
                    logging.warning('Texture update timestamp was outdated, allowing texture update (Old timestamp: %d)' % currentVersion)
                else:
                    logging.warning('Texture update requested from texture server %s at %d, but already in progress' % (serverkey, t))
                    self.response.out.write('Update already in progress, try again later' )
                    return
            logging.info('Texture update started from texture server %s at %d' % (serverkey, t))
            model.GenericStorage_Store('TextureTime', '-%d' % t)
            self.response.out.write('Timestamp:%d' % t )


class AddTextures(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            name = self.request.headers['X-SecondLife-Owner-Name']
            serverkey = self.request.headers['X-SecondLife-Object-Key']
            logging.info('Receiving textures from texture server %s' % (serverkey))
            lines = unicode(self.request.body).split('\n')

            for line in lines:
                params = {}
                if line != "":
                    params['item'] = line.split('=')[0]
                    params['texture'] = line.split('=')[1]
                    item = params['item'].split('~')[0]
                    texture = params['texture']
                    if params['item'].find('~')!= -1:
                        tags = params['item'].split('~',1)[1].split('~')
                    else:
                        tags = list()
                    t=int(time.time())
                    ts="%d" % t

                    record = FreebieItem.gql('WHERE freebie_name = :1', item).get()
                    if record is None:
                        logging.info("Item %s not in freebielist, skipping texture %s" % (item ,texture))
                    else:
                        record.freebie_texture_key = texture
                        record.freebie_texture_serverkey = serverkey
                        record.freebie_texture_update= t
                        record.tags = tags
                        record.put()
                        logging.info("Texture updated for %s with %s form server %s at %d" % (item,texture,serverkey,t))
#            model.GenericStorage_Store('TextureTime', ts)
            self.response.out.write('saved')


class AddPrice(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            self.response.headers['Content-Type'] = 'text/plain'
            name = self.request.headers['X-SecondLife-Owner-Name']
            serverkey =self.request.headers['X-SecondLife-Object-Key']
            logging.info('Receiving price info from texture server %s' % (serverkey))
            lines = self.request.body.split('\n')

            for line in lines:
                params = {}
                if line != "":
                    item = line.split('~')[0]

                    t=int(time.time())
                    ts="%d" % t

                    record = FreebieItem.gql('WHERE freebie_name = :1', item).get()
                    if record is None:
                        logging.info("Item %s not in freebielist, skipping price info %s" % (item ,line))
                    else:
                        numParms = line.count('~')
                        if numParms > 0:
                            baseprice = line.split('~')[1]
                            record.baseprice = int(baseprice)
                            if numParms > 2:
                                designer = line.split('~')[2]
                                designer_cut = line.split('~')[3]
                                record.designer_key = designer
                                record.designer_cut = int(designer_cut)
                            record.freebie_texture_update= t
                            record.put()
                            logging.info("Price updated for %s with %s form server %s at %d" % (item,line,serverkey,t))
                            token = 'item_%s' % record.freebie_name
                            token2 = 'paid_item_%s' % record.freebie_name
                            memcache.delete(token)
                            memcache.set(token2, yaml.safe_dump({"name":record.freebie_name, "version":record.freebie_version, "giver":record.freebie_giver, "givers":record.givers, "designer_key":record.designer_key, "designer_cut":record.designer_cut, "baseprice":record.baseprice}))
                        else:
                            logging.info("No info for item %s skipping" % (item))
#            model.GenericStorage_Store('TextureTime', ts)
            self.response.out.write('saved')

class UpdateVersion(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
            self.error(403)
        else:
            done_str = self.request.get('done')
            serverkey= self.request.headers['X-SecondLife-Object-Key']
            logging.info('Finalizing texture update from texture server %s' % (serverkey))
            if not done_str:
                logging.info ('Done not confirmed, something is seriously wrong')
                self.error(402)
            else:
                starttime=int(done_str)
                t=int(time.time())
                ts="%d" % t
                logging.info ('Cleaning all textures for server %s with timestamp below %d' % (serverkey, starttime))

                query = FreebieItem.gql("WHERE freebie_texture_serverkey = :1", serverkey)
                for record in query:
                    if record.freebie_texture_update < starttime:
                        logging.info ('Cleaned info for %s' % record.freebie_name)
                        record.freebie_texture_serverkey = ''
                        record.freebie_texture_update = -1
                        record.freebie_texture_key = ''
                        record.put()

                logging.info ('Version info stored: %s' % ts)
                model.GenericStorage_Store('TextureTime', ts)
                self.response.out.write('Version updated: %s' % ts)




class GetAllTextures(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            av=self.request.headers['X-SecondLife-Owner-Key']
            if not distributors.Distributor_authorized(av): #Really needs to be changed??? function needs to be changed to distributors.authorized_designer as soon as the database for that is fully functioning
                self.error(402)
            else:
                objectkey=self.request.headers['X-SecondLife-Object-Key']
                sim_id = self.request.headers['X-SecondLife-Region']
                logging.info('Texture request from %s in sim %s' % (objectkey, sim_id))

                public = self.request.get('Public')
                paid_items = self.request.get('paid_items', default_value='0')
                #if paid_items == '':
                #    paid_items = '0'
                tags = self.request.get('tags', default_value='all').split('|')
                #if tags == '':
                #   tags = 'all'
                #tags = tags.split('|')
                body = self.request.body
                # Use a query parameter to keep track of the last key of the last
                # batch, to know where to start the next batch.
                last_key_str = self.request.get('start')
                last_version_str = self.request.get('last_version')
                last_version = int(last_version_str)
                current_version = int(model.GenericStorage_GetOrPutDefault('TextureTime', '0'))
                if current_version < 0:
                    # system updating at the moment
                    logging.info ('System in update mode, inform the client')
                    self.response.out.write('Updating')
                else:
                    # normal work mode, lets do check and send texture
                    result =''
                    if not last_version_str:
                        # no last time given so we can use the stored time
                        last_version_str = '0'
                        last_version = 0
                        logging.info ('no last_version, send update')
                    else:
                        last_version = int(last_version_str)
                        logging.info ('last_version (%s)' % last_version_str)
                    if current_version == last_version:
                        logging.info ('Versions are identic, no action needed')
                        UpdateVendorInfo(objectkey, av, public, sim_id, body)
                        self.response.out.write('CURRENT')
                    else:
                        logging.info ('Versions different (DB:%s,Vendor:%s) Starting to send update...' % (current_version, last_version_str))
                        if not last_key_str:
                            last_key = 0
                            result ='version\n%s\n' % current_version
                            logging.info ('no last_key, send from start')
                        else:
                            last_key=int(last_key_str)
                            result ='continue\n%s\n' % current_version
                            logging.info ('last_key was: %s' % last_key_str)
                        query = FreebieItem.all()
                        query.filter('freebie_texture_update >', 0)
                        if paid_items == '0':
                            query.filter('baseprice =', 0)
                        if tags[0] != 'all':
                            query.filter('tags IN', tags)
                        entities = query.fetch(21,last_key)
                        count = 0
                        more = False
                        for texture in entities:
                            count = count + 1
                            if count < 21:
                                logging.info('%s:%d' % (texture.freebie_name,texture.freebie_texture_update))
                                result=result + texture.freebie_name +"\n"+texture.freebie_texture_key+"\n"
                                if tags[0] != 'all':
                                    result=result +texture.tags[0]+"\n"#we only send the first tag
                                if paid_items != '0':
                                    result=result + "%s\n" % texture.baseprice
                            else:
                                last_key=last_key+20
                                result=result + ("startwith\n%d" % (last_key))
                                more = True
                                logging.info ('More texture availabe, request next time from %d' % (last_key))
                        if more == False:
                            logging.info ('Sending finished now')
                            UpdateVendorInfo(objectkey, av, public, sim_id, body)
                            result = result + "end\n"
                        self.response.out.write(result)

class GiftGetAllTextures(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
                av=self.request.headers['X-SecondLife-Owner-Key']
#            if not distributors.Distributor_authorized(av): #Really needs to be changed??? function needs to be changed to distributors.authorized_designer as soon as the database for that is fully functioning
#                self.error(402)
#            else:
                objectkey=self.request.headers['X-SecondLife-Object-Key']
                sim_id = self.request.headers['X-SecondLife-Region']
                logging.info('Gift Texture request from %s in sim %s' % (objectkey, sim_id))
                body = self.request.body
                # Use a query parameter to keep track of the last key of the last
                # batch, to know where to start the next batch.
                last_key_str = self.request.get('start')
                last_version_str = self.request.get('last_version')
                last_version = int(last_version_str)
                current_version = int(model.GenericStorage_GetOrPutDefault('TextureTime', '0'))
                if current_version < 0:
                    # system updating at the moment
                    logging.info ('System in update mode, inform the client')
                    self.response.out.write('Updating')
                else:
                    # normal work mode, lets do check and send texture
                    result =''
                    if not last_version_str:
                        # no last time given so we can use the stored time
                        last_version_str = '0'
                        last_version = 0
                        logging.info ('no last_version, send update')
                    else:
                        last_version = int(last_version_str)
                        logging.info ('last_version (%s)' % last_version_str)
                    if current_version == last_version:
                        logging.info ('Versions are identic, no action needed')
                        self.response.out.write('CURRENT')
                    else:
                        logging.info ('Versions different (DB:%s,Vendor:%s) Starting to send update...' % (current_version, last_version_str))
                        if not last_key_str:
                            last_key = 0
                            result ='version\n%s\n' % current_version
                            logging.info ('no last_key, send from start')
                        else:
                            last_key=int(last_key_str)
                            result ='continue\n%s\n' % current_version
                            logging.info ('last_key was: %s' % last_key_str)
                        query = FreebieItem.all()
                        query.filter('freebie_texture_update >', 0)
                        entities = query.fetch(21,last_key)
                        count = 0
                        more = False
                        for texture in entities:
                            count = count + 1
                            if count < 21:
                                logging.info('%s:%d' % (texture.freebie_name,texture.freebie_texture_update))
                                result=result + texture.freebie_name +"\n"+texture.freebie_texture_key+"\n"
                                result=result + "%s\n" % texture.baseprice
                            else:
                                last_key=last_key+20
                                result=result + ("startwith\n%d" % (last_key))
                                more = True
                                logging.info ('More texture availabe, request next time from %d' % (last_key))
                        if more == False:
                            logging.info ('Sending finished now')
                            result = result + "end\n"
                        self.response.out.write(result)

class GetAllBought(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            av=self.request.headers['X-SecondLife-Owner-Key']
            objectkey=self.request.headers['X-SecondLife-Object-Key']
            sim_id = self.request.headers['X-SecondLife-Region']
            logging.info('Bought items request from %s in sim %s' % (av, sim_id))

            #if paid_items == '':
            #    paid_items = '0'
            #if tags == '':
            #   tags = 'all'
            #tags = tags.split('|')
            body = self.request.body
            # Use a query parameter to keep track of the last key of the last
            # batch, to know where to start the next batch.
            last_key_str = self.request.get('start')
            last_version_str = self.request.get('last_version')
            last_version = int(last_version_str)
            current_version = int(model.GenericStorage_GetOrPutDefault('TextureTime', '0'))
            # normal work mode, lets do check and send texture
            result =''
            logging.info ('Versions different (DB:%s,Vendor:%s) Starting to send update...' % (current_version, last_version_str))
            if not last_key_str:
                last_key = 0
                result ='version\n%s\n' % current_version
                logging.info ('no last_key, send from start')
            else:
                last_key=int(last_key_str)
                result ='continue\n%s\n' % current_version
                logging.info ('last_key was: %s' % last_key_str)
            query = Purchases.all()
            query.filter('item_reciver =', av)
            entities = query.fetch(21,last_key)
            count = 0
            more = False
            for texture in entities:
                count = count + 1
                if count < 21:
                    logging.info('%s:%d' % (texture.freebie_name,texture.freebie_texture_update))
                    result=result + texture.freebie_name +"\n"+texture.freebie_texture_key+"\n"
                else:
                    last_key=last_key+20
                    result=result + ("startwith\n%d" % (last_key))
                    more = True
                    logging.info ('More texture availabe, request next time from %d' % (last_key))
            if more == False:
                logging.info ('Sending finished now')
                result = result + "end\n"
            self.response.out.write(result)

class VersionCheck(webapp.RequestHandler):
    def post(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            av=self.request.headers['X-SecondLife-Owner-Key']
            if not distributors.distributor_authorized(av): # function needs to be changed to distributors.authorized_designer as soon as the database for that is fully functioning
                self.error(402)
            else:
                objectkey=self.request.headers['X-SecondLife-Object-Key']
                public = self.request.get('Public')
                version = self.request.get('tv')
                current_version = model.GenericStorage_GetOrPutDefault('TextureTime', '0')
                logging.info("Texture request from vendor with version %s, db at version %s" % (version, current_version))
                if version:
                    if current_version != version:
                        self.response.out.write('UPDATE:%s' % current_version)
                    else:
                        self.response.out.write('CURRENT')





def main():
    application = webapp.WSGIApplication([
                                        (r'/.*?/starttextureupdate',StartTextureUpdate),
                                        (r'/.*?/updatetextures',AddTextures),
                                        (r'/.*?/updateprices',AddPrice),
                                        (r'/.*?/getalltextures',GetAllTextures),
                                        (r'/.*?/giftgetalltextures',GiftGetAllTextures),
                                        (r'/.*?/versioncheck',VersionCheck),
                                        (r'/.*?/updateversion',UpdateVersion)
                                        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()



# used to add a single texture, not in use for texture server
##class AddTexture(webapp.RequestHandler):
##    def post(self):
##        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
##            self.error(403)
##        elif not self.request.headers['X-SecondLife-Owner-Key'] in model.adminkeys:
##            self.error(403)
##        else:
##            self.response.headers['Content-Type'] = 'text/plain'
##            name = self.request.headers['X-SecondLife-Owner-Name']
##            item = cgi.escape(self.request.get('object'))
##            texture = cgi.escape(self.request.get('texture'))
##            t=int(time.time())
##            ts="%d" % t
##
##            record = VendorTexture.gql('WHERE item_name = :1', item).get()
##            if record is None:
##                NewText = VendorTexture(item_name = item, item_texture = texture, texture_owner = name, item_update_time= t)
##                NewText.put()
##
##                model.GenericStorage_Store('TextureTime',ts)
##                logging.info("Texture created for %s with %s at %d" % (item,texture,t))
##            else:
##                if record.item_texture != texture:
##                    record.item_texture = texture
##                    record.texture_owner = name
##                    model.GenericStorage_Store('TextureTime',ts)
##                    logging.info("Texture updated for %s with %s at %d" % (item,texture,t))
##                else:
##                    logging.info("Texture for %s does not need a change at %d" % (item,t))
##                record.item_update_time= t
##                record.put()
##            self.response.out.write('saved')


# used to get a texture for a single object, not in use on textureserver
##class GetTexture(webapp.RequestHandler):
##    def post(self):
##        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
##            self.error(403)
##        else:
####            av=self.request.headers['X-SecondLife-Owner-Key']
####            if not distributors.authorized(av): # function needs to be changed to distributors.authorized_designer as soon as the database for that is fully functioning
####                self.error(402)
####            else:
##                # Use a query parameter to keep track of the last key of the last
##                # batch, to know where to start the next batch.
##                object = self.request.get('object')
##                if object:
##                    query = VendorTexture.gql('WHERE item_name = :1', object).get()
##                    result="none"
##                    if query is None:
##                        result="none"
##                    else:
##                        result=query.item_name+"|"+query.item_texture
##                    self.response.out.write(result)

