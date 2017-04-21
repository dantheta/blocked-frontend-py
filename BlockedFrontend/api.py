
import json
from signing import RequestSigner

import requests

class APIError(Exception):
    pass

class ApiClient(object):
    API = 'https://api.blocked.org.uk/1.2/'
    def __init__(self, username, secret):
        self.username = username
        self.secret = secret
        self.signer = RequestSigner(self.secret)
        self.sign = self.signer.get_signature


    def GET(self, url, data,decode=True):
        data['email'] = self.username
        try:
            req = requests.get(self.API + url, params=data)
            if decode:
                return req.json()
            else:
                return req.content
        except Exception as exc:
            raise APIError(*exc.args)

    def POST(self, url, data):
        try:
            req = requests.post(self.API + url, data=data)
            return req.json()
        except Exception as exc:
            raise APIError(*exc.args)
    
    def POST_JSON(self, url, data):
        req = requests.post(self.API + url, data=json.dumps(data),
            headers={'Content-type': 'application/javascript'})
        return req.json()





