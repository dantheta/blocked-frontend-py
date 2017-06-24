
import re
import logging

from flask import Blueprint, render_template, redirect, request, \
    jsonify, g, url_for

from utils import *

category_pages = Blueprint('category', __name__)


@category_pages.route('/check', methods=['GET'])
@category_pages.route('/check/<mode>', methods=['GET'])
def check(mode=None):
    return render_template('check.html', live = (mode == 'live'))

@category_pages.route('/blocked-sites')
@category_pages.route('/blocked-sites/<int:category>')
@category_pages.route('/blocked-sites/<int:category>/<int:page>')
def blocked_sites(category=1, page=0):
    req = {
        'id': category,
        'recurse': 1,
        'active': 1,
        'page': page,
        }
    req['signature'] = request.api.sign(req, ['id'])
    data = request.api.GET('category/sites/'+str(category), req)
    extra = {}
    if data['total_blocked_url_count'] < 100:
        data2 = request.api.GET('category/'+str(category), req)
        extra['parentid'] =  data2['parents'][-1][0]
        extra['parentname'] =  data2['parents'][-1][1]

    return render_template('blocked-sites.html',data=data, page=page, category=category, **extra)

@category_pages.route('/sites')
@category_pages.route('/sites/<search>')
@category_pages.route('/sites/<search>/<int:page>')
def sites_search(search=None, page=0):
    if search:
        req = {'q': search, 'page': page}
        req['signature'] = request.api.sign(req, ['q'])
        data = request.api.GET('search/url', req)
        logging.info(data)
    else:
        data = None
    return render_template('site-search.html', data=data, page=page, search=search)

@category_pages.route('/sites', methods=['POST'])
def sites_search_post():
    search = request.form['search']
    return redirect(url_for('.sites_search', search=search))

@category_pages.route('/apicategorysearch')
def apicategorysearch():
    req = {
        'search': request.args['term']
    }
    req['signature'] = request.api.sign(req, ['search'])
    data = request.api.GET('category/search', req, decode=False)
    return data

@category_pages.route('/random')
def random():
    data = request.api.GET('ispreport/candidates',{'count':1})
    return redirect(url_for('.site', url=data['results'][0]))

@category_pages.route('/random-category')
def random_category():
    req = {
        'count': 1
        }
    req['signature'] = request.api.sign(req, ['count'])
    data = request.api.GET('category/random', req)
    return redirect(url_for('.blocked_sites', category=data['id']))

@category_pages.route('/site')
@category_pages.route('/site/<path:url>')
def site(url=None):
    if not url:
        url = request.args['url']
    # workaround for apache folding // into /
    url = re.sub(':/(?!/)','://', url)
    req = {
        'url': url,
        }
    req['signature'] = request.api.sign(req, ['url'])
    data = request.api.GET('status/url', req)
    activecount=0
    pastcount=0
    can_unblock = None
    results = [x for x in data['results'] if x['isp_active'] ]
    for item in results:
        if item['status'] == 'blocked':
            activecount += 1
            if item['last_report_timestamp']:
                if can_unblock is None:
                    can_unblock = False
            else:
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


@category_pages.route('/check', methods=['POST'])
def check_post():
    if request.form['submit'] == 'false':
        return redirect(url_for('.site', url=request.form['url']))
    req = {
        'url': request.form['url'],
    }
    req['signature'] = request.api.sign(req, ['url'])
    data = request.api.POST('submit/url', req)
    if data['queued'] == True:
        return render_template('site.html',
            results_blocked=[], results_past=[], results_all=[],
            activecount=0,
            pastcount=0,
            can_unblock=None,
            domain=get_domain(request.form['url']),
            url=request.form['url'],
            md5=data['hash'],
            live=True
            )
    return redirect(url_for('.site', url=request.form['url']))

@category_pages.route('/stream-results-dummy')
def stream_results_dummy():
    from hashlib import md5
    from flask import Response
    import json
    import time

    url = request.args['url']

    def dummy():
        networks = ['BT','Sky','TalkTalk','AAISP']
        yield json.dumps({
            'type': 'status',
            'tag': 'dummy',
            'hash': md5(url).hexdigest(),
            'url': url
            }) + "\r\n"

        for network in networks:
            yield json.dumps({
                'network_name': network,
                'status': 'ok',
                'status_timestamp': get_timestamp(),
                'last_blocked_timestamp': None,
                'first_blocked_timestamp': None,
                'category': None
                }) + "\r\n"
        oldts = get_timestamp()
        time.sleep(2)
        for network in networks:
            yield json.dumps({
                'network_name': network,
                'status': 'blocked',
                'status_timestamp': get_timestamp(),
                'last_blocked_timestamp': get_timestamp(),
                'first_blocked_timestamp': None,
                'category': 'violence'
                }) + "\r\n"
            time.sleep(1)
        for network in networks:
            yield json.dumps({
                'network_name': network,
                'status': 'ok',
                'status_timestamp': get_timestamp(),
                'last_blocked_timestamp': oldts,
                'first_blocked_timestamp': None,
                'category': 'violence'
                }) + "\r\n"
            time.sleep(1)
    return Response(dummy(), content_type='application/json')


@category_pages.route('/stream-results')
def stream_results():
    from flask import Response, stream_with_context
    #hash = request.form['hash']
    url = request.args['url']
    
    def stream():
        req = {
            'url': url,
            'timeout': 20,
            }
        req['date'] = request.api.timestamp()
        req['signature'] = request.api.sign(req, ['url','date'])
        for row in request.api.GET('stream/results', req, _stream=True):
            print row
            yield row+"\r\n"
    return Response(stream_with_context(stream()))

