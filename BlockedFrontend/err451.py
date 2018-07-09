import re
import logging
import urlparse

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, session, abort

from utils import *
from models import *
from db import *

err451_pages = Blueprint('err451', __name__,
                           template_folder='templates/451')
def get_referrer_domain():
    parts = urlparse.urlparse(request.headers['Referer'])
    return 'http://' + parts.netloc

@err451_pages.route('/')
@err451_pages.route('/<path:site>')
@err451_pages.route('/<isp>/<path:site>')
def err451(site=None, isp=None):
    

    if site is None:
        return abort(404)

    site = fix_path(site)

    try:
        cjurl = CourtJudgmentURL.select_one(g.conn, url=site)
    except ObjectNotFound:
        abort(404)

    judgment = cjurl.get_court_judgment()

    if isp:
        orders = judgment.get_court_orders_by_network()
        if isp not in orders:
            abort(404)
        orders = [orders[isp]]
    else:
        orders = list(judgment.get_court_orders())
    networks = [x['network_name'] for x in orders]

    return render_template('451.html',
                           site=site,
                           cjurl=cjurl,
                           judgment=judgment,
                           power=judgment.get_power(),
                           networks=networks,
                           orders=orders)

