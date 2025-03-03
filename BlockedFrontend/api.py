
import json
import logging
import datetime

from .signing import RequestSigner

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
            logger.debug("Status: %s", req.status_code)
            if _stream:
                return req.iter_lines()
            elif decode:
                logger.debug("Return: %s", req.content)
                json = req.json()
                if 'success' in json and json['success'] != True:
                    raise APIError(json['error'])
                return json
            else:
                return req.content
        except Exception as exc:
            raise
            raise APIError(*exc.args)

    def POST(self, url, data):
        data['email'] = self.username
        try:
            req = requests.post(self.API + url, data=data)
            logger.debug("Status: %s", req.status_code)
            logger.debug("Return: %s", req.content)
            return req.json()
        except Exception as exc:
            raise APIError(*exc.args)

    def DELETE(self, url, data):
        data['email'] = self.username
        try:
            req = requests.delete(self.API + url, params=data)
            logger.debug("Status: %s", req.status_code)
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
        'status/probes': ['date'],
        'status/url': ['url'],
        'status/blocks': ['date'],
        'status/ispreports': ['date'],
        'status/stats': ['date'],
        'status/country-stats': ['date'],
        'status/isp-stats': ['date'],
        'status/category-stats': ['date'],
        'status/domain-isp-stats': ['date'],
        'status/domain-stats': ['date'],
        'status/ispreport-stats': ['date'],
        'ispreport/blacklist': ['date'],
        'ispreport/flag': ['date','url'],
        'ispreport/unflag': ['date','url'],
        'list/users': ['date'],
        'status/result/': ['date'],
        }

    def _request(self, endpoint, req):
        try:
            req['signature'] = self.sign(req, self.SIGNATURES[endpoint])
        except KeyError:
            for k,v in self.SIGNATURES.items():
                if endpoint.startswith(k):
                    req['signature'] = self.sign(req, v)
                    break
        data = self.GET(endpoint, req)
        return data

    def submit_url(self, url, force=0, source=None, queue=None):
        req = {
            'url': url,
        }
        if force:
            req['force'] = force
        if queue is not None:
            req['queue'] = queue
        if source is not None:
            req['source'] = source
        req['signature'] = self.sign(req, ['url'])
        return self.POST('submit/url', req)

    def status_url(self, url, region=None, normalize=True):
        req = {'url':url, 'normalize': '1' if normalize else '0'}
        if region:
            req['region'] = region
        return self._request('status/url', req)

    def set_status_url(self, url, status, normalize=True):
        req = {'url': url, 'status': status,
               'normalize': '1' if normalize else '0',
               'date': self.timestamp()
               }
        req['signature'] = self.sign(req, ['url'])
        return self.POST('status/url', req)

    def search_url(self, search, page=0, exclude_adult=0, networks=None, tld=None):
        """Search sites by keyword"""

        req = {'q': search, 'page': page, 'exclude_adult': exclude_adult}
        if networks:
            req['networks[]'] = map(lambda x: x.lower(), networks)
        if tld:
            req['domain'] = tld
        return self._request('search/url', req)

    def recent_blocks(self, page, region, format='networkrow', sort='url'):
        req = {'date': self.timestamp(), 'page': str(page), 'format': format, 'sort': sort}
        return self._request('status/blocks/'+region, req)

    def stats(self):
        req = {'date': self.timestamp()}
        return self._request('status/stats', req)

    def country_stats(self):
        req = {'date': self.timestamp()}
        return self._request('status/country-stats', req)

    def reports(self, page, state=None, isp=None, category=None, reportercategory=None, list=None, year=None,
                policy=None, admin=False, order=None, url=None, user=None, url_status=None, age=None):
        req = {'date': self.timestamp(), 'page': str(page)}
        if isp:
            req['isp'] = isp
        if admin:
            req['admin'] = 1
        if state:
            assert state in ('open', 'hold', 'sent', 'closed', 'rejected', 'cancelled', 'reviewed', 'featured',
                             'egregious',
                             'harmless', 'unresolved', 'resubmit', 'accepted', 'rejected', 'not_accepted')
            req[state] = 1
        if category:
            req['category'] = category
        if reportercategory:
            req['reportercategory'] = reportercategory
        if list:
            req['list'] = list
        if order:
            assert order in ('asc','desc')
            req['order'] = order
        if url:
            req['url'] = url
        if url_status:
            req['url_status'] = url_status
        if user:
            req['user'] = user
        if policy is not None:
            if policy == 'true':
                policy = True
            if policy == 'false':
                policy = False
            assert policy in (True, False, 0, 1, '0', '1')
            req['policy'] = int(policy)
        if year:
            req['year'] = int(year)
        if age is not None:
            req['age'] = age
        return self._request('status/ispreports', req)

    def isp_stats(self):
        req = {'date': self.timestamp()}
        return self._request('status/isp-stats', req)

    def category_stats(self):
        req = {'date': self.timestamp()}
        return self._request('status/category-stats', req)

    def domain_stats(self):
        req = {'date': self.timestamp()}
        return self._request('status/domain-stats', req)

    def domain_isp_stats(self):
        req = {'date': self.timestamp()}
        return self._request('status/domain-isp-stats', req)

    def ispreport_stats(self):
        req = {'date': self.timestamp()}
        return self._request('status/ispreport-stats', req)

    def status_probes(self, region):
        req = {'date':self.timestamp()}
        return self._request('status/probes/'+region, req)

    def blacklist_insert(self, domain):
        req = {'date': self.timestamp(), 'domain': domain}
        req['signature'] = self.sign(req, ['date','domain'])
        return self.POST('ispreport/blacklist', req)

    def blacklist_select(self):
        req = {'date': self.timestamp()}
        return self._request('ispreport/blacklist', req)

    def blacklist_delete(self, domain):
        req = {'date': self.timestamp(), 'domain': domain}
        req['signature'] = self.sign(req, ['date','domain'])
        return self.DELETE('ispreport/blacklist', req)

    def reports_flag(self, url, status='abuse'):
        req = {'date':self.timestamp(), 'url': url, 'status': status}
        req['signature'] = self.sign(req, ['date','url'])
        return self.POST('ispreport/flag', req)

    def reports_unflag(self, url):
        req = {'date':self.timestamp(), 'url': url}
        req['signature'] = self.sign(req, ['date','url'])
        return self.POST('ispreport/unflag', req)

    def list_users(self):
        req = {'date': self.timestamp()}
        return self._request('list/users', req)

    def result(self, uuid):
        req = {'date': self.timestamp()}
        return self._request('status/result/'+uuid, req)
