import logging
from google.appengine.ext import db
from google.appengine.api import urlfetch

relationtypes = ['owns', 'secowns']#valid relation types.  For the sake of consistency
                                    #let's keep only active verbs in this list

from model import  Av, Relation, AppSettings

sharedpass = AppSettings.get_or_insert("sharedpass", value="sharedpassword").value
cmdurl = AppSettings.get_or_insert("cmdurl", value="http://yourcmdapp.appspot.com").value

def key2name(key):
    """given an av uuid, returns av name.  Returns None if av not found"""
    av = Av.get_by_key_name("Av:"+key)
    if av is None:
        av = Av.gql("WHERE id = :1", key).get()
        if av:
            return av.name
        else:
            return None
    else:
        return av.name

def update_av(id, name):
    """update's av's name if key found, else creates entity.  only use request header data.  POST and PUT data are not trustworthy."""
    av = Av.get_by_key_name("Av:"+id)#optimize
    if av is None:
        #Av(key_name="Av:"+id,id = id, name = name).put()
        query = Av.gql("WHERE id = :1", id)
        count = query.count()
        if count == 0:#doesn't exist. save
            Av(key_name="Av:"+id,id = id, name = name).put()
        elif count == 1:#already exists.  just update the name
            av = query.get()
            if (av.name != name):
                av.name = name
                av.put()
        else:#there's more than one record.  delete them all and just save one
            #this should never happen
            logging.error("%s key %s had more than one record in Av.", name, id)
            for record in query:
                record.delete()
            av = Av(key_name="Av:"+id, id = id, name = name)
            av.put()
    elif (av.name != name):
        av.name = name
        av.put()


def getby_subj_type(subj, type):
    """returns all relation entities with given subj, type"""
    return Relation.gql("WHERE subj_id = :1 AND type = :2", subj, type)

def getby_obj_type(obj, type):
    """returns all relation entities with given obj, type"""
    return Relation.gql("WHERE obj_id = :1 AND type = :2", obj, type)

def getby_subj_obj(subj, obj):
    """returns all relation entities with given subj_id and obj_id"""
    return Relation.gql("WHERE subj_id = :1 AND obj_id = :2", subj, obj)

def getby_subj_obj_type(subj, obj, type):
    return Relation.gql("WHERE subj_id =  :1 AND type = :2 and obj_id = :3", subj, type, obj)

def create_unique(subj, type, obj):
    """creates relation with given subj_id, type, and obj_id, if not already present"""
    query = Relation.gql("WHERE subj_id =  :1 AND type = :2 and obj_id = :3", subj, type, obj)
    if query.count() == 0:
        rpc = urlfetch.create_rpc()
        urlfetch.make_fetch_call(rpc, cmdurl + '/relation/?%s/%s/%s' % (type, obj, subj), method="PUT", headers={'sharedpass': sharedpass})
        record = Relation(subj_id = subj, type = type, obj_id = obj)
        record.put()

def delete(subj, type, obj):
    """deletes any and all entities with given subj_id, type, and obj_id"""
    query = Relation.gql("WHERE subj_id =  :1 AND type = :2 and obj_id = :3", subj, type, obj)
    for record in query:
        rpc = urlfetch.create_rpc()
        urlfetch.make_fetch_call(rpc, cmdurl + '/relation/all?%s/%s/%s' % (type, obj, subj), method="DELETE", headers={'sharedpass': sharedpass})
        record.delete()

def del_by_obj(obj):
    """deletes any and all entities with given obj_id"""
    query = Relation.gql("WHERE obj_id = :1", obj)
    for record in query:
        rpc = urlfetch.create_rpc()
        urlfetch.make_fetch_call(rpc, cmdurl + "/relation/obj?null/%s/null" % (obj), method="DELETE", headers={'sharedpass': sharedpass})
        record.delete()

def del_by_obj_type(obj, type):
    """deletes any and all entities with given obj_id and type"""
    query = Relation.gql("WHERE obj_id = :1 AND type = :2", obj, type)
    for record in query:
        rpc = urlfetch.create_rpc()
        urlfetch.make_fetch_call(rpc, cmdurl + "/relation/type?%s/%s/null" % (type, obj), method="DELETE", headers={'sharedpass': sharedpass})
        record.delete()
