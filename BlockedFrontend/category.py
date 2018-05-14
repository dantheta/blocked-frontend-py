
import re
import logging

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, session

from utils import *
from models import SavedList
from db import *

category_pages = Blueprint('category', __name__,
                           template_folder='templates/category')



@category_pages.route('/blocked-sites')
@category_pages.route('/blocked-sites/<int:category>')
@category_pages.route('/blocked-sites/<int:category>/<int:page>')
def blocked_sites(category=1, page=1):
    session['route'] = 'category'
    pagesize = 20 # defined in API
    req = {
        'id': category,
        'recurse': 1,
        'active': 1,
        'page': page-1,
        }
    req['signature'] = g.api.sign(req, ['id'])
    data = g.api.GET('category/sites/'+str(category), req)
    extra = {}
    if data['total_blocked_url_count'] < 100:
        data2 = g.api.GET('category/'+str(category), req)
        extra['parentid'] =  data2['parents'][-1][0]
        extra['parentname'] =  data2['parents'][-1][1]

    session['category'] = (category, get_pagecount(data['total_blocked_url_count'], pagesize))

    g.remote_content = g.remote.get_content('category-search')
    return render_template('blocked-sites.html',
            pagecount=get_pagecount(data['total_blocked_url_count'], pagesize),
            data=data, page=page, category=category, 
            **extra)

@category_pages.route('/sites')
@category_pages.route('/sites/<search>')
@category_pages.route('/sites/<search>/<int:page>')
def sites_search(search=None, page=1):
    if search:
        session['route'] = 'keyword'

        exclude_adult = request.args.get('exclude_adult', 0)
        data = g.api.search_url(search, page-1, exclude_adult)
        logging.debug(data)
        pagesize = 20 # defined in API
        pagecount = get_pagecount(data['count'], pagesize)
        session['keyword'] = (search, pagecount)
    else:
        data = None
        pagecount = 0
    g.remote_content = g.remote.get_content('keyword-search')
    return render_template('site-search.html', 
            data=data, page=page, search=search, pagecount=pagecount
            )

@category_pages.route('/sites', methods=['POST'])
def sites_search_post():
    search = request.form['search']
    exclude_adult = request.form.get('exclude_adult', '0')
    return redirect(url_for('.sites_search', search=search, exclude_adult=exclude_adult))

@category_pages.route('/apicategorysearch')
def apicategorysearch():
    req = {
        'search': request.args['term']
    }
    req['signature'] = g.api.sign(req, ['search'])
    data = g.api.GET('category/search', req, decode=False)
    return data

@category_pages.route('/random')
def random():
    session['route'] = 'random'
    data = g.api.GET('ispreport/candidates',{'count':1})
    return redirect(url_for('site.site', url=data['results'][0]))

@category_pages.route('/random-category')
def random_category():
    req = {
        'count': 1
        }
    req['signature'] = g.api.sign(req, ['count'])
    data = g.api.GET('category/random', req)
    return redirect(url_for('.blocked_sites', category=data['id']))

@category_pages.route('/sitemap.xml')
def sitemap():
    req = {'parent': 0}
    req['signature'] = g.api.sign(req, ['parent'])
    data = g.api.GET('category/0', req)

    return render_template('sitemap_xml.j2', categories=data['categories'])


