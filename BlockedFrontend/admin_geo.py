from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from .models import *
from .auth import *
from .utils import *
from .resources import *
from .db import *

from . import anomaly
from . import helpers

from NORM.exceptions import ObjectNotFound,ObjectExists

###########################
#  GeoBlocking test pages
###########################

admin_geo_pages = Blueprint('admin_geo', __name__)

@admin_geo_pages.route('/control/geo')
@check_moderator
def admin_geo_index():
    return render_template('geo/geo_index.html')
    pass

@admin_geo_pages.route('/control/geo/test', methods=['POST'])
@check_moderator
def admin_geo_test():
    url = request.form['url']
    proxy = current_app.config['GEO_PROXY']

    result = anomaly.test_url(url, proxy)
    return render_template('geo/geo_test.html',
                           url=url,
                           result=result)