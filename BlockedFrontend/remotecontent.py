
import logging

import requests
import requests_cache
try:
    import lxml.etree as et
except ImportError:
    import xml.etree as et

class RemoteContentCockpit(object):
    UPLOAD_PATH = '/storage/uploads'

    def __init__(self, src, auth, cachefile, reload=False):
        self.src = src
        self.auth = auth
        self.cachefile = cachefile
        self.reload = reload
        self.session = self.get_session()
        self._cache_networks = None

    def get_session(self):
        if self.reload:
            session = requests.session()
        else:
            session = requests_cache.CachedSession(
                self.cachefile,
                allowable_methods=('GET','POST'),
                old_data_on_error=True
                )
        session.headers = {'Authorization': 'Bearer ' + self.auth}
        return session

    def get_content(self, page, _type='pages', filterfield='name'):
        if page == 'chunks':
            return self.get_chunks()
        req = self.session.post(self.src + '/api/collections/get/'+_type,
                                json={'filter':{filterfield: page}}
                                )
        logging.info("Fetching %s: %s",_type, page)
        ret = req.json()
        if 'error' in ret:
            raise ValueError(ret['error'])
        if ret['total'] < 1:
            raise ValueError("Entries " + str(ret['total']))
        return ret['entries'][0]

    def get_collection(self, _type):
        req = self.session.get(self.src + '/api/collections/get/'+_type)
        logging.info("Fetching %s:",_type)
        ret = req.json()
        if 'error' in ret:
            raise ValueError(ret['error'])
        return ret['entries']

    def get_networks(self):
        out = {}
        req = self.session.get(self.src + '/api/collections/get/networkdescriptions')
        for entry in req.json()['entries']:
            out[ entry['name'] ] = entry['description']
        return out

    def get_network(self, name, default=''):
        if not self._cache_networks:
            self._cache_networks = self.get_networks()
            
        return self._cache_networks.get(name, default)

    def get_chunks(self):
        out = {}
        req = self.session.get(self.src + '/api/collections/get/chunks')
        for entry in req.json()['entries']:
            out[ entry['name'] ] = entry['content']
        return out

    def get_asset(self, path):
        req = self.session.get(self.src + self.UPLOAD_PATH + path, allow_redirects=False)
        logging.info("Req: %s, %s %s", req.status_code, req.headers['Content-type'], req.headers.get('location'))
        if req.status_code == 302 and req.headers['location'].startswith('/auth/login'):
            raise ValueError(404)
        if req.status_code != 200:
            raise ValueError(req.status_code)
        return req



class RemoteContentModX(object):
    def __init__(self, src, auth, cachefile, reload=False):
        self.src = src
        self.auth = auth
        self.cachefile = cachefile
        self.reload = reload
        self.session = self.get_session()
        self._cache_networks = None


    def get_content(self, page):
        if not self.src:
            return
        logging.debug("Running remote_src_fetch: %s", self.src + page + '.xml')

        try:
            req = self.get_remote_content(page)
            page_fields = self.parse_remote_content(req.content)

            return page_fields

        except requests.RequestException as exc:
            logging.warn("Fetch error: %s", repr(exc))
            raise

    def get_networks(self):
        req = self.get_remote_content('network-descriptions')
        doc = et.fromstring(req.content)
        networks = {}
        for child in doc.iterchildren():
            content = child.text
            if content is None:
                continue

            if child.tag == 'network':
                networks[child.attrib['name']] = content
        return networks
        
    def get_network(self, name, default=''):
        if not self._cache_networks:
            self._cache_networks = self.get_networks()
            
        return self._cache_networks.get(name, default)

    def get_session(self):
        if self.reload:
            session = requests.session()
        else:
            session = requests_cache.CachedSession(
                self.cachefile,
                old_data_on_error=True
                )
        return session


    def get_remote_content(self, page):
        req = self.session.get(
            self.src + page + '.xml', 
            auth=self.auth
            )
        logging.info("Retrieved %s; cache=%s", 
            page, 
            req.from_cache if hasattr(req, 'from_cache') else None
            )
            
        return req

    def parse_remote_content(self, content):
        doc = et.fromstring(content)
        page_fields = {}
        for child in doc.iterchildren():
            content = child.text
            if content is None:
                continue

            if child.tag in ('region','chunk'):
                page_fields[child.attrib['name']] = content
            else:
                page_fields[child.tag] = content
        return page_fields

RemoteContent = RemoteContentModX

def get_remote_content_loader(loader):
    if loader == 'cockpit':
        return RemoteContentCockpit

    return RemoteContentModX

