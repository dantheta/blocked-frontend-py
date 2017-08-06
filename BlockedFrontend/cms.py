
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
    remote_content = g.remote.get_content('homepage-text')
    stats = request.api.stats()
    return render_template('index.html', remote_content=remote_content, stats=stats)

@cms_pages.route('/personal-stories')
def personal_stories():
    remote_content = g.remote.get_content('personal-stories')
    return render_template('personal-stories.html', remote_content=remote_content)

@cms_pages.route('/legal-blocks')
@cms_pages.route('/legal-blocks/<int:page>')
def legal_blocks(page=1):
    remote_content = g.remote.get_content('legal-blocks')
    data = request.api.recent_blocks(page-1)
    blocks = data['results']
    count = data['count']
    return render_template('legal-blocks.html', remote_content=remote_content, 
            page=page, count=count, pagecount = int(math.ceil(count/25)+1), blocks=blocks)

@cms_pages.route('/reported-sites')
@cms_pages.route('/reported-sites/<int:page>')
@cms_pages.route('/reported-sites/<isp>')
@cms_pages.route('/reported-sites/<isp>/<int:page>')
def reported_sites(isp=None, page=1):
    data = request.api.reports(page-1, isp=isp)
    count = data['count']
    return render_template('reports.html',
            current_isp=isp,
            page=page, count=count, pagecount = int(math.ceil(count/25)+1), 
            remote_content = {},
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


    remote_content = {}
    if page in REMOTE_TEXT_CONTENT:
        try:
            remote_content = g.remote.get_content(REMOTE_TEXT_CONTENT[page])
        except Exception:
            pass

    if page in current_app.config['REMOTE_PAGES']:
        # page uses generic template from local filesystem, and pretty much requires
        # remote content
        remote_content = g.remote.get_content(page)

        logging.info("page content: %s", remote_content.keys())
        if set(remote_content.keys()).intersection(
            ['TextAreaFour','TextAreaFive','TextAreaSix']
            ):
            return render_template('remote_content2x3.html',
                content=remote_content
                )
        return render_template('remote_content1x3.html',    
            content=remote_content
            )

    try:
        # template exists in local filesystem, but can accept remote content
        return render_template(page + '.html', remote_content=remote_content)
    except jinja2.TemplateNotFound:
        abort(404)


