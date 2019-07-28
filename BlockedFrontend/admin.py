
import os
import re
import psycopg2
import logging
import datetime
import itertools

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from models import *
from auth import *
from utils import *
from resources import *
from db import *

from NORM.exceptions import ObjectNotFound,ObjectExists

admin_pages = Blueprint('admin', __name__, template_folder='templates/admin')

def convertnull(value):
    if not isinstance(value,(unicode,str)):
        return value
    return None if value == '' else value


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
    try:
        user = User.authenticate(g.conn, request.form['username'], request.form['password'])
        if user is None:
            raise ValueError
    except (ObjectNotFound,ValueError) as exc:
        current_app.logger.warn("Exception: %s", repr(exc))
        return render_template('login.html', message='Incorrect username or password')

    session['admin'] = True
    session['userid'] = user['id']
    session['username'] = user['username']
    session['admin_level'] = user['user_type']
    flash("Admin login successful")
    if session['admin_level'] != 'admin':
        return redirect(url_for('cms.index'))
    return redirect(url_for('.admin'))


@admin_pages.route('/control/logout')
def logout():
    del session['admin']
    return redirect(url_for('cms.index'))

@admin_pages.route('/control/url/submit', methods=['POST'])
@check_admin
def forcecheck():
    data = g.api.submit_url(request.form['url'], force=1)
    if data['success']:
        flash("URL submitted successfully")
    else:
        flash("Error submitting result")
    return redirect(url_for('.admin'))

@admin_pages.route('/control/savedlists')
@check_admin
def savedlists():
    return render_template('listindex.html',
        lists=SavedList.select(g.conn, _orderby='name')
        )

@admin_pages.route('/control/savedlists/add')
@check_admin
def savedlist_add():
    return render_template('list_add.html')

@admin_pages.route('/control/savedlists/create', methods=['POST'])
@check_admin
def savedlist_create():
    f = request.form

    savedlist = SavedList(g.conn)
    savedlist.update({
        'username': session.get('username','admin'),
        'name': f['name'],
        'public': False,
        'frontpage': False
    })
    savedlist.store()

    if 'upload' in request.files and request.files['upload'].filename:
        for line in request.files['upload'].stream:
            if not line.strip():
                continue

            url = normalize_url(line.strip())
            
            try:
                urlobj = Url.select_one(g.conn, url=url)
            except ObjectNotFound:
                urlobj = {}


            item = Item(g.conn)
            item.update({
                'list_id': savedlist.id,
                'url': url,
                'title': urlobj.get('title')
            })
            item.store()

    flash("List {0} created".format(f['name']))
    g.conn.commit()
    return redirect(url_for('.savedlists'))


@admin_pages.route('/control/savedlists/delete/<int:id>')
@check_admin
def savedlist_delete(id):
    savedlist = SavedList(g.conn, id=id)
    savedlist.delete()
    g.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/show/<int:id>')
@check_admin
def savedlist_show(id):
    savedlist = SavedList(g.conn, id=id)
    savedlist['public'] = True
    savedlist.store()
    g.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/hide/<int:id>')
@check_admin
def savedlist_hide(id):
    savedlist = SavedList(g.conn, id=id)
    savedlist['public'] = False
    savedlist.store()
    g.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/<int:id>/frontpage/<int:state>')
@check_admin
def savedlist_frontpage(id, state):
    savedlist = SavedList(g.conn, id=id)
    savedlist['frontpage'] = bool(state)
    savedlist.store()
    g.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/merge', methods=['POST'])
@check_admin
def savedlist_merge():
    ids = request.form.getlist('merge')
    logging.info("Merge: %s", ids)
    if not isinstance(ids, list):
        abort(500)
    ids.sort()
    first = SavedList(g.conn, id=ids[0])
    c = g.conn.cursor()
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
            SavedList(g.conn, id=id).delete()
            continue

        # otherwise, move one-by-one and delete on duplicate
        for item in Item.select(g.conn, list_id = id):
            try:
                c.execute("savepoint point1")
                item['list_id'] = first['id']
                item.store()
            except ObjectExists:
                c.execute("rollback to point1")
                item.delete()
        SavedList(g.conn, id=id).delete()
    g.conn.commit()
    flash("Selected lists have been merged into '{}'".format(first['name']))
    return redirect(url_for('.savedlists'))
                
@admin_pages.route('/control/blacklist', methods=['GET'])
@check_admin
def blacklist_select():
    entries = g.api.blacklist_select()

    return render_template('blacklist.html',
        entries = entries
        )


@admin_pages.route('/control/blacklist', methods=['POST'])
@check_admin
def blacklist_post():
    g.api.blacklist_insert(request.form['domain'])
    return redirect(url_for('.blacklist_select'))


@admin_pages.route('/control/blacklist/delete', methods=['GET'])
@check_admin
def blacklist_delete():
    g.api.blacklist_delete(request.args['domain'])
    return redirect(url_for('.blacklist_select'))

@admin_pages.route('/control/user')
@check_admin
def users():
    users = User.select(g.conn)
    return render_template('users.html', users=users)

@admin_pages.route('/control/user/add', methods=['POST'])
@check_admin
def user_add():
    f = request.form
    user = User(g.conn)
    user.update({
        'username': f['username'],
        'email': f['email'],
        'user_type': f['user_type'],
    })
    newpass = user.random_password()
    user.set_password(newpass)
    user.store()
    g.conn.commit()
    flash("User {0} created with password {1} ".format(f['username'], newpass))
    return redirect(url_for('.users'))

@admin_pages.route('/control/user/disable/<int:id>')
@check_admin
def user_disable(id):
    ret = user_set_enabled(id, False)
    return ret

@admin_pages.route('/control/user/enable/<int:id>')
@check_admin
def user_enable(id):
    ret = user_set_enabled(id, True)
    return ret
    
def user_set_enabled(id, value):    
    user = User(g.conn, id)
    user['enabled'] = value
    user.store()
    g.conn.commit()
    flash("User {0} {1}.".format(user['username'],
                                 'enabled' if value else 'disabled'))

    return redirect(url_for('.users'))

@admin_pages.route('/control/user/newpassword/<int:id>')
@check_admin
def user_generate_password(id):
    user = User(g.conn, id)
    newpass = user.reset_password()
    user.store()
    g.conn.commit()
    flash("User {0} password reset to: {1}".format(user['username'], newpass))
    return redirect(url_for('.users'))


#
# ISP Report admin
# ------------------
#

@admin_pages.route('/control/ispreports')
@check_admin
def ispreports():
    page = int(request.args.get('page',1))
    reports = g.api.reports(page-1, 
                            state=request.args.get('state'), 
                            isp=request.args.get('network', None), 
                            category=request.args.get('category'), 
                            reportercategory=request.args.get('reportercategory'), 
                            order=request.args.get('order','desc'), 
                            admin=True)

    all_categories = ( cat['name'] for cat in Category.select_active(g.conn) )
    reporter_categories = UrlReportCategory.select(g.conn, category_type='reporter', _orderby='name')
    damage_categories = UrlReportCategory.select(g.conn, category_type='damage', _orderby='name')

    return render_template('ispreports.html',
                           args=get_args_helper(['state','category','reportercategory','network','page','order']),
                           reports=reports,
                           page=page,
                           all_categories=all_categories,
                           reporter_categories=reporter_categories,
                           damage_categories=damage_categories,
                           pagecount = get_pagecount(reports['count'], 25))


@admin_pages.route('/control/ispreports/flag/<path:url>')
@check_admin
def ispreports_flag(url):
    url = fix_path(url)
    req = g.api.reports_flag(url, request.args.get('status','abuse'))
    if req['success'] != True:
        flash("An error occurred flagging \"{0}\": \"{1}\"".format(url, req['error']))
    return redirect(url_for('.ispreports',page=request.args.get('page',1)))

@admin_pages.route('/control/ispreports/unflag/<path:url>')
@check_admin
def ispreports_unflag(url):
    url = fix_path(url)
    req = g.api.reports_unflag(url)
    if req['success'] != True:
        flash("An error occurred unflagging \"{0}\": \"{1}\"".format(url, req['error']))
    return redirect(url_for('.ispreports',page=request.args.get('page',1)))

@admin_pages.route('/control/ispreports/resend/<path:url>')
@check_admin
def ispreports_resend(url):
    url = fix_path(url)
    req = g.api.reports_flag(url, 'cancelled')
    urlobj = Url.select_one(g.conn, url=url)
    report = ISPReport.select_one(g.conn, urlid=urlobj['urlid'])
    session['resend'] = (url, report.data)
    if 'name' in session and 'email' in session:
        return redirect(url_for('unblock.unblock2', url=url))
    else:
        return redirect(url_for('unblock.unblock', url=url))


@admin_pages.route('/control/ispreports/unblocked/<int:id>')
@check_admin
def ispreports_status_unblocked(id):
    email = ISPReportEmail.select_one(g.conn, id)
    report = email.get_report()
    url = report.get_url()
    
    report.set_status('unblocked', email)
    g.conn.commit()
    
    return redirect(url_for('.ispreports_view', url=url['url'], network_name=report['network_name']))

@admin_pages.route('/control/ispreports/rejected/<int:id>')
@check_admin
def ispreports_status_rejected(id):
    email = ISPReportEmail.select_one(g.conn, id)
    report = email.get_report()
    url = report.get_url()
    
    report.set_status('rejected', email)
    g.conn.commit()
    
    return redirect(url_for('.ispreports_view', url=url['url'], network_name=report['network_name']))

@admin_pages.route('/control/ispreports/<network_name>/<path:url>')
@admin_pages.route('/control/ispreports/<network_name>/<int:msgid>/<path:url>')
@check_admin
def ispreports_view(url, network_name, msgid=None):
    url = fix_path(url)
    urlobj = Url.select_one(g.conn, url=url)
    ispreport = ISPReport.get_by_url_network(g.conn, url, network_name)
    isp = ispreport.get_isp()
    contact = ispreport.get_contact()
    emails = list(ispreport.get_emails_parsed())
    if msgid:
        email = ISPReportEmail.select_one(g.conn, id=msgid)
        msg = email.decode()
    else:
        if len(emails):
            email, msg = emails[0]
        else:
            email, msg = None, None
        
    all_categories = ( (cat['id'], cat['namespace'], cat['name'])
                       for cat in Category.select_active(g.conn) )
    
    reporter_categories =  ( (cat['id'], cat['name']) for cat in
                           UrlReportCategory.select(g.conn, category_type = 'reporter', _orderby='name'))
                           
    damage_categories =  ( (cat['id'], cat['name']) for cat in
                           UrlReportCategory.select(g.conn, category_type = 'damage', _orderby='name'))                           
    
    return render_template('ispreports_email.html',
                           network_name=network_name, 
                           report=ispreport,
                           url=url,
                           urlobj = urlobj,
                           isp=isp,
                           comments = urlobj.get_category_comments(),
                           review_comments = ispreport.get_comments(),
                           report_comments = urlobj.get_report_comments(),
                           latest_status = urlobj.get_latest_status(),
                           categories = urlobj.get_categories(),
                           all_categories=all_categories,
                           emails=emails,
                           selected_msg=msg,
                           selected_email=email,
                           report_next=ispreport.get_next(),
                           report_prev=ispreport.get_prev(),
                           reporter_categories=reporter_categories,
                           damage_categories=damage_categories,
                           report_damage_categories=urlobj.get_report_categories('damage'),
                           reporter_category=urlobj.get_reporter_category(),
                           verified= contact and contact['verified']
                           ) 


@admin_pages.route('/control/ispreports/category/update', methods=['POST'])
@check_admin
def ispreports_update_category():
    f = request.form
    
    # helper functions
    
    def add_notes(urlid):
        comment = UrlCategoryComment(g.conn, data={
            'urlid': urlid,
            'description': f['category_notes'],
            'userid': session['userid']
            })
        comment.store()   
    
    def add_association(catid, urlid, primary):
        if primary:
            # clear primary for all other ORG categories
            q = Query(g.conn, 
                      """update public.url_categories set primary_category = False
                         where urlid = %s and category_id in (select id from public.categories where namespace = 'ORG')""",
                      [urlid])
        urlcat = UrlCategory.find_or_create(g.conn, 
                                            ['category_id', 'urlid'], # key fields
                                            {
                                                'category_id': catid,
                                                'urlid': urlid,
                                                'enabled': True,
                                                'primary_category': primary,
                                                'userid': session['userid']
                                            })
        if urlcat['enabled'] == False:
            urlcat.update({
                'enabled': True,
                'userid': session['userid']
            })
            urlcat.store()
        if primary:
            urlcat.update({
                'primary_category': primary,
                'userid': session['userid']
            })
            urlcat.store()
        return urlcat
    
    # main controller
    
    report = ISPReport(g.conn, f['report_id'])

    if 'url_category_id' in f:
        for urlcatid in make_list(f['url_category_id']):
            urlcat = UrlCategory(g.conn, int(urlcatid))
            urlcat['enabled'] = not urlcat['enabled']
            if not urlcat['enabled'] and urlcat['primary_category']:
                urlcat['primary_category'] = False
            urlcat['userid'] = session['userid']
            urlcat.store()
            
    if f['add_category_name']:
        cat = Category.find_or_create(g.conn, 
                                      ['name','namespace'],
                                      {
                                          'namespace':'ORG', 
                                          'name': f['add_category_name'].strip(),
                                          'display_name': f['add_category_name'].strip()
                                      })
            
        urlcat = add_association(cat['id'], report['urlid'], ('primary_category' in f))

        flash("Added to category: {0} ({1})".format(cat['display_name'], cat['namespace']))
                
    
    if f['add_category_id']:
        
        cat = Category(g.conn, f['add_category_id'])
        
        urlcat = add_association(cat['id'], report['urlid'], ('primary_category' in f))
        
        flash("Added to category: {0} ({1})".format(cat['display_name'], cat['namespace']))
        
    if f['category_notes'].strip():
        add_notes(report['urlid'])
        
    g.conn.commit()
    
    url = report.get_url()
    return redirect(url_for('.ispreports_view', url=url['url'], network_name=report['network_name'], tab='categories'))
    
@admin_pages.route('/control/ispreports/reportcategory/update', methods=['POST'])
@check_admin
def ispreports_update_report_category():
    f = request.form
    report = ISPReport(g.conn, f['report_id'])
    url = report.get_url()
    
    def find_reporter_category():
        q = Query(g.conn,
                  """select url_report_category_asgt.* from public.url_report_category_asgt
                     inner join public.url_report_categories on category_id = url_report_categories.id
                     where urlid = %s and category_type = 'reporter'""",
                  [ url['urlid'] ])
        row = q.fetchone()
        q.close()
        if row:
            print "Found reporter category"
            return UrlReportCategoryAsgt(g.conn, data=row)
        return None
    
    
    if f['new_reporter_category']:
        reportercat = UrlReportCategory(g.conn)
        reportercat.update({
            'name': f['new_reporter_category'],
            'category_type': 'reporter'
        })
        reportercat.store()
        asgt = find_reporter_category()
        if not asgt:
            asgt = UrlReportCategoryAsgt(g.conn)
            asgt['urlid'] = url['urlid']
        asgt['category_id'] = reportercat['id']
        asgt.store()
        flash("Added reporter category: {0}".format(f['new_reporter_category']))
    elif f['reporter_category_id']:
        reportercat = UrlReportCategory(g.conn, f['reporter_category_id'])
        asgt = find_reporter_category()
        if not asgt:
            asgt = UrlReportCategoryAsgt(g.conn)
            asgt['urlid'] = url['urlid']
        asgt['category_id'] = reportercat['id']
        asgt.store()
        
    damagecat = None
    if f['add_category_name'].strip():
        damagecat = UrlReportCategory(g.conn)
        damagecat.update({
            'name': f['add_category_name'],
            'category_type': 'damage'
        })
        damagecat.store()
        
        report_cat_asgt = UrlReportCategoryAsgt(g.conn)
        report_cat_asgt.update({
            'category_id': damagecat['id'],
            'urlid': url['urlid'],
        })
        report_cat_asgt.store()
        
        flash("Added damage category: {0}".format(f['add_category_name']))
    if f.get('damage_category_id'):
        damagecat = UrlReportCategory(g.conn, f['damage_category_id'])
        
        report_cat_asgt = UrlReportCategoryAsgt(g.conn)
        report_cat_asgt.update({
            'category_id': damagecat['id'],
            'urlid': url['urlid'],
        })
        report_cat_asgt.store()
        
        flash("Added damage category: {0}".format(damagecat['name']))
        
    comment = UrlReportCategoryComment(g.conn)
    comment.update({
        'urlid': url['urlid'],
        'userid': session['userid'],
        'damage_category_id': damagecat['id'] if damagecat else None,
        'reporter_category_id': reportercat['id'] if reportercat else None,
        'review_notes': f['review_notes']
    })
    comment.store()
        
    g.conn.commit()
    return redirect(url_for('.ispreports_view', url=url['url'], network_name=report['network_name'], tab='rptcategories'))    
    
@admin_pages.route('/control/ispreports/review/update', methods=['POST'])
@check_admin
def ispreports_review_update():
    f = request.form
    report = ISPReport(g.conn, f['report_id'])
    url = report.get_url()

    if 'matches_policy' in f:
        report.update_flag('matches_policy', (True if f['matches_policy'] == 'true' else False))

    report.update_flag('egregious_block', 'egregious_block' in f)
    report.update_flag('featured_block', 'featured_block' in f)
    report.update_flag('maybe_harmless', 'maybe_harmless' in f)

    comment = ISPReportComment(g.conn)
    comment.update({
        'userid': session['userid'],
        'report_id': report['id'],
        'review_notes': f['review_notes'],
        'matches_policy': f.get('matches_policy', None),
        'egregious_block': 'egregious_block' in f,
        'featured_block': 'featured_block' in f,
        'maybe_harmless': 'maybe_harmless' in f,
    })
    comment.store()
    g.conn.commit()
    flash("Review notes updated")
    return redirect(url_for('.ispreports_view', url=url['url'], network_name=report['network_name'], tab='block'))


def group_by_year(q):
    # reshape into list of (reporter,damage,network),dict(year: count)             
    return ( (grp, {int(row['yr']): row['ct'] for row in ls})
            for (grp, ls) in 
            itertools.groupby(q, lambda row: (row.get('reporter'), row.get('damage'), row.get('network_name'), row.get('isp_type') ))
            )

def get_isp_report_stats_data():
    q = Query(g.conn,
              """select cat1.name reporter, cat2.name damage, network_name, extract('year' from isp_reports.created) yr, count(*) ct
                 from public.isp_reports_sent isp_reports
                 inner join public.urls using (urlid)
                 inner join public.url_report_category_asgt asgt1 using (urlid)
                 inner join public.url_report_categories cat1 on asgt1.category_id = cat1.id and cat1.category_type = 'reporter'
                 inner join public.url_report_category_asgt asgt2 using (urlid)
                 inner join public.url_report_categories cat2 on asgt2.category_id = cat2.id and cat2.category_type = 'damage'
                 where network_name <> 'ORG'
                 group by cat1.name, cat2.name, network_name, extract('year' from isp_reports.created)
                 order by network_name, cat1.name, cat2.name, extract('year' from isp_reports.created)""", [])
    return q

@admin_pages.route('/control/ispreport/stats')
@check_admin
def ispreport_stats():
    q1 = Query(g.conn,
              """select cat1.name reporter,  extract('year' from urls.last_reported) yr, count(*) ct
                 from public.urls
                 inner join public.url_report_category_asgt asgt1 using (urlid)
                 inner join public.url_report_categories cat1 on asgt1.category_id = cat1.id and cat1.category_type = 'reporter'
                 group by cat1.name, extract('year' from urls.last_reported)
                 order by cat1.name, extract('year' from urls.last_reported)"""
                 , [])
                 
    q1_1, q1_2, q1_3 = itertools.tee(q1, 3)
    q1_totals = {}
    for row in q1_1:
        q1_totals.setdefault(row['yr'], 0)
        q1_totals[row['yr']] += row['ct']
                            
    site_owner_totals = {}
    for grp, yeardata in group_by_year(q1_3):
        if grp[0].startswith('Site Owner '):
            for k,v in yeardata.iteritems():
                site_owner_totals.setdefault(k, 0)
                site_owner_totals[k] += v

    q2 = Query(g.conn,
              """select cat2.name damage, extract('year' from urls.last_reported) yr, count(*) ct
                 from public.urls 
                 inner join public.url_report_category_asgt asgt2 using (urlid)
                 inner join public.url_report_categories cat2 on asgt2.category_id = cat2.id and cat2.category_type = 'damage'
                 group by cat2.name, extract('year' from urls.last_reported)
                 order by cat2.name, extract('year' from urls.last_reported)"""
                 , [])            

    q_reporter = Query(g.conn,
              """select cat1.name reporter, network_name, extract('year' from isp_reports.created) yr, count(*) ct
                 from public.isp_reports_sent isp_reports
                 inner join public.urls using (urlid)
                 inner join public.url_report_category_asgt asgt1 using (urlid)
                 inner join public.url_report_categories cat1 on asgt1.category_id = cat1.id and cat1.category_type = 'reporter'
                 where network_name <> 'ORG'
                 group by cat1.name,  network_name, extract('year' from isp_reports.created)
                 order by network_name, cat1.name, extract('year' from isp_reports.created)""", [])



                 
    q_damage = Query(g.conn,
              """select cat2.name damage, network_name, extract('year' from isp_reports.created) yr, count(*) ct
                 from public.isp_reports_sent isp_reports
                 inner join public.urls using (urlid)
                 inner join public.url_report_category_asgt asgt2 using (urlid)
                 inner join public.url_report_categories cat2 on asgt2.category_id = cat2.id and cat2.category_type = 'damage'
                 where network_name <> 'ORG'
                 group by cat2.name, network_name, extract('year' from isp_reports.created)
                 order by network_name, cat2.name, extract('year' from isp_reports.created)""", [])                 

    q_isps = Query(g.conn,
              """select network_name, isp_type, extract('year' from isp_reports.created) yr, count(*) ct
                 from public.isp_reports_sent isp_reports
                 inner join public.isps on network_name = isps.name
                 where network_name <> 'ORG'
                 group by network_name, isp_type, extract('year' from isp_reports.created)
                 order by isp_type, network_name, extract('year' from isp_reports.created)""", [])                 

    q_isps1, q_isps2 = itertools.tee(q_isps, 2)
    
    totalrows = {'_all':{} }
    for hdr, iter in itertools.groupby(q_isps1, lambda row: row['isp_type']):
        for row in iter:
            if row['isp_type'] not in totalrows:
                totalrows[ row['isp_type'] ] = {}
            if row['yr'] not in totalrows[ row['isp_type'] ]:
                totalrows[ row['isp_type'] ][ row['yr'] ] = row['ct']
            else:
                totalrows[ row['isp_type'] ][ row['yr'] ] += row['ct']
            if row['yr'] not in totalrows['_all']:
                totalrows[ '_all' ][ row['yr'] ] = row['ct']
            else:
                totalrows[ '_all' ][ row['yr'] ] += row['ct']

    return render_template('ispreport_stats.html',
                           currentyear = datetime.date.today().year, 
                           reporter_stats=group_by_year(q1_2),
                           q1_totals=q1_totals,
                           damage_stats=group_by_year(q2),
                           reporter_full=group_by_year(q_reporter),
                           damage_full=group_by_year(q_damage),
                           isp_stats=group_by_year(q_isps2),
                           totalrows=totalrows,
                           site_owner_totals=site_owner_totals
                           )

@admin_pages.route('/control/ispreport/csv-stats')
@check_admin
def ispreport_stats_csv():
    import csv
    import tempfile
    
    tmpfile = tempfile.SpooledTemporaryFile(mode='w+t')
    writer = csv.writer(tmpfile)
    writer.writerow(['# ISP Reports stats from blocked.org.uk',str(datetime.datetime.now()) ])
    writer.writerow([''])
    writer.writerow(['Reporter','Damage','Network'] + [str(x) for x in range(2016, datetime.date.today().year+1)] + ['Total'])
    
    for (grp, data) in group_by_year(get_isp_report_stats_data()):
        row = [ grp[0], grp[1], grp[2] ]
        for yr in range(2016, datetime.date.today().year+1):
            row.append(data.get(yr,''))
        row.append(sum(data.values()))
        writer.writerow(row)
        
    
    tmpfile.flush()
    length = tmpfile.tell()
    tmpfile.seek(0)

    def returnvalue(*args):
        for line in tmpfile:
            yield line

    return Response(returnvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=isp_report_stats.csv',
        'Content-length': str(length)
        })
            
@admin_pages.route('/control/ispreport/reply-stats')
@check_admin
def ispreport_reply_stats():

    q = Query(g.conn,
              """
              select extract('year' from isp_reports.created)::int as year, 
                count(*) count_reported, count(distinct urlid) count_sites,
                sum(case when status >= 'sent' then 1 else 0 end) count_sent,
                sum(case when status >= 'unblocked' or status = 'rejected' or exists(select 1 from public.isp_report_emails where report_id = isp_reports.id) then 1 else 0 end) count_responded,
                sum(case when status = 'unblocked' or unblocked =1 then 1 else 0 end) count_unblocked,
                sum(case when status = 'rejected' then 1 else 0 end) count_rejected,
                sum(case when unblocked=0 and not exists(select 1 from public.isp_report_emails where report_id = isp_reports.id) then 1 else 0 end) count_unresolved,
                sum(case when unblocked=0 and not exists(select 1 from public.isp_report_emails where report_id = isp_reports.id) and matches_policy is false then 1 else 0 end) count_unresolved_badblock
                from public.isp_reports_sent isp_reports
                where network_name <> 'ORG' and network_name <> 'BT-Strict'
                group by extract('year' from isp_reports.created)::int 
                """, [])
    totals = {}
    sent_stats = {}
    for row in q:
        sent_stats[row['year']] = row
        for col in row.keys():
            if col == 'year': continue
            totals.setdefault(col, 0)
            totals[col] += row[col]
    sent_stats['_total'] = totals

    q5 = Query(g.conn,
               """select
                       avg(case when (status='unblocked' or status='rejected' or unblocked=1) and isp_report_emails.id = isp_reports.resolved_email_id then isp_reports.last_updated - isp_reports.submitted else null end) avg_response_time,
                       array_agg(distinct network_name) isps
                  from public.isp_reports_sent isp_reports
                  left join public.isp_report_emails on report_id = isp_reports.id
                  where network_name not in ('ORG','TalkTalk','Plusnet','O2')
                      and extract('year' from isp_reports.created) = 2018""", [])
    all_isp_response = q5.fetchone()


    reply_stats = ISPReport.get_reply_stats(g.conn)


    return render_template('ispreport_reply_stats.html',
                           sent_stats=sent_stats,
                           all_isp_response=all_isp_response,
                           reply_stats=reply_stats)


@admin_pages.route('/control/ispreport/consistency')
@check_admin
def ispreport_consistency():
    q = Query(g.conn,
              """select savedlists.id, savedlists.name, count(*) ct, sum(case when reported is true then 1 else 0 end) reported
                 from savedlists
                 inner join items on list_id = savedlists.id
                 where name like 'Mobile Inconsistency%%'
                 group by savedlists.id, savedlists.name
                 order by savedlists.name""",[])

    list_summary, counter = itertools.tee(q)

    counts = {}
    for row in counter:
        if 'only on' in row['name']:
            counts.setdefault(1, 0)
            counts[1] += row['ct']
        else:
            num = int(row['name'].rsplit(' ', 2)[1])
            counts[num] = row['ct']
    counts = [ {'network_count': k, 'urls': v} for (k,v) in sorted(counts.iteritems()) ]

    networks = list(Query(g.conn,
                     """select * from stats.mobile_blocks order by network_name""", []))

    return render_template("ispreport_consistency.html",
                           list_summary=list_summary,
                           counts=counts,
                           networks=networks
                           )

@admin_pages.route('/control/ispreports/category-status')
@check_admin
def ispreport_category_stats():

    reporter_categories = UrlReportCategory.select(g.conn, category_type='reporter', _orderby='name')

    if request.args.get('reporter'):
        cat = UrlReportCategory(g.conn, id=request.args['reporter'])
        q = Query(g.conn,
                  """select name, count(distinct case when primary_category = true then url_categories.id else null end ) primary_ct, count(*) ct
                     from public.categories
                     inner join public.url_categories on url_categories.category_id = categories.id
                     inner join public.url_report_category_asgt asgt on asgt.urlid = url_categories.urlid
                     where categories.namespace = 'ORG' and url_categories.enabled = true and asgt.category_id = %s
                     group by name
                     order by name""",
                  [request.args['reporter']])
    else:
        cat = None
        q = ISPReport.get_category_stats(g.conn)

    return render_template('ispreport_category_stats.html',
                           categories=q,
                           cat=cat,
                           reporter_categories=reporter_categories) 


#
#  Search filter admin
#  -------------------
#

@admin_pages.route('/control/search-filter')
@check_admin
def search_filter():
    terms = SearchIgnoreTerm.select(g.conn, _orderby=['-enabled','term'])

    return render_template('search_filter.html',
                           terms=terms)


@admin_pages.route('/control/search-filter/add', methods=['POST'])
@check_admin
def search_filter_add():
    f = request.form
    term = SearchIgnoreTerm(g.conn)
    term.update({
        'term': f['term'],
        'enabled': True
    })
    term.store()
    g.conn.commit()

    return redirect(url_for('.search_filter'))

@admin_pages.route('/control/search-filter/update', methods=['POST'])
@check_admin
def search_filter_update():
    f = request.form
    enabled = set(make_list(f.getlist('enabled')))
    terms = set(make_list(f.getlist('term')))

    remove = terms - enabled
    add = enabled - terms

    current_app.logger.info("Terms: %s, Enabled: %s", terms, enabled)
    current_app.logger.info("Add: %s, Remove: %s", add, remove)

    for termid in remove:
        term = SearchIgnoreTerm(g.conn, id=int(termid))
        term['enabled'] = False
        term.store()

    for termid in add:
        term = SearchIgnoreTerm(g.conn, id=int(termid))
        term['enabled'] = True
        term.store()

    g.conn.commit()
    return redirect(url_for('.search_filter'))


#
# Court Order admin
# ------------------
#


@admin_pages.route('/control/courtorders')
@check_admin
def courtorders():
    reports = CourtJudgment.select(g.conn, _orderby='-date')
    return render_template('courtorders.html', judgments=reports)

@admin_pages.route('/control/courtorders/<int:id>')
@check_admin
def courtorders_view(id):
    obj = CourtJudgment(g.conn, id)
    return render_template('courtorders_view.html',
                           judgment=obj,
                           orders=obj.get_court_orders(),
                           sites=obj.get_grouped_urls_with_expiry(),
                           groups=[(grp['id'],grp['name']) for grp in obj.get_url_groups()]
                           )

@admin_pages.route('/control/courtorders/review')
@admin_pages.route('/control/courtorders/review/<int:page>')
@check_admin
def courtorders_review(page=1):
    offset = (page-1)*25
    q = Query(g.conn, 
              """
              select count(distinct urls.urlid) ct from urls
              inner join url_latest_status uls on uls.urlid = urls.urlid
              inner join isps on isps.name = uls.network_name and regions && %s::varchar[]
                and (isps.filter_level = 'No Adult' or isps.isp_type = 'mobile')
              left join court_judgment_urls cu on urls.url = cu.url
              where urls.status = 'ok' and uls.status = 'blocked' 
                and urls.url ~* '^https?://[^/]+$'
                and uls.blocktype = 'COPYRIGHT' and (cu.url is null or cu.judgment_id is null)
              """,
              [[current_app.config['DEFAULT_REGION']]]

             )
    count = q.fetchone()['ct']
    q.close()
    
    q = Query(g.conn, 
              """
              select urls.url, array_agg(network_name) networks, 
                min(uls.created) created, min(uls.first_blocked) first_blocked, whois_expiry ,
                  case when exists(select id from court_judgment_url_flags cjuf 
                                    where cjuf.urlid = urls.urlid and cjuf.judgment_url_id is null) then true else false end as flagged 
              from urls
              inner join url_latest_status uls on uls.urlid = urls.urlid
              inner join isps on isps.name = uls.network_name and regions && %s::varchar[]
                and (isps.filter_level = 'No Adult' or isps.isp_type = 'mobile')
              left join court_judgment_urls cu on urls.url = cu.url
              where urls.status = 'ok' and uls.status = 'blocked' 
                and urls.url ~* '^https?://[^/]+$'
                and uls.blocktype = 'COPYRIGHT' and cu.url is null
              group by urls.url, whois_expiry, urls.urlid
              order by min(uls.first_blocked) limit 25 offset {0}""".format(offset),
              [[current_app.config['DEFAULT_REGION']]]
             )
    return render_template('courtorders_review.html',
                           results=q,
                           page=page,
                           pagesize=25, 
                           pagecount=get_pagecount(count, 25)
                          )
    
@admin_pages.route('/control/courtorders/edit/<int:id>')
@admin_pages.route('/control/courtorders/add')
@check_admin
def courtorders_edit(id=None):
    obj = CourtJudgment(g.conn, id)
    return render_template('courtorders_edit.html',
                           obj=obj,
                           powers=[ (x['id'], x['name'])
                                    for x in
                                    CourtPowers.select(g.conn, _orderby='name')
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
        print f
        obj = CourtJudgment(g.conn, id)
        obj.update({x: convertnull(f[x]) for x in CourtJudgment.FIELDS})
        obj.store()

        to_delete = [ int(x) for x in f.getlist('delete') if x ]

        for order_id, network_name, url, date, expiry_date in zip(
                f.getlist('order_id'),
                f.getlist('network_name'),
                f.getlist('applies_url'),
                f.getlist('order_date'),
                f.getlist('expiry_date'),
            ):
            print order_id, network_name
            order = CourtOrder(g.conn, order_id or None)
            if order['id'] in to_delete:
                order.delete()
                continue
            order.update({
                'network_name': network_name,
                'url': url,
                'judgment_id': obj['id'],
                'date':convertnull(date),
                'expiry_date':convertnull(expiry_date)
            })
            order.store()
        g.conn.commit()
        return redirect(url_for('.courtorders'))
    except KeyError as exc:
        logging.warn("Key error: %s", exc.args)
        raise

@admin_pages.route('/control/courtorders/delete/<int:id>')
@check_admin
def courtorders_delete(id):
    obj = CourtJudgment(g.conn, id)
    obj.delete()
    g.conn.commit()
    return redirect(url_for('.courtorders'))

@admin_pages.route('/control/courtorders/site/add', methods=['POST'])
@check_admin
def courtorders_site_add():
    f = request.form
    obj = CourtJudgmentURL(g.conn)
    obj.update({'url':normalize_url(f['url']),'judgment_id':f['judgment_id']})
    try:
        obj.store()
        g.conn.commit()
    except ObjectExists:
        print obj.data
        flash("This site has already been added to this court order")
        g.conn.rollback()
    return redirect(url_for('.courtorders_view', id=f['judgment_id']))

@admin_pages.route('/control/courtorders/site/group', methods=['POST'])
@check_admin
def courtorders_site_group():
    f = request.form
    if f['group_id']:
        grp = CourtJudgmentURLGroup(g.conn, f['group_id'])
    else:
        grp = None
    for site_id in f.getlist('site_id'):
        obj = CourtJudgmentURL(g.conn, site_id)
        if f['group_id'] == '':
            obj['group_id'] = None
        else:
            obj['group_id'] = f['group_id']
        obj.store()
    g.conn.commit()
    if grp:
        flash("Added URL(s) to group: " + grp['name'])
    else:
        flash("Removed URL(s) from groups")
    return redirect(url_for('.courtorders_view', id=f['judgment_id']))

@admin_pages.route('/control/courtorders/site/group/add', methods=['POST'])
@check_admin
def courtorders_group_add():
    obj = CourtJudgmentURLGroup(g.conn)
    obj['judgment_id'] = request.form['judgment_id']
    obj['name'] = request.form['name']
    obj.store()
    g.conn.commit()
    flash("Added URL group: "+ request.form['name'])
    return redirect(url_for('.courtorders_view', id=request.form['judgment_id']))

@admin_pages.route('/control/courtorders/site/group/delete/<int:id>', methods=['GET'])
@check_admin
def courtorders_group_delete(id):
    obj = CourtJudgmentURLGroup(g.conn, id=id)
    obj.delete()
    g.conn.commit()
    flash("Deleted URL group: "+ obj['name'])
    return redirect(url_for('.courtorders_view', id=obj['judgment_id']))

@admin_pages.route('/control/courtorders/site/delete/<int:id>', methods=['GET'])
@check_admin
def courtorders_site_delete(id):
    obj = CourtJudgmentURL(g.conn, id=id)
    obj.delete()
    g.conn.commit()
    flash("Removed site: "+ obj['url'])
    return redirect(url_for('.courtorders_view', id=obj['judgment_id']))

@admin_pages.route('/control/courtorders/site/flag/<int:id>', methods=['GET'])
@check_admin
def courtorders_site_flag(id):
    url = CourtJudgmentURL(g.conn, id=id)
    judgment = url.get_court_judgment()
    
    q = Query(g.conn, """
        select isps.name, uls.status, uls.blocktype, uls.created
        from urls
        inner join url_latest_status uls on uls.urlid = urls.urlid
        inner join isps on uls.network_name = isps.name
        where urls.url = %s 
        and isps.regions && '{gb}'::varchar[] and (isps.isp_type = 'mobile' or isps.filter_level = 'No Adult')
        order by isps.name""",
        [url['url']])
    
    flags = Query(g.conn, """
        select f.*
        from court_judgment_url_flag_history f 
        where f.judgment_url_id = %s
        order by f.date_observed desc""",
        [url['id']])
    
    try:
        flag = CourtJudgmentURLFlag.select_one(g.conn, 
                                               judgment_url_id = url['id'])
    except ObjectNotFound:
        flag = {}
    
    return render_template('courtorders_flag.html', 
                           url=url, 
                           flag=flag, 
                           judgment=judgment, 
                           today=datetime.date.today(),
                           status=q,
                           flags=flags,
                           flagreasons=load_data('flagreasons')
                           )

@admin_pages.route('/control/courtorders/url/flag/<path:id>', methods=['GET'])
@check_admin
def courtorders_url_flag(id):
    id = fix_path(id)
    try:
        url = Url.select_one(g.conn, url=id)
    except ObjectNotFound:
        abort(404)

    
    q = Query(g.conn, """
        select isps.name, uls.status, uls.blocktype, uls.created
        from url_latest_status uls 
        inner join isps on uls.network_name = isps.name
        where urlid = %s 
        and isps.regions && '{gb}'::varchar[] and (isps.isp_type = 'mobile' or isps.filter_level = 'No Adult')
        order by isps.name""",
        [url['urlid']])
    
    flags = Query(g.conn, """
        select f.*
        from court_judgment_url_flag_history f 
        where f.urlid = %s
        order by f.date_observed desc""",
        [url['urlid']])
    
    try:
        flag = CourtJudgmentURLFlag.select_one(g.conn, 
                                               urlid = url['urlid'])
    except ObjectNotFound:
        flag = {}
    
    return render_template('courtorders_flag.html', 
                           url=url, 
                           flag=flag, 
                           judgment=None, 
                           today=datetime.date.today(),
                           status=q,
                           flags=flags,
                           flagreasons=load_data('flagreasons'),
                           formsubmit=url_for('.courtorders_url_flag_post')
                           )


@admin_pages.route('/control/courtorders/site/flag', methods=['POST'])
@check_admin
def courtorders_site_flag_post():
    f = request.form
    url = CourtJudgmentURL(g.conn, id=f['urlid'])
    
    if 'delete' in f:
        try:
            flag = CourtJudgmentURLFlag.select_one(g.conn, judgment_url_id = url['id'])
            flag.delete()
            judgment = url.get_court_judgment()
            g.conn.commit()
            flash("Url {0} unflagged".format(url['url']))
            return redirect(url_for('.courtorders_view', id=judgment['id']))
        except ObjectNotFound:
            g.conn.rollback()
            abort(404)
        
    
    try:
        flag = CourtJudgmentURLFlag.select_one(g.conn, judgment_url_id = url['id'])
    except ObjectNotFound:
        flag = CourtJudgmentURLFlag(g.conn)
        
    flag.update({
        'reason': f['reason'],
        'description': f['description'],
        'date_observed': f['date_observed'] or None,
        'abusetype': f['abusetype'] if f['reason'] == 'domain_may_be_abusive' else None,
        'judgment_url_id': f['urlid'],
        'urlid': url.get_urlid(),
    })
    flag.store()
    judgment = url.get_court_judgment()
    g.conn.commit()
    flash("Url {0} flagged".format(url['url']))
    return redirect(url_for('.courtorders_view', id=judgment['id']))


@admin_pages.route('/control/courtorders/url/flag', methods=['POST'])
@check_admin
def courtorders_url_flag_post():
    f = request.form
    url = Url.select_one(g.conn, urlid=f['urlid'])
    
    if 'delete' in f:
        try:
            flag = CourtJudgmentURLFlag.select_one(g.conn, urlid = url['urlid'])
            flag.delete()
            g.conn.commit()
            flash("Url {0} unflagged".format(url['url']))
            return redirect(url_for('.courtorders_url_flag', id=url['url']))
        except ObjectNotFound:
            g.conn.rollback()
            abort(404)
        
    
    try:
        flag = CourtJudgmentURLFlag.select_one(g.conn, urlid = url['urlid'])
    except ObjectNotFound:
        flag = CourtJudgmentURLFlag(g.conn)
        
    flag.update({
        'reason': f['reason'],
        'description': f['description'],
        'date_observed': f['date_observed'] or None,
        'abusetype': f['abusetype'] if f['reason'] == 'domain_may_be_abusive' else None,
        'judgment_url_id': None,
        'urlid': url['urlid'],
    })
    flag.store()
    g.conn.commit()
    flash("Url {0} flagged".format(url['url']))
    return redirect(url_for('.courtorders_url_flag', id=url['url']))

@admin_pages.route('/control/courtorders/site/flag/delete/<int:id>', methods=['GET'])
@check_admin
def courtorders_site_flag_delete(id):
    q = Query(g.conn, 
              "delete from court_judgment_url_flag_history where id = %s returning judgment_url_id, urlid ",
              [id])
    row = q.fetchone()
    
    g.conn.commit()
    flash("Historical flag removed")
    if row['judgment_url_id']:
        return redirect(url_for('.courtorders_site_flag', id=row['judgment_url_id']))
    else:
        url = Url.select_one(g.conn, urlid=row['urlid'])
        return redirect(url_for('.courtorders_url_flag', id=url['url']))
    
    

@admin_pages.route('/control/courtorders/site/group/import', methods=['GET'])
@check_admin
def courtorders_group_import():
    return render_template('courtorders_group_import.html', groups=CourtJudgmentURLGroup.select(g.conn, _orderby='name'))

@admin_pages.route('/control/courtorders/site/group/import', methods=['POST'])
@check_admin
def courtorders_group_do_import():
    if 'groupfile' not in request.files:
        flash('No input file supplied')
        return redirect(request.url)

    groupfile = request.files['groupfile']
    if groupfile.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if groupfile and groupfile.filename.endswith('.csv'):
        import_groupfile(groupfile)


    flash("Imported successfully")
    return redirect(url_for('.courtorders'))

def import_groupfile(groupfile):
    import csv
    reader = csv.reader(groupfile.stream)
    for row in reader:
        url = row[0]
        if len(row) < 2:
            continue

        group = row[1]

        if not url or not group:
            continue

        try:
            groupobj = CourtJudgmentURLGroup.select_one(g.conn, name=group)
            try:
                urlobj = CourtJudgmentURL.select_one(g.conn, url=url)
            except ObjectNotFound:
                urlobj = None
            if urlobj is None or urlobj['group_id']:
                # already assigned to a group, create a new url obj and assign that to the group & same judgment
                urlobj = CourtJudgmentURL(g.conn)
                urlobj.update({
                    'judgment_id': groupobj['judgment_id'],
                    'group_id': groupobj['id'],
                    'url': url
                })
            else:
                # assign existing url to group
                urlobj['group_id'] = groupobj['id']
            try:
                urlobj.store()
            except ObjectExists:
                current_app.logger.warn("Duplicate entry: %s", urlobj.data)
                g.conn.rollback()
            else:
                g.conn.commit()
        except ObjectNotFound:
            current_app.logger.warn("Group not found: %s", group)
            g.conn.rollback()


## URL Admin


@admin_pages.route('/control/urls', methods=['GET'])
@check_admin
def urls():
    if request.args.get('url'):
        try:
            status = g.api.status_url(request.args['url'], True)
        except Exception:
            status = None
            flash("Could not locate a URL record for {0}".format(request.args['url']))
    else:
        status = None
        
    return render_template('admin_urls.html', status=status, tags=load_data('tags'))

@admin_pages.route('/control/urls/check', methods=['GET'])
@check_admin
def admin_urls_check():
    status = g.api.status_url(request.args['url'], request.args.get('normalize', '1') == '1')
    return jsonify(**status)

@admin_pages.route('/control/urls', methods=['POST'])
@check_admin
def urls_post():
    f = request.form
    print f
    if 'update_status' in f:
        rsp = g.api.set_status_url(f['url'], f['status'],
                                         f.get('normalize', '0') == '1')
        if rsp['success'] == True:
            flash("URL Status updated")
        else:
            flash("Error updating URL status")
        return redirect(url_for('.urls'))

    if 'update_tag' in f:
        if f['newtag']:
            tag = f['newtag'].lower()
        else:
            tag = f['tag'].lower()
        
        if not is_tag_valid(tag):
            flash("Tag \"{0}\" is not valid.  Tags must contain only characters a-z, 0-9 and '-'.".format(tag))
            return redirect(url_for('.urls'))
        
            
        q = Query(g.conn, """update urls set tags = tags || %s::varchar where url = %s and not tags && %s::varchar[]""",
            [ tag, normalize_url(f['url']), [tag] ])
        q.close()
        g.conn.commit()
        flash("URL Tags updated")
        return redirect(url_for('.urls', url=normalize_url(f['url'])))

    abort(400)

@admin_pages.route('/control/urls/upload')
@check_admin
def urls_upload():
    return render_template('admin_url_upload.html',
                           tags=sorted(load_data('tags'))
                           )
@admin_pages.route('/control/urls/upload', methods=['POST'])
@check_admin
def urls_upload_post():

    bad_tags = [ # strip empty and invalid values
            x.lower() for x in request.form.getlist('tag')
            if x and not is_tag_valid(x.lower())
            ]
    if bad_tags:
        flash("Invalid tags: {0}".format(", ".join(bad_tags)))

    tags = make_list([ # strip empty and invalid values
            x.lower() for x in request.form.getlist('tag')
            if x and is_tag_valid(x.lower())
            ])

    addcount = 0

    errors = []
    for _url in request.form['urls'].splitlines():
        url = normalize_url(_url)

        try:
            result = g.api.submit_url(url, queue='none', source=request.form['source'])
            if result['success']:
                addcount += 1
            else:
                errors.append(url)
                continue

            for tag in tags:
                q = Query(g.conn, 
                          """update urls set tags = tags || %s::varchar 
                             where url = %s and not tags && %s::varchar[]""",
                          [ tag, url, [tag] ])
                q.close()
            g.conn.commit()
        except Exception as v:
            current_app.logger.warn("API exception: %s", str(v))

    if errors:
        flash("Errors submitting: {0}".format(", ".join(errors)))
    flash("{0} url{1} uploaded".format(addcount, '' if addcount == 1 else 's'))
    return redirect(url_for('.urls_upload'))

################
#
# URL category admin
#
################

@admin_pages.route('/control/url-category')
@check_admin
def url_categories():

    return render_template('url_category.html',
                           categories=Category.select_with_counts(g.conn),
                           ) 

@admin_pages.route('/control/url-category/edit/<id>')
@check_admin
def url_category_edit(id):
    cat = Category(g.conn, id)
    return render_template('url_category_edit.html', category=cat)

@admin_pages.route('/control/url-category/update', methods=['POST'])
@check_admin
def url_category_update():
    f = request.form
    cat = Category(g.conn, f['id'])
    cat.update({
        'name': f['name'],
        'display_name': f['display_name'],
    })
    cat.store()
    g.conn.commit()
    flash("Category {0} updated".format(f['name']))
    return redirect(url_for('.url_categories'))

@admin_pages.route('/control/url-category/merge', methods=['POST'])
@check_admin
def url_category_merge():
    f = request.form

    mergelist = f.getlist('merge')

    if len(mergelist) == 1:
        flash("More than 1 merge category required")
        return redirect(url_for('.url_categories'))

    cat = Category(g.conn, id=mergelist.pop(0))

    mergenames = []
    for merge in mergelist:
        mergecat = Category(g.conn, id=merge)
        q = Query(g.conn,
                  """update public.url_categories 
                     set category_id = %s 
                     where category_id = %s 
                        and not exists(select 1 from public.url_categories x where x.urlid = url_categories.urlid and x.category_id = %s)""",
                  [cat['id'], merge, cat['id']])
        q = Query(g.conn,
                  """update public.url_categories set enabled = true, last_updated=now() where category_id = %s and enabled = false""",
                  [cat['id']])
        mergenames.append(mergecat['name'])
        mergecat.delete()
    g.conn.commit()
    flash("Merged categories {0} with {1}".format(", ".join(mergenames), cat['name']))
    return redirect(url_for('.url_categories'))


@admin_pages.route('/control/url-category/delete/<id>', methods=['GET','POST']) # should be a post method
@check_admin
def url_category_delete(id):
    cat = Category(g.conn, id=id)
    if request.method == 'POST':
        if cat['namespace'] != 'ORG':
            flash("Cannot delete non-ORG category")
            return redirect(url_for('.url_categories'))

        cat.delete()
        g.conn.commit()
        flash("Category {0} deleted".format(cat['name']))
        return redirect(url_for('.url_categories'))

    if request.method == 'GET':
        return render_template('url_category_delete_confirm.html', id=id, cat=cat)


## Tests admin

@admin_pages.route('/control/tests')
@check_admin
def tests():
    tests = Test.select(g.conn, _orderby='last_run')
    queues = Query(g.conn, """select * 
        from tests.queue_status 
        where queue_name like '%%.public'
        order by message_count desc""", 
        [])
    return render_template('tests.html', tests=tests, queues=queues)

@admin_pages.route('/control/tests/add')
@admin_pages.route('/control/tests/edit/<int:id>')
@check_admin
def tests_edit(id=None):
    test = Test(g.conn, id=id)
    logging.debug("Repeat interval: %s", test['repeat_interval'])
    if not id:
        test['check_interval'] = datetime.timedelta(0)
        test['repeat_interval'] = datetime.timedelta(0)
    return render_template('tests_edit.html',
                           test=test,
                           isps=load_isp_data(),
                           countries=load_country_data(),
                           filters=load_data('filters'),
                           tags=[ x['id'] for x in Tags.select_all(g.conn, _orderby='id')]
                           )

@admin_pages.route('/control/tests/update', methods=['POST'])
@check_admin
def tests_update():
    f = request.form
    
    test = Test(g.conn, id=(f['id'] or None))
    test.update({
        'name': f['name'],
        'description': f['description'],
        'check_interval': "{0} {1}".format(f['check_interval_num'], f['check_interval_unit']),
        'repeat_interval': 
            "{0} {1}".format(f['repeat_interval_num'], f['repeat_interval_unit'])
            if f.get('repeat_enable') else None,
        'batch_size': f['batch_size']
    })
    
    
    if f.get('source') == 'query':
        test['filter'] = f['filter']
    elif f.get('source') == 'tag':
        test['tags'] = [f['tag']]
        test['filter'] = None
        
    if 'isps' in f:
        test['isps'] = f.getlist('isps')
    else:
        test['isps'] = []
        
    test.store()
    g.conn.commit()
    flash("Test case updated")
    return redirect(url_for('.tests'))

@admin_pages.route('/control/tests/delete/<int:id>')
@check_admin
def tests_delete(id):
    t = Test(g.conn, id)
    t.delete()
    g.conn.commit()
    flash("Test case deleted")
    return redirect(url_for('.tests'))
    
@admin_pages.route('/control/tests/status/<int:id>/<status>')
@check_admin
def tests_status(id, status):
    t = Test(g.conn, id)
    t['status'] = status.upper()
    if status.upper() == 'RUNNING':
        t['status_message'] = ''
        if not t.get('last_run'):
            t['last_run'] = datetime.datetime.now()
    t.store()
    g.conn.commit()
    flash("Test status updated.")
    return redirect(url_for('.tests'))    
