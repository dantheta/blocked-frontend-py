
import os
import sys
import logging
import datetime

from api import ApiClient
from utils import *

from flask import Flask, render_template, request,  \
    abort

app = Flask(__name__)

app.config.from_object('BlockedFrontend.default_settings')
if 'BLOCKEDFRONTEND_SETTINGS' in os.environ:
    app.config.from_envvar('BLOCKEDFRONTEND_SETTINGS')

api = ApiClient(
    app.config['API_EMAIL'],
    app.config['API_SECRET']
    )
if 'API' in app.config:
    api.API = app.config['API']

logging.basicConfig(level=logging.INFO)

#blueprints
from category import category_pages
app.register_blueprint(category_pages)

from unblock import unblock_pages
app.register_blueprint(unblock_pages)

from reload import reload_blueprint
app.register_blueprint(reload_blueprint)

from cms import cms_pages
app.register_blueprint(cms_pages)

@app.before_request
def hook_api():
    request.api = api

@app.template_filter('fmtime')
def fmtime(s):
    if not s:
        return ''
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S') \
        .strftime('%d %B, %Y at %H:%M')
    

def run():

    app.run(host='0.0.0.0')
