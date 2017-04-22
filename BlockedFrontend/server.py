
import os
import sys
import logging
import datetime

import jinja2
from api import ApiClient
from utils import *

from flask import Flask, render_template, request, jsonify, redirect, \
    url_for, g, abort

app = Flask(__name__)

app.config.from_object('BlockedFrontend.default_settings')
if 'BLOCKEDFRONTEND_SETTINGS' in os.environ:
    app.config.from_envvar('BLOCKEDFRONTEND_SETTINGS')

api = ApiClient(
    app.config['API_EMAIL'],
    app.config['API_SECRET']
    )
if 'API' in app.config:
    api.API = app.config['API']

logging.basicConfig(level=logging.INFO)

#blueprints
from unblock import unblock_pages
app.register_blueprint(unblock_pages)

@app.before_request
def hook_api():
    request.api = api

@app.template_filter('fmtime')
def fmtime(s):
    if not s:
        return ''
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S') \
        .strftime('%d %B, %Y at %H:%M')
    
# static page routing
@app.route('/')
@app.route('/<page>')
def index(page='index'):
    if '/' in page:
        return "Invalid page name", 400
    try:
        return render_template(page + '.html')
    except jinja2.TemplateNotFound:
        abort(404)
    except Exception as exc:
        print repr(exc)
        abort(500)

@app.route('/check', methods=['GET'])
@app.route('/check/live', methods=['GET'])
def check():
    return render_template('check.html', live = (request.path == '/check/live'))

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
    data = api.GET('category/sites/'+str(category), req)
    extra = {}
    if data['total_blocked_url_count'] < 100:
        data2 = api.GET('category/'+str(category), req)
        extra['parentid'] =  data2['parents'][-1][0]
        extra['parentname'] =  data2['parents'][-1][1]

    return render_template('blocked-sites.html',data=data, page=page, category=category, **extra)

@app.route('/sites/<search>')
@app.route('/sites/<search>/<int:page>')
def sites_search(search, page=0):
    req = {'q': search}
    req['signature'] = api.sign(req, ['q'])
    data = api.GET('search/url', req)
    logging.info(data)
    return render_template('site-search.html', data=data, page=page, search=search)

@app.route('/sites', methods=['POST'])
def sites_search_post():
    search = request.form['search']
    return redirect(url_for('sites_search', search=search))

@app.route('/apicategorysearch')
def apicategorysearch():
    req = {
        'search': request.args['term']
    }
    req['signature'] = api.sign(req, ['search'])
    data = api.GET('category/search', req, decode=False)
    return data

@app.route('/random')
def random():
    data = api.GET('ispreport/candidates',{'count':1})
    return redirect(url_for('site', url=data['results'][0]))

@app.route('/random-category')
def random_category():
    req = {
        'count': 1
        }
    req['signature'] = api.sign(req, ['count'])
    data = api.GET('category/random', req)
    return redirect(url_for('blocked_sites', category=data['id']))

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
    can_unblock = False
    results = [x for x in data['results'] if x['isp_active'] ]
    for item in results:
        if item['status'] == 'blocked':
            activecount += 1
            if not item['last_report_timestamp']:
                can_unblock = True
        else:
            if item['last_blocked_timestamp']:
                pastcount += 1
            
        
    return render_template('site.html',
        results_blocked = (result for result in results if result['status'] == 'blocked'),
        results_past = (result for result in results if result['status'] != 'blocked' and result['last_blocked_timestamp']),
        results_all = (result for result in results if result['status'] != 'blocked' and not result['last_blocked_timestamp']),

        activecount=activecount,
        pastcount=pastcount,
        can_unblock=can_unblock,
        domain=get_domain(url),
        url = url
        )


@app.route('/check', methods=['POST'])
def check_post():
    if request.form['submit'] == 'false':
        return redirect(url_for('site', url=request.form['url']))
    req = {
        'url': request.form['url'],
    }
    req['signature'] = api.sign(req, ['url'])
    data = api.POST('submit/url', req)
    print data
    return redirect(url_for('site', url=request.form['url']))


        
@app.route('/_refresh')
@app.route('/_refresh/<remote>')
def refresh(remote='github'):
    import subprocess
    if app.config['UPDATE_PASSWORD'] != request.args['key']:
        return "Refresh target forbidden", 403

    proc=subprocess.Popen(['git','pull',remote,'master'],
        cwd=os.path.dirname(os.path.abspath(sys.argv[0])),
        )
    proc.wait()
    return "OK"


def run():

    app.run(host='0.0.0.0')
