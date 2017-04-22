
from flask import Blueprint, render_template, redirect, request, \
    jsonify, g, url_for

from utils import *

category_pages = Blueprint('category', __name__)


@category_pages.route('/check', methods=['GET'])
@category_pages.route('/check/live', methods=['GET'])
def check():
    return render_template('check.html', live = (request.path == '/check/live'))

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

@category_pages.route('/sites/<search>')
@category_pages.route('/sites/<search>/<int:page>')
def sites_search(search, page=0):
    req = {'q': search}
    req['signature'] = request.api.sign(req, ['q'])
    data = request.api.GET('search/url', req)
    logging.info(data)
    return render_template('site-search.html', data=data, page=page, search=search)

@category_pages.route('/sites', methods=['POST'])
def sites_search_post():
    search = request.form['search']
    return redirect(url_for('sites_search', search=search))

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
    return redirect(url_for('site', url=data['results'][0]))

@category_pages.route('/random-category')
def random_category():
    req = {
        'count': 1
        }
    req['signature'] = request.api.sign(req, ['count'])
    data = request.api.GET('category/random', req)
    return redirect(url_for('blocked_sites', category=data['id']))

@category_pages.route('/site')
@category_pages.route('/site/<path:url>')
def site(url=None):
    if not url:
        url = request.args['url']
    req = {
        'url': url,
        }
    req['signature'] = request.api.sign(req, ['url'])
    data = request.api.GET('status/url', req)
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


@category_pages.route('/check', methods=['POST'])
def check_post():
    if request.form['submit'] == 'false':
        return redirect(url_for('site', url=request.form['url']))
    req = {
        'url': request.form['url'],
    }
    req['signature'] = request.api.sign(req, ['url'])
    data = request.api.POST('submit/url', req)
    print data
    return redirect(url_for('site', url=request.form['url']))

