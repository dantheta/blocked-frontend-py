from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from .models import *
from .auth import *
from .utils import *
from .resources import *
from .db import *

from NORM.exceptions import ObjectNotFound,ObjectExists

PAGESIZE = 25

###########################
#  GeoBlocking test pages
###########################

admin_geo_pages = Blueprint('admin_geo', __name__)

@admin_geo_pages.route('/control/geo')
@check_moderator
def admin_geo_index():
    return render_template('geo/geo_index.html')
    pass


@admin_geo_pages.route('/control/geo/anomalies')
@admin_geo_pages.route('/control/geo/anomalies/<int:page>')
@check_moderator
def admin_geo_anomaly_index(page=1):
    count=AnomalyCheckResult.count(g.conn, review='new')
    return render_template('geo/geo_anomaly_index.html',
                           anomalies=AnomalyCheckResult.select_with_urls(g.conn, page-1, PAGESIZE, review='new'),
                           count=count,
                           page=page,
                           pagesize=PAGESIZE,
                           pagecount=get_pagecount(count, PAGESIZE),
                           )
    abort(501)

@admin_geo_pages.route('/control/geo/anomalies/all')
@admin_geo_pages.route('/control/geo/anomalies/all/<int:page>')
@check_moderator
def admin_geo_anomaly_all(page=1):
    count=AnomalyCheckResult.count(g.conn)
    return render_template('geo/geo_anomaly_index.html',
                           anomalies=AnomalyCheckResult.select_with_urls(g.conn, page-1, PAGESIZE),
                           count=count,
                           page=page,
                           pagesize=PAGESIZE,
                           pagecount=get_pagecount(count, PAGESIZE),
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
    rec.update_reviewed(session['userid'], request.form['review'])        
    g.conn.commit()
    
    return redirect(url_for('.admin_geo_anomaly_view', id=id))
