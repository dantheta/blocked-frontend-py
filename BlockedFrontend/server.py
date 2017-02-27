
import os
import sys
import time
import datetime
import urlparse

from api import ApiClient

from flask import Flask,render_template,request,jsonify,redirect,url_for,g
app = Flask(__name__)

@app.template_filter('fmtime')
def fmtime(s):
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S') \
        .strftime('%d %B, %Y at %H:%M')
    

def get_domain(url):
    p = urlparse.urlsplit(url)
    return p.netloc

def make_list(item):
    if isinstance(item, list):
        return item
    else:
        return [item]

def get_timestamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')

@app.route('/')
@app.route('/<page>')
def index(page='index'):
    if '/' in page:
        return "Invalid page name", 400
    try:
        return render_template(page + '.html')
    except:
        return "Page not found", 404

@app.route('/blocked-sites')
@app.route('/blocked-sites/<int:category>')
@app.route('/blocked-sites/<int:category>/<int:page>')
def blocked_sites(category=1, page=0):
    req = {
        'id': category,
        'recurse': 1,
        'active': 1,
        'page': page,
        }
    req['signature'] = api.sign(req, ['id'])
    data = api.GET('category/sites/'+str(category),
        req)
    return render_template('blocked-sites.html',data=data, page=page, category=category)

@app.route('/apicategorysearch')
def apicategorysearch():
    req = {
        'search': request.args['term']
    }
    req['signature'] = api.sign(req, ['search'])
    data = api.GET('category/search', req, decode=False)
    return data

@app.route('/apicategoryresults')
def apicategoryresults():
    req = {
        'id': request.args['cat'],
        'recurse': 1,
        'active': 1,
        'page': request.args.get('page', 0),
        }
    req['signature'] = api.sign(req, ['id'])
    data = api.GET('category/sites/'+request.args['cat'],
        req, decode=False)
    return data

@app.route('/site')
@app.route('/site/<path:url>')
def site(url=None):
    if not url:
        url = request.args['url']
    req = {
        'url': url,
        }
    req['signature'] = api.sign(req, ['url'])
    data = api.GET('status/url', req)
    activecount=0
    pastcount=0
    results = [x for x in data['results'] if x['isp_active'] ]
    for item in results:
        if item['status'] == 'blocked':
            activecount += 1
        else:
            if item['last_blocked_timestamp']:
                pastcount += 1
            
        
    return render_template('site.html',
        results = results,
        activecount=activecount,
        pastcount=pastcount,
        domain= get_domain(url),
        url = url
        )

@app.route('/unblock')
def unblock():
    url = request.args['url']
    return render_template('unblock.html',
        url=url,
        domain=get_domain(url)
        )

@app.route('/unblock2', methods=['POST'])
def unblock2():
    data = request.form
    return render_template('unblock2.html',
        data=data,
        url=data['url'],
        domain=get_domain(data['url'])
        )

@app.route('/feedback')
def feedback():
    return render_template('feedback.html',
        url = request.args['url'],
        domain=get_domain(request.args['url'])
        )
        

@app.route('/submit-unblock', methods=['POST'])
def submit_unblock():
    if not request.form.get('checkedsite'):
        return None #TODO: message template
    form = request.form
    req = {
        'url': form['url'],
        'reporter': {
            'name': form['name'],
            'email': form['email'],
            },
        'message': form['message'],
        'report_type': ",".join(make_list(form['report_type'])),
        'date': get_timestamp(),
        'send_updates': 1 if form.get('send_updates') else 0,
        'auth': {
            'email': api.username,
            'signature': '',
            }
        }
    if 'networks' in form:
        req['networks'] = make_list(form['networks'])
    req['auth']['signature'] = api.sign(req,  ['url','date'])
    print req
    data = api.POST_JSON('ispreport/submit', req)
    if 'ORG' in form.get('networks',[]):
        return redirect('/thanks?f=1')
    else:
        if data['verification_required']:
            return redirect('/thanks?u=1&v=1')
        else:
            return redirect('/thanks?u=1&v=0')

@app.route('/thanks')
def thanks():
    return render_template('thanks.html',
        u=request.args.get('u'),
        f=request.args.get('f'),
        v=request.args.get('v'),
        )
        
@app.route('/_refresh')
@app.route('/_refresh/<remote>')
def refresh(remote='github'):
    import subprocess
    if app.config['dev_key'] != request.args['key']:
        return "Refresh target forbidden", 403

    print remote
    proc=subprocess.Popen(['git','pull',remote,'master'],
        cwd=os.path.dirname(os.path.abspath(sys.argv[0])),
        )
    proc.wait()
    return "OK"

@app.route('/random')
def random():
    data = api.GET('ispreport/candidates',{'count':1})
    return redirect(url_for('site', url=data['results'][0]))

def run(config=None, dev=None):
    global api
    if config:
        apiconf = dict(config.items('api'))
        api = ApiClient(
            apiconf['email'],
            apiconf['secret']
            )
    else:
        api = None
    app.config['dev_key'] = dev
    print dev

    app.run(host='0.0.0.0', debug=True)
