
import os
import sys
import logging
import datetime
import collections

from api import ApiClient
from utils import *
from .remotecontent import RemoteContent

from flask import Flask, render_template, request,  \
    abort, g, session

app = Flask("BlockedFrontend")

app.config.from_object('BlockedFrontend.default_settings')
if 'BLOCKEDFRONTEND_SETTINGS' in os.environ:
    app.config.from_envvar('BLOCKEDFRONTEND_SETTINGS')

if app.config.get('SITE_THEME'):
    searchpath = app.jinja_loader.searchpath
    app.jinja_loader.searchpath.insert(0, searchpath[0] + '/' + app.config['SITE_THEME'])

app.logger.info("Search path: %s", app.jinja_loader.searchpath)

api = ApiClient(
    app.config['API_EMAIL'],
    app.config['API_SECRET']
    )
if 'API' in app.config:
    api.API = app.config['API']

app.secret_key = app.config['SESSION_KEY']

logging.basicConfig(
    level=logging.DEBUG,
    datefmt="[%Y-%m-%dT%H:%M:%S]",
    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s"

    )
logging.info("API_EMAIL: %s", app.config['API_EMAIL'])
logging.info("REMOTE_SRC: %s", app.config['REMOTE_SRC'])

#blueprints
from site_results import site_pages
app.register_blueprint(site_pages)

if app.config['MODULE_CATEGORY']:
    from category import category_pages
    app.register_blueprint(category_pages)

if app.config['MODULE_UNBLOCK']:
    from unblock import unblock_pages
    app.register_blueprint(unblock_pages)

if app.config['MODULE_SAVEDLIST']:
    from savedlists import list_pages
    app.register_blueprint(list_pages)

if app.config['MODULE_ADMIN']:
    from admin import admin_pages
    app.register_blueprint(admin_pages)

from reload import reload_blueprint
app.register_blueprint(reload_blueprint)

from stats import stats_pages
app.register_blueprint(stats_pages)

from cms import cms_pages
app.register_blueprint(cms_pages)


@app.before_request
def hook_api():
    request.api = api

@app.template_filter('fmtime')
def fmtime(s):
    if not s:
        return ''
    if isinstance(s, datetime.datetime):
        return s.strftime('%d %B, %Y at %H:%M')
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S') \
        .strftime('%d %B, %Y at %H:%M')


@app.template_filter('null')
def null(s, default):
    if s is None:
        return default
    if isinstance(s, (str,unicode)) and not s.strip():
        return default
    return s

@app.template_filter('join_en')
def join_en(ls, markup=False):
    if markup:
        tag = lambda x: "<span>{0}</span>".format(x)
    else:
        tag = lambda x: x

    if len(ls) == 1:
        return tag(ls[0])
    elif len(ls) >= 2:
        return ", ".join([tag(x) for x in ls[:-1]]) + " and " + tag(ls[-1])
    return ''

@app.template_filter('domain')
def domain(url):
    """Shorten a URL to just the domain"""
    import urlparse
    try:
        parts = urlparse.urlparse(url)
        return parts.netloc
    except Exception as exc:
        logging.warn("filter.domain exception: %s", repr(exc))
        return url
    
@app.errorhandler(Exception)
def on_error(error):
    logging.warn("Exception: %s", repr(error))
    if app.config['DEBUG']:
        raise
    return render_template('error.html'), 500

@app.before_request
def check_user():
    g.admin = session.get('admin', False)
    if app.config['ADMIN_USER'] is None:
        g.admin = True

@app.before_request
def load_remote_data():
    g.remote_content = collections.defaultdict(dict)
    g.remote_chunks = collections.defaultdict(lambda: None)

    if app.config.get('REMOTE_SRC'):
        g.remote = RemoteContent(
            app.config['REMOTE_SRC'],
            app.config['REMOTE_AUTH'],
            app.config['CACHE_PATH'],
            app.config['REMOTE_RELOAD'] and g.admin, # remote reload only available to admin users
            )
        logging.debug("Loading chunks")
        g.remote_chunks = g.remote.get_content('chunks')
        logging.debug("Got chunks: %s", g.remote_chunks.keys())


def run():
    app.run(host='0.0.0.0')
