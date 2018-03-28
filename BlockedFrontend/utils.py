import re
import math
import time
import datetime
import urlparse

__all__ = ['get_domain','make_list','get_timestamp', 'parse_timestamp', 'get_pagecount','fix_path','normalize_url']

def get_domain(url):
    p = urlparse.urlsplit(url)
    return p.netloc

def normalize_url(url):
    if not ':' in url or not url.lower().startswith(('http:','https:')):
        url = 'http://' + url
    p = urlparse.urlsplit(url)          
    new = urlparse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path if p.path != '/' else '', p.query, p.fragment))
    return new
    

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
