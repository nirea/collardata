from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from model import FreebieItem, Distributor, Contributor
import datetime
import logging


head = '''
<html>
<head>
<title>%s</title>
<script src="/static/sorttable.js"></script>
<style>
body {
    background-color: #000000;
    color: #FFFFFF;
}
input {
    background-color: #000000;
    color: #FF0000;
    outline-color: #000000;
    border-color: #FF0000;
}
table.sortable thead {
    background-color:#202020;
    color:#FFFFFF;
    font-weight: bold;
    cursor: default;
}
</style>
</head>
<body>
<b><a href="/freebielist/">Freebies</a> | <a href="/freebielist/distributors">Distributors</a> | <a href="/freebielist/contributors">Contributors</a></b><p>
'''

end = '''
</body>
</html>
'''



class Distributors(webapp.RequestHandler):
    def get(self):
        message = '''<h1>List of Distributors</h1>
<p>This lists all Distributors currently in the distribution system as of %s.</p>
<table class="sortable" border=\"1\">''' % datetime.datetime.utcnow().isoformat(' ')
        message += '<tr><th>Row</th><th>Distributor</th><th>Key</th></tr><br />\n'
        query = Distributor.gql("")
        dists = []
        for record in query:
            s = '<td>%s</td><td>%s</td>\n' % (record.avname, record.avkey)
            if (s in dists) == False:
                dists += [s]

        for i in range(0,len(dists)):
            message += '<tr><td>%d</td>%s' % (i+1, dists[i])

        message += "</table>"
        self.response.out.write((head % 'Distributor List') + message + end)


class Contributors(webapp.RequestHandler):
    def get(self):
        message = '''<h1>List of Contributors</h1>
<p>This lists all Contributors currently in the distribution system as of %s.</p>
<table class="sortable" border=\"1\">''' % datetime.datetime.utcnow().isoformat(' ')
        message += '<tr><th>Row</th><th>Contributor</th><th>Key</th></tr><br />\n'
        query = Contributor.gql("")
        dists = []
        for record in query:
            s = '<td>%s</td><td>%s</td>\n' % (record.avname, record.avkey)
            if (s in dists) == False:
                dists += [s]

        for i in range(0,len(dists)):
            message += '<tr><td>%d</td>%s' % (i+1, dists[i])

        message += "</table>"
        self.response.out.write((head % 'Contributor List') + message + end)

class MainPage(webapp.RequestHandler):

    def get(self):
        message = '''<h1>List of Freebie items</h1>
<p>This lists all item currently in the distribution system as of %s.</p>
<table class="sortable" border=\"1\">''' % datetime.datetime.utcnow().isoformat(' ')
        message += '<tr><th>Row</th><th>Owner</th><th>Giver ID</th><th>Name</th><th>Version</th><th>Update Date</th><th>Distributor Location</th><th>Texture Key</th><th>Texture Server</th><th>Texture Updatetime</th></tr><br />\n'
        query = FreebieItem.gql("")
        content =[]
        for record in query:
            owner = record.freebie_owner
            if (owner == None):
                owner = '***Not assigned***'
            if (record.freebie_texture_update == None):
                i = -1
            else:
                i = record.freebie_texture_update
            content += ['<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td>\n' % (owner, record.freebie_giver, record.freebie_name, record.freebie_version, record.freebie_timedate, record.freebie_location, record.freebie_texture_key, record.freebie_texture_serverkey, i)]



        content = sorted(content)

        for i in range(0,len(content)):
            message += '<tr><td>%d</td>%s' % (i+1, content[i])

        message += "</table>"
        self.response.out.write((head % 'Freebie Items List') + message + end)


application = webapp.WSGIApplication([
    (r'/.*?/distributors',Distributors),
    (r'/.*?/contributors',Contributors),
    ('.*', MainPage)
     ],
    debug=True)

def real_main():
    run_wsgi_app(application)

def profile_main():
    # This is the main function for profiling
    # We've renamed our original main() above to real_main()
    import cProfile, pstats, StringIO
    prof = cProfile.Profile()
    prof = prof.runctx("real_main()", globals(), locals())
    stream = StringIO.StringIO()
    stats = pstats.Stats(prof, stream=stream)
    stats.sort_stats("time")  # Or cumulative
    stats.print_stats(80)  # 80 = how many to print
    # The rest is optional.
    # stats.print_callees()
    # stats.print_callers()
    logging.info("Profile data:\n%s", stream.getvalue())

if __name__ == "__main__":
    profile_main()