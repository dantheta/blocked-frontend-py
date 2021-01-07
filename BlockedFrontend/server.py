
import os
import sys
import logging
import datetime
import collections

from api import ApiClient
import auth
from utils import *
from .remotecontent import get_remote_content_loader
import db

from flask import Flask, render_template, request,  \
    abort, g, session

app = Flask("BlockedFrontend", subdomain_matching=True)

app.config.from_object('BlockedFrontend.default_settings')
if 'BLOCKEDFRONTEND_SETTINGS' in os.environ:
    app.config.from_envvar('BLOCKEDFRONTEND_SETTINGS')

if app.config.get('SITE_THEME'):
    searchpath = app.jinja_loader.searchpath
    app.jinja_loader.searchpath.insert(0, searchpath[0] + '/' + app.config['SITE_THEME'])

# app.secret_key = app.config['SESSION_KEY']

logging.basicConfig(
    level=getattr(logging, app.config.get('LOGLEVEL', 'INFO')),
    datefmt="[%Y-%m-%dT%H:%M:%S]",
    format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s"

    )
logging.info("API_EMAIL: %s", app.config['API_EMAIL'])
logging.info("REMOTE_SRC: %s", app.config['REMOTE_SRC'])

# blueprints

www_domain = app.config['SUBDOMAIN_MAIN']
app.url_map.default_subdomain = www_domain

if app.config['MODULE_ADMIN']:
    from admin import admin_pages
    app.register_blueprint(admin_pages, subdomain=www_domain)

    from admin_rightsholder import admin_rightsholder_pages
    app.register_blueprint(admin_rightsholder_pages, subdomain=www_domain)

    from admin_savedlists import admin_savedlist_pages
    app.register_blueprint(admin_savedlist_pages, subdomain=www_domain)

    from admin_ispreports import admin_ispreport_pages
    app.register_blueprint(admin_ispreport_pages, subdomain=www_domain)

if app.config.get('SITE_THEME') == '451':
    from err451 import err451_pages
    app.register_blueprint(err451_pages)
else:
    from cms import cms_pages, custom_routing
    custom_routing(app.config['SITE_THEME'])
    app.register_blueprint(cms_pages, subdomain=www_domain)

    from site_results import site_pages
    app.register_blueprint(site_pages, subdomain=www_domain)

    if app.config['MODULE_CATEGORY']:
        from category import category_pages
        app.register_blueprint(category_pages, subdomain=www_domain)

    if app.config['MODULE_UNBLOCK']:
        from unblock import unblock_pages
        app.register_blueprint(unblock_pages, subdomain=www_domain)

    if app.config['MODULE_SAVEDLIST']:
        from savedlists import list_pages
        app.register_blueprint(list_pages, subdomain=www_domain)

    from stats import stats_pages
    app.register_blueprint(stats_pages, subdomain=www_domain)

    from injunctions import injunct_pages
    app.register_blueprint(injunct_pages, subdomain=app.config['SUBDOMAIN_INJUNCTIONS'])

    from cmsassets import cms_assets
    app.register_blueprint(cms_assets, subdomain=www_domain)
    app.register_blueprint(cms_assets, subdomain=app.config['SUBDOMAIN_INJUNCTIONS'])

@app.before_first_request
def setup_db():
    db.setup()


@app.before_request
def open_db():
    if request.path.startswith('/static'):
        return
    g.conn = db.db_connect_pool()


@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'conn'):
        db.db_disconnect(g.conn)


@app.before_request
def hook_api():
    g.api = ApiClient(
        app.config['API_EMAIL'],
        app.config['API_SECRET']
        )
    if 'API' in app.config:
        g.api.API = app.config['API']


@app.before_request
def hook_miscdata():
    if request.path.startswith('/static'):
        return
    from resources import load_data
    g.miscvars = load_data('misc')


@app.template_filter('fmtime')
def fmtime(s):
    if not s:
        return ''
    if isinstance(s, datetime.datetime):
        return s.strftime('%d %B, %Y at %H:%M')
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S') \
        .strftime('%d %B, %Y at %H:%M')


@app.template_filter('fmdate')
def fmdate(s):
    if not s:
        return ''
    if isinstance(s, datetime.date):
        return s.strftime('%d %B, %Y')
    return datetime.datetime.strptime(s, '%Y-%m-%d') \
        .strftime('%d %B, %Y')


@app.template_filter('null')
def null(s, default=''):
    if s is None:
        return default
    if isinstance(s, (str, unicode)) and not s.strip():
        return default
    return s


@app.template_filter('strip')
def strip(s, chars):
    return s.strip(chars)


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


@app.template_filter('customgrouper')
def customgrouper(values, keys):
    import itertools
    """Used by legal blocks template in court orders mode.
    vars: values - list of values
          keys - list of keys
    Groups by compound key made of keys 
    Assumes correctly sorted input.
    """
    return itertools.groupby(
        values,
        lambda values: [values[x] for x in keys],
    )


@app.template_filter('noproto')
def filter_noproto(url):
    import re
    if url is None:
        return None
    return re.sub(r'^https?://', '', url)


@app.template_filter('stripstyletag')
def filter_strip_style(s):
    import re
    
    return re.sub(r'<style[^>]+>.*</style>', '', s)


@app.template_filter('lpad')
def lpad(s, width=20):
    return s.ljust(width)


@app.template_filter('rmtasset')
def rmtasset(path):
    """Convert relative path to CMS asset URL"""
    if path.startswith(('http:', 'https:')):
        return path
    return '/cms/assets' + path


@app.template_filter('strip_email_phone')
def strip_email_phone(value):
    import re
    newvalue = re.sub(r'\+?\d{4,6}\s*[ \-\d]{5,7}', '<phone removed>', value)
    newvalue = re.sub(r'\S+@([\S.])+\.\S+', '<email removed>', newvalue)
    return newvalue


@app.errorhandler(Exception)
def on_error(error):
    logging.warn("Exception: %s", repr(error))
    if app.config['DEBUG']:
        raise
    return render_template('error.html'), 500


@app.before_request
def check_user():
    g.admin = session.get('admin', False)
    g.admin_level = session.get('admin_level', 'admin' if g.admin else 'user')
    g.is_level = auth.is_level
    

@app.before_request
def load_remote_content():
    if request.path.startswith('/static') or request.path.startswith('/assets'):
        return
    if app.config.get('SITE_THEME') == '451':
        return
    g.remote_content = collections.defaultdict(dict)
    g.remote_chunks = collections.defaultdict(lambda: None)

    if app.config.get('REMOTE_SRC'):
        loaderclass = get_remote_content_loader(app.config.get('REMOTE_TYPE'))
        g.remote = loaderclass(
            app.config['REMOTE_SRC'],
            app.config['REMOTE_AUTH'],
            app.config['CACHE_PATH'],
            app.config['REMOTE_RELOAD'] and g.admin,  # remote reload only available to admin users
            )
        logging.debug("Loading chunks")
        g.remote_chunks = g.remote.get_content('chunks')
        logging.debug("Got chunks: %s", g.remote_chunks.keys())


def run():
    app.run(host='0.0.0.0')
