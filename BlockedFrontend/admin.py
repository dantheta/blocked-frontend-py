
import os
import logging
import datetime

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash

from models import *
from auth import *
from utils import *

from NORM.exceptions import ObjectNotFound,ObjectExists

admin_pages = Blueprint('admin', __name__, template_folder='templates/admin')

@admin_pages.before_request
def setup_db():
    request.conn = psycopg2.connect(current_app.config['DB'])

@admin_pages.route('/control', methods=['GET'])
def admin():
    if not g.admin:
        return render_template('login.html')

    try:
        cmsdate = datetime.datetime.fromtimestamp(os.path.getmtime(current_app.config['CACHE_PATH']+'.sqlite'))
    except Exception as exc:
        logging.warn("Error getting cache time: %s", exc)
        cmsdate = None

    return render_template('admin.html', cmsdate=cmsdate)

@admin_pages.route('/control/cacheclear', methods=['POST'])
@check_admin
def cacheclear():
    try:
        os.unlink(current_app.config['CACHE_PATH']+'.sqlite')
    except Exception as exc:
        abort(500)

    return redirect(url_for('.admin'))


@admin_pages.route('/control', methods=['POST'])
def admin_post():
    if not (current_app.config.get('ADMIN_USER') and current_app.config.get('ADMIN_PASSWORD')):
        abort(403)

    if current_app.config['ADMIN_USER'] == request.form['username'] and \
        current_app.config['ADMIN_PASSWORD'] == request.form['password']:

        session['admin'] = True
        flash("Admin login successful")
        return redirect(url_for('.admin'))

    return render_template('login.html', message='Incorrect username or password')

@admin_pages.route('/control/logout')
@check_admin
def logout():
    del session['admin']
    return redirect(url_for('.admin'))

@admin_pages.route('/control/url/submit', methods=['POST'])
@check_admin
def forcecheck():
    data = request.api.submit_url(request.form['url'], force=1)
    if data['success']:
        flash("URL submitted successfully")
    else:
        flash("Error submitting result")
    return redirect(url_for('.admin'))

@admin_pages.route('/control/savedlists')
@check_admin
def savedlists():
    return render_template('listindex.html',
        lists=SavedList.select(request.conn, _orderby='name')
        )

@admin_pages.route('/control/savedlists/delete/<int:id>')
@check_admin
def savedlist_delete(id):
    savedlist = SavedList(request.conn, id=id)
    savedlist.delete()
    request.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/show/<int:id>')
@check_admin
def savedlist_show(id):
    savedlist = SavedList(request.conn, id=id)
    savedlist['public'] = True
    savedlist.store()
    request.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/hide/<int:id>')
@check_admin
def savedlist_hide(id):
    savedlist = SavedList(request.conn, id=id)
    savedlist['public'] = False
    savedlist.store()
    request.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/<int:id>/frontpage/<int:state>')
@check_admin
def savedlist_frontpage(id, state):
    savedlist = SavedList(request.conn, id=id)
    savedlist['frontpage'] = bool(state)
    savedlist.store()
    request.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/merge', methods=['POST'])
@check_admin
def savedlist_merge():
    ids = request.form.getlist('merge')
    logging.info("Merge: %s", ids)
    if not isinstance(ids, list):
        abort(500)
    ids.sort()
    first = SavedList(request.conn, id=ids[0])
    c = request.conn.cursor()
    for id in ids[1:]:
        # try to update in bulk
        c.execute("savepoint point1")
        try:
            c.execute("update items set list_id = %s where list_id = %s",
                [first['id'], id])
        except psycopg2.IntegrityError:
            c.execute("rollback to point1")
        else:
            # bulk move succeeded, onto the next list
            SavedList(request.conn, id=id).delete()
            continue

        # otherwise, move one-by-one and delete on duplicate
        for item in Item.select(request.conn, list_id = id):
            try:
                c.execute("savepoint point1")
                item['list_id'] = first['id']
                item.store()
            except ObjectExists:
                c.execute("rollback to point1")
                item.delete()
        SavedList(request.conn, id=id).delete()
    request.conn.commit()
    flash("Selected lists have been merged into '{}'".format(first['name']))
    return redirect(url_for('.savedlists'))
                
@admin_pages.route('/control/blacklist', methods=['GET'])
@check_admin
def blacklist_select():
    entries = request.api.blacklist_select()

    return render_template('blacklist.html',
        entries = entries
        )


@admin_pages.route('/control/blacklist', methods=['POST'])
@check_admin
def blacklist_post():
    request.api.blacklist_insert(request.form['domain'])
    return redirect(url_for('.blacklist_select'))


@admin_pages.route('/control/blacklist/delete', methods=['GET'])
@check_admin
def blacklist_delete():
    request.api.blacklist_delete(request.args['domain'])
    return redirect(url_for('.blacklist_select'))

@admin_pages.route('/control/user')
@check_admin
def users():
    users = request.api.list_users()
    return render_template('users.html', users=users)

#
# ISP Report admin
# ------------------
#


@admin_pages.route('/control/ispreports')
@check_admin
def ispreports():
    page = int(request.args.get('page',1))
    reports = request.api.reports(page-1, admin=True)
    return render_template('ispreports.html', reports=reports,
                           page=page,
                           pagecount = get_pagecount(reports['count'], 25))

@admin_pages.route('/control/ispreports/flag/<path:url>')
@check_admin
def ispreports_flag(url):
    url = fix_path(url)
    req = request.api.reports_flag(url, request.args.get('status','abuse'))
    if req['success'] != True:
        flash("An error occurred flagging \"{0}\": \"{1}\"".format(url, req['error']))
    return redirect(url_for('.ispreports',page=request.args.get('page',1)))

@admin_pages.route('/control/ispreports/unflag/<path:url>')
@check_admin
def ispreports_unflag(url):
    url = fix_path(url)
    req = request.api.reports_unflag(url)
    if req['success'] != True:
        flash("An error occurred unflagging \"{0}\": \"{1}\"".format(url, req['error']))
    return redirect(url_for('.ispreports',page=request.args.get('page',1)))


#
# Court Order admin
# ------------------
#


@admin_pages.route('/control/courtorders')
@check_admin
def courtorders():
    reports = CourtJudgment.select(request.conn, _orderby='name')
    return render_template('courtorders.html', judgments=reports)

@admin_pages.route('/control/courtorders/<int:id>')
@check_admin
def courtorders_view(id):
    obj = CourtJudgment(request.conn, id)
    return render_template('courtorders_view.html',
                           judgment=obj,
                           orders=obj.get_court_orders(),
                           sites=obj.get_urls()
                           )

@admin_pages.route('/control/courtorders/edit/<int:id>')
@admin_pages.route('/control/courtorders/add')
@check_admin
def courtorders_edit(id=None):
    obj = CourtJudgment(request.conn, id)
    return render_template('courtorders_edit.html',
                           obj=obj,
                           powers=[ (x['id'], x['name'])
                                    for x in
                                    CourtPowers.select(request.conn, _orderby='name')
                                    ],
                           orders = obj.get_court_orders(),
                           order_networks = obj.get_court_order_networks()
                           )


@admin_pages.route('/control/courtorders/update/<int:id>', methods=['POST'])
@admin_pages.route('/control/courtorders/insert', methods=['POST'])
@check_admin
def courtorders_update(id=None):
    try:
        f = request.form
        obj = CourtJudgment(request.conn, id)
        obj.update({x: None if f[x] == '' else f[x] for x in CourtJudgment.FIELDS})
        obj.store()

        applies = f.getlist('applies')
        for order_id, network_name, url in zip(f.getlist('order_id'), f.getlist('network_name'), f.getlist('applies_url')):
            order = CourtOrder(request.conn, order_id or None)
            if network_name in applies:
                order.update({'url': url, 'judgment_id': obj['id']})
            else:
                if order_id:
                    order.delete()
                continue
            order.update({'network_name': network_name, 'url': url, 'judgment_id': obj['id']})
            order.store()
        request.conn.commit()
        return redirect(url_for('.courtorders'))
    except KeyError as exc:
        logging.warn("Key error: %s", exc.args)
        raise

@admin_pages.route('/control/courtorders/delete/<int:id>')
@check_admin
def courtorders_delete(id):
    obj = CourtJudgment(request.conn, id)
    obj.delete()
    request.conn.commit()
    return redirect(url_for('.courtorders'))

@admin_pages.route('/control/courtorders/site/add', methods=['POST'])
@check_admin
def courtorders_site_add():
    f = request.form
    obj = CourtJudgmentURL(request.conn)
    obj.update({'url':f['url'],'judgment_id':f['judgment_id']})
    obj.store()
    request.conn.commit()
    return redirect(url_for('.courtorders_view', id=f['judgment_id']))