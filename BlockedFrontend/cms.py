
import logging
import psycopg2
import jinja2

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session

from utils import *
from models import Item

cms_pages = Blueprint('cms', __name__,
    template_folder='templates/cms')

REMOTE_TEXT_CONTENT = {
    'index': 'homepage-text',
    'legal-blocks': 'legal-blocks',
    'seized-domains': 'seized-domains'
    }

def frontpage_lists():
    conn = psycopg2.connect(current_app.config['DB'])
    for item in Item.get_frontpage_random(conn):
        site = request.api.status_url(item['url'])
        return site
        
def frontpage_random():
    randomsite = request.api.GET('ispreport/candidates',{'count':1})
    site = request.api.status_url(randomsite['results'][0])
    return site

@cms_pages.route('/')
def index():
    g.remote_content = g.remote.get_content('homepage-text')
    session['route'] = 'random'
    #stats = request.api.stats()

    if current_app.config['RANDOMSITE'] == 'frontpagerandom':
        site = frontpage_random()
    elif current_app.config['RANDOMSITE'] == 'frontpagelists':
        site = frontpage_lists()

    blockednetworks = [ x['network_id'] for x in site['results']
        if x['status'] == 'blocked' ]
    return render_template('index.html', site=site, blockednetworks=blockednetworks)

@cms_pages.route('/personal-stories')
def personal_stories():
    g.remote_content = g.remote.get_content('personal-stories')
    return render_template('personal-stories.html')

@cms_pages.route('/credits')
def credits():
    g.remote_content = g.remote.get_content('credits')
    return render_template('credits.html')

@cms_pages.route('/legal-blocks')
@cms_pages.route('/legal-blocks/<int:page>')
def legal_blocks(page=1):
    g.remote_content = g.remote.get_content('legal-blocks')
    data = request.api.recent_blocks(page-1)
    blocks = data['results']
    count = data['count']
    urlcount = data['urlcount']
    return render_template('legal-blocks.html',
            page=page, count=count, blocks=blocks, urlcount=urlcount,
            pagecount = get_pagecount(count, 25)
            )

@cms_pages.route('/reported-sites')
@cms_pages.route('/reported-sites/<int:page>')
@cms_pages.route('/reported-sites/<isp>')
@cms_pages.route('/reported-sites/<isp>/<int:page>')
def reported_sites(isp=None, page=1):
    if isp:
        if isp not in current_app.config['ISPS']:
            # search for case insensitive match and redirect
            for _isp in current_app.config['ISPS']:
                if _isp.lower() == isp.lower():
                    return redirect( url_for('.reported_sites', isp=_isp) )
            # otherwise, return a 404
            abort(404)
    g.remote_content = g.remote.get_content('reported-sites')
    data = request.api.reports(page-1, isp=isp)
    count = data['count']
    pagecount = get_pagecount(count, 25)
    if page > pagecount or page < 1:
        abort(404)
    return render_template('reports.html',
            current_isp=isp,
            page=page, count=count, pagecount=pagecount, 
            reports=data['reports'])

@cms_pages.route('/reported-sites', methods=["POST"])
def reported_sites_post():
    f = request.form
    isp = f['isp']
    if isp:
        return redirect( url_for('.reported_sites', isp=isp) )
    else:
        return redirect( url_for('.reported_sites') )

# static page routing
@cms_pages.route('/<page>')
def wildcard(page='index'):
    if '/' in page:
        return "Invalid page name", 400
    if page == 'favicon.ico':
        return "", 404


    g.remote_content = {}
    if page in REMOTE_TEXT_CONTENT:
        try:
            g.remote_content = g.remote.get_content(REMOTE_TEXT_CONTENT[page])
        except Exception:
            pass

    if page in current_app.config['REMOTE_PAGES']:
        # page uses generic template from local filesystem, and pretty much requires
        # remote content
        g.remote_content = g.remote.get_content(page)

        logging.info("page content: %s", g.remote_content.keys())
        if set(g.remote_content.keys()).intersection(
            ['TextAreaFour','TextAreaFive','TextAreaSix']
            ):
            return render_template('remote_content2x3.html',
                content=g.remote_content
                )
        return render_template('remote_content1x3.html',    
            content=g.remote_content
            )

    try:
        # template exists in local filesystem, but can accept remote content
        return render_template(page + '.html')
    except jinja2.TemplateNotFound:
        abort(404)


