
import logging

import requests
import requests_cache
try:
    import lxml.etree as et
except ImportError:
    import xml.etree as et

class RemoteContent(object):
    def __init__(self, src, auth, cachefile, reload=False):
        self.src = src
        self.auth = auth
        self.cachefile = cachefile
        self.reload = reload
        self.session = self.get_session()


    def get_content(self, page):
        if not self.src:
            return
        logging.debug("Running remote_src_fetch")

        try:
            req = self.get_remote_content(page)
            page_fields = self.parse_remote_content(req.content)

            return page_fields

        except requests.RequestException, exc:
            logging.warn("Fetch error: %s", repr(exc))
            raise


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
