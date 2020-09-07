
from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from models import *
from auth import *
from utils import *
from resources import *
from db import *

from NORM.exceptions import ObjectNotFound,ObjectExists

#################
#
#  Copyright-block rightsholder info
#
#################

admin_rightsholder_pages = Blueprint('admin_rightsholder', __name__)

@admin_rightsholder_pages.route('/control/rightsholder')
@check_moderator
def admin_rh_index():
    rhobjlist = Rightsholder.select(g.conn, _orderby='name')

    return render_template('rightsholder/arh_index.html',
                           rightsholders=rhobjlist)

@admin_rightsholder_pages.route('/control/rightsholder/add')
@admin_rightsholder_pages.route('/control/rightsholder/edit/<int:id>')
@check_moderator
def admin_rh_edit(id=None):
    obj = Rightsholder(g.conn, id)

    return render_template('rightsholder/arh_edit.html',
                           rh=obj)

@admin_rightsholder_pages.route('/control/rightsholder/update', methods=['POST'])
@admin_rightsholder_pages.route('/control/rightsholder/update/<int:id>', methods=['POST'])
@check_moderator
def admin_rh_update(id=None):
    obj = Rightsholder(g.conn, id)
    for f in obj.FIELDS:
        obj[f] = request.form[f]
    obj.store()
    g.conn.commit()
    flash("Record updated")
    return redirect(url_for('.admin_rh_index'))


@admin_rightsholder_pages.route('/control/rightsholder/view/<int:id>')
@check_moderator
def admin_rh_view(id=None):
    obj = Rightsholder(g.conn, id)

    return render_template('rightsholder/arh_view.html',
                           rh=obj,
                           judgments=obj.get_court_judgments())

@admin_rightsholder_pages.route('/control/rightsholder/delete/<int:id>')
@check_moderator
def admin_rh_delete(id):
    obj = Rightsholder(g.conn, id)
    obj.delete()
    g.conn.commit()

    flash("\"{0}\" deleted".format(obj['name']))
    return redirect(url_for('.admin_rh_index'))

