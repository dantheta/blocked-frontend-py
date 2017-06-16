
try:
    import lxml.etree as et
except ImportError:
    import xml.etree as et

import logging
import collections

import jinja2
import requests

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app

remote_content = collections.defaultdict(dict)

cms_pages = Blueprint('cms', __name__,
    template_folder='templates/cms')
# static page routing
@cms_pages.route('/')
@cms_pages.route('/<page>')
def index(page='index'):
    if '/' in page:
        return "Invalid page name", 400
    if page == 'favicon.ico':
        return "", 404

    if current_app.config.get('REMOTE_RELOAD',False):
        load_cms_pages()

    if page in remote_content:
        logging.info("page content: %s", remote_content[page].keys())
        if set(remote_content[page].keys()).intersection(
            ['TextAreaFour','TextAreaFive','TextAreaSix']
            ):
            return render_template('remote_content2x3.html',
                content=remote_content[page]
                )
        return render_template('remote_content1x3.html',    
            content=remote_content[page]
            )

    try:
        return render_template(page + '.html')
    except jinja2.TemplateNotFound:
        raise
        abort(404)
    except Exception as exc:
        print repr(exc)
        abort(500)

@cms_pages.before_app_first_request
def load_cms_pages():
    import pprint
    logging.info("Running first_request")
    
    if current_app.config['REMOTE_SRC']:
        session = requests.session()
        for page in current_app.config['REMOTE_PAGES']:
            req = session.get(current_app.config['REMOTE_SRC'] + page + '.xml', 
                auth=current_app.config['REMOTE_AUTH']
                )
            doc = et.fromstring(req.content)
            page_fields = {}
            for child in doc.iterchildren():
                content = et.tostring(child)
                start,end = content.find('>')+1, content.rfind('<')

                if child.tag == 'region':
                    page_fields[child.attrib['name']] = content[start:end]
                else:
                    page_fields[child.tag] = content[start:end]
            remote_content[page] = page_fields

