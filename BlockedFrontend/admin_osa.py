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
    flt = request.args.get('filter')
    fltargs = {}
    if flt == 'submitted':
        fltargs['status'] = 'submitted'
    
    objlist = OSACase.select_with_urls(g.conn, _orderby='id desc', **fltargs)
    return render_template('osa/osa_index.html',
                            filter=flt,
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
        #url = Url.select_one(g.conn, url=request.form['url'])
        #case['urlid'] = url.id
        case.submit_url(g.api, request.form['url'])

    for f in case.FIELDS:
        if f in ('urlid','contact_id','archive_url'):
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
def admin_osa_view(id):
    case = OSACase(g.conn, id)
    reviewer = User(g.conn, case['reviewed_userid'])
    return render_template('osa/osa_view.html', 
                           case=case, 
                           reviewer=reviewer,
                           url=case.get_url(),
                           )


@admin_osa_pages.route('/control/osa/verify', methods=['POST'])
@check_moderator
def admin_osa_verify():
    case = OSACase(g.conn, request.form['id'])
    if request.form.get('action') == 'remove':
        case.reset_reviewed()
    else:
        case.update_reviewed(session['userid'], request.form['archive_url'])
    g.conn.commit()
    flash("Verification recorded")
    return redirect(url_for('.admin_osa_view', id=case.id))


@admin_osa_pages.route('/control/osa/delete/<int:id>')
@check_moderator
def admin_osa_delete(id):
    case = OSACase(g.conn, id)
    case.delete()
    g.conn.commit()
    
    flash("Case {} deleted".format(case.id))
    return redirect(url_for('.admin_osa_index'))
