
import os
import sys
import time
import urlparse

from api import ApiClient

from flask import Flask,render_template,request,jsonify,redirect
app = Flask(__name__)

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
def index():
    return render_template('index.html')

@app.route('/blocked-sites')
def blocked_sites():
    return render_template('blocked-sites.html')

@app.route('/apicategorysearch')
def apicategorysearch():
    req = {
        'search': request.args['term']
    }
    req['signature'] = app.config['api'].sign(req, ['search'])
    data = app.config['api'].GET('category/search', req, decode=False)
    return data

@app.route('/apicategoryresults')
def apicategoryresults():
    req = {
        'id': request.args['cat'],
        'recurse': 1,
        'active': 1,
        'page': request.args.get('page', 0),
        }
    req['signature'] = app.config['api'].sign(req, ['id'])
    data = app.config['api'].GET('category/sites/'+request.args['cat'],
        req, decode=False)
    return data

@app.route('/site')
def site():
    req = {
        'url': request.args['url'],
        }
    req['signature'] = app.config['api'].sign(req, ['url'])
    data = app.config['api'].GET('status/url', req)
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
        domain= get_domain(request.args['url']),
        url = request.args['url']
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
    print form
    api = app.config['api']

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
        
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/check')
def check():
    return render_template('check.html')

def run(config=None):
    if config:
        apiconf = dict(config.items('api'))
        app.config['api'] = ApiClient(
            apiconf['email'],
            apiconf['secret']
            )
    else:
        app.config['api'] = None

    app.run(host='0.0.0.0', debug=True)
