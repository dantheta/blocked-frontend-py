
import json
from signing import RequestSigner

import requests


class ApiClient(object):
    API = 'https://api.blocked.org.uk/1.2/'
    def __init__(self, username, secret):
        self.username = username
        self.secret = secret
        self.signer = RequestSigner(self.secret)
        self.sign = self.signer.get_signature


    def GET(self, url, data,decode=True):
        data['email'] = self.username
        req = requests.get(self.API + url, params=data)
        if decode:
            return req.json()
        else:
            return req.content

    def POST(self, url, data):
        req = requests.post(self.API + url, data=data)
        return req.json()

    def POST_JSON(self, url, data):
        req = requests.post(self.API + url, data=json.dumps(data),
            headers={'Content-type': 'application/javascript'})
        return req.json()





