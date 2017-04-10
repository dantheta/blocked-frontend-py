import time
import urlparse

__all__ = ['get_domain','make_list','get_timestamp']

def get_domain(url):
    p = urlparse.urlsplit(url)
    return p.netloc

def make_list(item):
    if isinstance(item, list):
        return item
    else:
        return [item]

def get_timestamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')
