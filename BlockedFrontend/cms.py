
import math

import logging

import jinja2

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session


cms_pages = Blueprint('cms', __name__,
    template_folder='templates/cms')

REMOTE_TEXT_CONTENT = {
    'index': 'homepage-text',
    'legal-blocks': 'legal-blocks',
    'seized-domains': 'seized-domains'
    }

@cms_pages.route('/')
def index():
    g.remote_content = g.remote.get_content('homepage-text')
    #stats = request.api.stats()
    randomsite = request.api.GET('ispreport/candidates',{'count':1})
    site = request.api.status_url(randomsite['results'][0])
    blockednetworks = [ x['network_id'] for x in site['results']
        if x['status'] == 'blocked' ]
    return render_template('index.html', randomsite=randomsite, site=site, 
        blockednetworks=blockednetworks)

@cms_pages.route('/personal-stories')
def personal_stories():
    g.remote_content = g.remote.get_content('personal-stories')
    return render_template('personal-stories.html')

@cms_pages.route('/legal-blocks')
@cms_pages.route('/legal-blocks/<int:page>')
def legal_blocks(page=1):
    g.remote_content = g.remote.get_content('legal-blocks')
    data = request.api.recent_blocks(page-1)
    blocks = data['results']
    count = data['count']
    return render_template('legal-blocks.html',
            page=page, count=count, pagecount = int(math.ceil(count/25)+1), blocks=blocks)

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
    data = request.api.reports(page-1, isp=isp)
    count = data['count']
    pagecount = int(math.ceil(count/25)+1)
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


