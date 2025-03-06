from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from .models import *
from .auth import *
from .utils import *
from .resources import *
from .db import *

from NORM.exceptions import ObjectNotFound,ObjectExists

#################
#
#  Online safety act case administration
#
#################

admin_osa_pages = Blueprint('admin_osa', __name__)

@admin_osa_pages.route('/control/osa')
@check_moderator
def admin_osa_index():
	objlist = OSACase.select_with_urls(g.conn, _orderby='id desc')
	return render_template('osa/osa_index.html',
                            cases=objlist)

@admin_osa_pages.route('/control/osa/add')
@admin_osa_pages.route('/control/osa/edit/<int:id>')
@check_moderator
def admin_osa_edit(id=None):
    case = OSACase(g.conn, id)
    if id is None:
        case['source'] = 'operator'

    return render_template('osa/osa_edit.html', 
                           mode='edit' if id else 'add',
                           url=case.get_url(),
                           case=case
                           )

@admin_osa_pages.route('/control/osa/update', methods=['POST'])
@admin_osa_pages.route('/control/osa/update/<int:id>', methods=['POST'])
@check_moderator
def admin_osa_update(id=None):
    case = OSACase(g.conn, id)

    if id is None:
        url = Url.select_one(g.conn, url=request.form['url'])
        case['urlid'] = url.id

    for f in case.FIELDS:
        if f in ('urlid','contact_id'):
            continue
        elif f in ('shutdown_date'):
            case[f] = request.form[f] or None
        else:
            case[f] = request.form[f]
    case.store()
    g.conn.commit()
    if id is None:
        flash("Record added")
    else:
        flash("Record updated")
    return redirect(url_for('.admin_osa_index'))


@admin_osa_pages.route('/control/osa/view/<int:id>')
@check_moderator
def admin_osa_view(id=None):
    pass

@admin_osa_pages.route('/control/osa/delete/<int:id>')
@check_moderator
def admin_osa_delete(id):
    case = OSACase(g.conn, id)
    case.delete()
    g.conn.commit()
    
    flash("Case {} deleted".format(case.id))
    return redirect(url_for('.admin_osa_index'))
