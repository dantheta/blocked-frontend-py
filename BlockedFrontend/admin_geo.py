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


@admin_geo_pages.route('/control/geo/anomalies')
@check_moderator
def admin_geo_anomaly_index():
    return render_template('geo/geo_anomaly_index.html',
                           anomalies=AnomalyCheckResult.select_with_urls(g.conn),
                           )

@admin_geo_pages.route('/control/geo/anomalies/view/<int:id>')
@check_moderator
def admin_geo_anomaly_view(id):
    rec = AnomalyCheckResult(g.conn, id)
    responses = rec.get_responses()
    url = rec.get_url()
    
    return render_template('geo/geo_anomaly_view.html',
                           anomaly=rec,
                           responses=responses,
                           review_user=rec.get_review_user(),
                           url=url
                           )

@admin_geo_pages.route('/control/geo/anomalies/review/<int:id>', methods=['POST'])
@check_moderator
def admin_geo_anomaly_review(id):
    rec = AnomalyCheckResult(g.conn, id)
    rec.update_reviewed(session['userid'], request.form['reviewed'] == '1')        
    g.conn.commit()
    
    return redirect(url_for('.admin_geo_anomaly_view', id=id))
