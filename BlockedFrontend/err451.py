import re
import logging
import urlparse

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, session, abort

from utils import *
from models import *
from db import *

err451_pages = Blueprint('category', __name__,
                           template_folder='templates/451')
def get_referrer_domain():
    parts = urlparse.urlparse(request.headers['Referer'])
    return 'http://' + parts.netloc

@err451_pages.route('/')
@err451_pages.route('/<path:site>')
def err451(site=None):
    conn = db_connect()

    print site

    if site is None:
        return abort(404)

    site = fix_path(site)

    cjurl = CourtJudgmentURL.select_one(conn, url=site)
    judgment = cjurl.get_court_judgment()
    networks = judgment.get_court_order_networks()
    orders = list(judgment.get_court_orders())

    return render_template('451.html',
                           site=site,
                           cjurl=cjurl,
                           judgment=judgment,
                           power=judgment.get_power(),
                           networks=networks,
                           orders=orders)

