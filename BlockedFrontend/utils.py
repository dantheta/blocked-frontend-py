import re
import math
import time
import datetime

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

__all__ = ['get_domain','make_list','get_timestamp', 'parse_timestamp', 'get_pagecount',
           'fix_path','normalize_url','is_tag_valid','get_args_helper', 'convertnull']

def get_domain(url):
    p = urlparse.urlsplit(url)
    return p.netloc

def normalize_url(_url):
    url = _url.strip()
    if not ':' in url or not url.lower().startswith(('http:','https:')):
        url = 'http://' + url
    p = urlparse.urlsplit(url)          
    new = urlparse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path if p.path != '/' else '', p.query, p.fragment))
    return new

def is_tag_valid(tag):
    if re.match(r'[a-z0-9-]+$', tag):
        return True
    return False

def get_args_helper(arglist, initial={}):
    from flask import request
    # returns a helper function that will merge supplied parameters onto the existing state URL parameters
    args = initial.copy()
    args.update({x: request.args.get(x) 
            for x in arglist
            if x in request.args and request.args[x] is not None
                 and not (x == 'url' and request.args[x] == '')
                 and x not in initial})

    def helper_func(**kw):
        newargs = args.copy()
        newargs.update(kw)
        if 'page' in kw and kw['page'] is None:
            # remove page when it has been supplied as a positional arg in pagelist macro
            del newargs['page']
        return newargs
    return helper_func

def make_list(item):
    if isinstance(item, list):
        return item
    else:
        return [item]

def get_timestamp():
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())

def parse_timestamp(s):
    if s == "" or s is None:
        return None
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S') 

def get_pagecount(count, pagesize):
    return int(math.ceil(count/pagesize)+1)

def fix_path(url):
    return re.sub(':/(?!/)', '://', url)


def convertnull(value):
    if not isinstance(value,(bytes,str)):
        return value
    return None if value == '' else value
