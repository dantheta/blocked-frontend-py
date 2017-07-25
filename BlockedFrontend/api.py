
import json
import logging
import datetime

from signing import RequestSigner

import requests

class APIError(Exception):
    pass

logger = logging.getLogger('blocked.api')


class BaseApiClient(object):
    API = 'https://api.blocked.org.uk/1.2/'
    def __init__(self, username, secret):
        self.username = username
        self.secret = secret
        self.signer = RequestSigner(self.secret)
        self.sign = self.signer.get_signature

    def timestamp(self):
        return datetime.datetime.utcnow().strftime(
            '%Y%m%d-%H:%M:%S'
            )

    def GET(self, url, data,decode=True, _stream=False):
        data['email'] = self.username
        try:
            req = requests.get(self.API + url, params=data, stream=_stream)
            logger.info("Status: %s", req.status_code)
            if _stream:
                return req.iter_lines()
            elif decode:
                return req.json()
            else:
                return req.content
        except Exception as exc:
            raise
            raise APIError(*exc.args)

    def POST(self, url, data):
        data['email'] = self.username
        try:
            req = requests.post(self.API + url, data=data)
            logger.info("Status: %s", req.status_code)
            return req.json()
        except Exception as exc:
            raise APIError(*exc.args)
    
    def POST_JSON(self, url, data):
        req = requests.post(self.API + url, data=json.dumps(data),
            headers={'Content-type': 'application/javascript'})
        return req.json()

class ApiClient(BaseApiClient):
    SIGNATURES = {
        'search/url': ['q'],
        'status/blocks': ['date']
        }

    def _request(self, endpoint, req):
        req['signature'] = self.sign(req, self.SIGNATURES[endpoint])
        data = self.GET(endpoint, req)
        return data

    def search_url(self, search, page=0):
        """Search sites by keyword"""

        req = {'q': search, 'page': page}
        return self._request('search/url', req)

    def recent_blocks(self):
        req = {'date': self.timestamp()}
        return self._request('status/blocks', req)


