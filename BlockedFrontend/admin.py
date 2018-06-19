
import os
import re
import psycopg2
import logging
import datetime

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify

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
    reports = g.api.reports(page-1, admin=True)
    return render_template('ispreports.html', reports=reports,
                           page=page,
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
              select count(*) ct from urls
              inner join url_latest_status uls on uls.urlid = urls.urlid
              inner join isps on isps.name = uls.network_name and regions && %s::varchar[]
                and (isps.filter_level = 'No Adult' or isps.isp_type = 'mobile')
              left join court_judgment_urls cu on urls.url = cu.url
              where urls.status = 'ok' and uls.status = 'blocked' 
                and urls.url ~* '^https?://[^/]+$'
                and uls.blocktype = 'COPYRIGHT' and cu.url is null
              """,
              [[current_app.config['DEFAULT_REGION']]]

             )
    count = q.fetchone()['ct']
    q.close()
    
    q = Query(g.conn, 
              """
              select urls.url, network_name, uls.created, uls.first_blocked, whois_expiry from urls
              inner join url_latest_status uls on uls.urlid = urls.urlid
              inner join isps on isps.name = uls.network_name and regions && %s::varchar[]
                and (isps.filter_level = 'No Adult' or isps.isp_type = 'mobile')
              left join court_judgment_urls cu on urls.url = cu.url
              where urls.status = 'ok' and uls.status = 'blocked' 
                and urls.url ~* '^https?://[^/]+$'
                and uls.blocktype = 'COPYRIGHT' and cu.url is null
              order by uls.first_blocked limit 25 offset {0}""".format(offset),
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
        obj = CourtJudgment(g.conn, id)
        obj.update({x: convertnull(f[x]) for x in CourtJudgment.FIELDS})
        obj.store()

        applies = f.getlist('applies')
        for order_id, network_name, url, date, expiry_date in zip(
                f.getlist('order_id'), f.getlist('network_name'), f.getlist('applies_url'),
                f.getlist('order_date'), f.getlist('expiry_date')):

            order = CourtOrder(g.conn, order_id or None)
            if network_name in applies:
                order.update({
                    'url': url,
                    'judgment_id': obj['id'],
                    'date': convertnull(date),
                    'expiry_date': convertnull(expiry_date),
                })
            else:
                if order_id:
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
        where f.urlid = %s
        order by f.date_observed desc""",
        [url['id']])
    
    try:
        flag = CourtJudgmentURLFlag.select_one(g.conn, 
                                               urlid = url['id'])
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

@admin_pages.route('/control/courtorders/site/flag', methods=['POST'])
@check_admin
def courtorders_site_flag_post():
    f = request.form
    url = CourtJudgmentURL(g.conn, id=f['urlid'])
    
    if 'delete' in f:
        try:
            flag = CourtJudgmentURLFlag.select_one(g.conn, urlid = url['id'])
            flag.delete()
            judgment = url.get_court_judgment()
            g.conn.commit()
            flash("Url {0} unflagged".format(url['url']))
            return redirect(url_for('.courtorders_view', id=judgment['id']))
        except ObjectNotFound:
            g.conn.rollback()
            abort(404)
        
    
    try:
        flag = CourtJudgmentURLFlag.select_one(g.conn, urlid = url['id'])
    except ObjectNotFound:
        flag = CourtJudgmentURLFlag(g.conn)
        
    flag.update({
        'reason': f['reason'],
        'description': f['description'],
        'date_observed': f['date_observed'] or None,
        'abusetype': f['abusetype'] if f['reason'] == 'domain_may_be_abusive' else None,
        'urlid': f['urlid']
    })
    flag.store()
    judgment = url.get_court_judgment()
    g.conn.commit()
    flash("Url {0} flagged".format(url['url']))
    return redirect(url_for('.courtorders_view', id=judgment['id']))

@admin_pages.route('/control/courtorders/site/flag/delete/<int:id>', methods=['GET'])
@check_admin
def courtorders_site_flag_delete(id):
    q = Query(g.conn, 
              "delete from court_judgment_url_flag_history where id = %s returning urlid as urlid",
              [id])
    row = q.fetchone()
    
    g.conn.commit()
    flash("Historical flag removed")
    return redirect(url_for('.courtorders_site_flag', id=row['urlid']))
    
    

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


## Tests admin

@admin_pages.route('/control/tests')
@check_admin
def tests():
    tests = Test.select(g.conn, _orderby='name')
    return render_template('tests.html', tests=tests)

@admin_pages.route('/control/tests/add')
@admin_pages.route('/control/tests/edit/<int:id>')
@check_admin
def tests_edit(id=None):
    test = Test(g.conn, id=id)
    if not id:
        test['check_interval'] = datetime.timedelta(0)
    return render_template('tests_edit.html',
                           test=test,
                           isps=load_isp_data(),
                           countries=load_country_data(),
                           filters=load_data('filters'),
                           tags=load_data('tags')
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
        'repeat_interval': f.get('repeat_interval') or None,
        'batch_size': f['batch_size']
    })
    
    if f.get('source') == 'query':
        test['filter'] = f['filter']
    elif f.get('source') == 'tag':
        test['tags'] = [f['tag']]
        
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
    t.store()
    g.conn.commit()
    flash("Test status updated.")
    return redirect(url_for('.tests'))    
