#!/usr/bin/python
#Licensed under the GPLv2 (not later versions)
#see LICENSE.txt for details

#
#
#
#

import os
import logging
import datetime
import urllib
import random
import lindenip
import relations
import tools

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class Article(db.Model):
    """the text of a notice, with author and date/time stamp"""
    title = db.StringProperty()
    author = db.StringProperty()
    text = db.TextProperty()
    dts = db.DateTimeProperty()
    
class Item(db.Model):
    """items in the in-world object will have corresponding records of this class""" 
    name = db.StringProperty()
    giverkey = db.StringProperty()

class Attachment(db.Model):
    """associates an Item with a Article"""
    article = db.ReferenceProperty(Article)
    item = db.StringProperty()
    
class AvLastChecked(db.Model):
    """stores the datetime that the avatar last checked for news"""
    av = db.StringProperty()
    dts = db.DateTimeProperty()
    
def format_article(article):    
    return "%s\n%s\n%s\n\n%s" % (article.title, relations.key2name(article.author), str(article.dts), article.text)
    
class UpdateItems(webapp.RequestHandler):
    """responds to in-world attachment box that give list of items"""

class GiverQueue(webapp.RequestHandler):
    """responds to in-world attachment box querying for deliveries"""
    
class MainPage(webapp.RequestHandler):
    """draws a web form for creating new Articles and attaching Items to them, responds to said web form"""
    def get(self):
        self.response.out.write('hello world')
    
class NewsCheck(webapp.RequestHandler):    
    """responds to collars querying for new news items.  Returns 
    newline-delimited list of new article ids that"""
    def get(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        elif self.request.headers['X-SecondLife-Shard'] != 'Production':
            logging.warning("Attempt while on beta grid %s" % (self.request.headers['X-SecondLife-Shard']))
            self.response.set_status(305)
        else:
            av = self.request.headers['X-SecondLife-Owner-Key']
            query = AvLastChecked.gql('WHERE av = :1', av)
            now = datetime.datetime.now()
            weekago = now + datetime.timedelta(weeks = -1)
            if query.count() == 0:
                #save the check date
                lastchecked = AvLastChecked(av = av, dts = now)
                #no date recorded, just go back a week
                cutoff = weekago
            elif query.count() == 1:
                #there's just one record, as there should be
                lastchecked = query.get()
                cutoff = lastchecked.dts
                
                if cutoff < weekago:
                    cutoff = weekago               
                
                lastchecked.dts = now
            else:
                #there's more than one record somehow.  use the first, delete the duplicates
                lastchecked = query.get() 
                cutoff = lastchecked.dts
                if cutoff < weekago:
                    cutoff = weekago
                    
                for record in query:
                    record.delete()
                #now make a new record
                lastchecked = AvLastChecked(av = av, dts = now)
            lastchecked.put()  
            articles = Article.gql('WHERE dts > :1', cutoff)                              
            self.response.out.write("\n".join([str(x.key()) for x in articles]))            
                
                

class CreateArticle(webapp.RequestHandler):
    """for creating news items from scripts in-world"""
    def put(self):
        if lindenip.inrange(os.environ['REMOTE_ADDR']) != 'Production':
            self.error(403)
        else:
            av = self.request.headers['X-SecondLife-Owner-Key']
            if av in tools.adminkeys:
                #save the notice
                title = urllib.unquote(self.request.path.split("/")[-1])
                article = Article(title = title, author = av, text = self.request.body, dts = datetime.datetime.now())
                article.put()
                self.response.out.write('Saved article %s:\n%s' % (article.key(), format_article(article)))
            else:
                self.error(403)
                
class GetArticle(webapp.RequestHandler):
    def get(self):
        key = self.request.path.split("/")[-1]
        article = db.get(key)
        self.response.out.write(format_article(article))
    
application = webapp.WSGIApplication(
    [('/.*?/article/.*', GetArticle),
     ('/.*?/create/.*', CreateArticle),
     ('/.*?/check', NewsCheck),
     ('/.*', MainPage)
     ], 
    debug=True) 

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()    