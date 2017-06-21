
try:
    import lxml.etree as et
except ImportError:
    import xml.etree as et

import os
import time
import logging
import lockfile
import contextlib
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


    if page in current_app.config['REMOTE_PAGES']:
        load_cms_page(page)

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

def load_cms_page(page):
    if not current_app.config['REMOTE_SRC']:
        return
    logging.info("Running remote_src_fetch")

    cache = RemoteCache(
        current_app.config['CACHE_PATH'],
        current_app.config['CACHE_TIME']
        )

    session = requests.session()

    valid = cache.valid(page)
    if valid is True and current_app.config['REMOTE_RELOAD']:
        valid = False
    logging.info("Cache %s valid: %s", page, valid)
    if not valid:
        try:
            with cache.open(page, True) as cachefile:
                req = get_remote_content(page, session)
                page_fields = parse_remote_content(req.content)

                remote_content[page] = page_fields

                logging.info("writing content")
                cachefile.truncate()
                cachefile.write(req.content)
        except requests.RequestException, exc:
            logging.warn("Fetch error: %s", repr(exc))
            if valid is None:
                logging.warn("No cache file to fall back on")
                raise

    logging.info("Using cached content: %s", page)
    with cache.open(page) as cachefile:
        remote_content[page] = parse_remote_content(cachefile.read())


def get_remote_content(page, session):
    req = session.get(
        current_app.config['REMOTE_SRC'] + page + '.xml', 
        auth=current_app.config['REMOTE_AUTH']
        )
    return req

def parse_remote_content(content):
    doc = et.fromstring(content)
    page_fields = {}
    for child in doc.iterchildren():
        content = child.text
        if content is None:
            continue

        if child.tag == 'region':
            page_fields[child.attrib['name']] = content
        else:
            page_fields[child.tag] = content
    return page_fields

class RemoteCache(object):
    def __init__(self, path, time):
        self.path = path
        self.time = time

    def get_path(self, filename):
        cachefile = os.path.join(self.path, filename)
        return cachefile
        
    @contextlib.contextmanager
    def open(self, filename, lock=False):
        cachefile = self.get_path(filename)
        with open(cachefile, 'a+') as fp:
            fp.seek(0)
            logging.info("Position: %s", fp.tell())
            lock = lockfile.FileLock(cachefile)
            logging.info("Locking: %s", cachefile)
            with lock:
                yield fp
            logging.info("Releasing: %s", cachefile)

    def stat(self, filename):
        return os.stat(self.get_path(filename))

    def valid(self, filename):
        try:
            return (time.time() - os.path.getmtime(
                self.get_path(filename)
                )) < self.time
        except OSError,exc:
            if exc.errno == 2:
                return None
            raise
        

