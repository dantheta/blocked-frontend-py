import re
import math
import time
import datetime
import urlparse

__all__ = ['get_domain','make_list','get_timestamp', 'parse_timestamp', 'get_pagecount','fix_path']

def get_domain(url):
    p = urlparse.urlsplit(url)
    return p.netloc

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