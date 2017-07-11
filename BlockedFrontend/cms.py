

import logging

import jinja2

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session


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

    if page in current_app.config['REMOTE_PAGES']:
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
        return render_template(page + '.html')
    except jinja2.TemplateNotFound:
        abort(404)
    except Exception as exc:
        raise
        print repr(exc)
        abort(500)



