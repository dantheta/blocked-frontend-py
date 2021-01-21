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


admin_ispreport_pages = Blueprint('admin_ispreport', __name__, template_folder='templates/admin')

#
# ISP Report admin
# ------------------
#


@admin_ispreport_pages.route('/control/ispreports')
@check_reviewer
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
                           reportable_isps = load_data('isps')['reportable_isps'],
                           page=page,
                           all_categories=all_categories,
                           reporter_categories=reporter_categories,
                           damage_categories=damage_categories,
                           pagecount = get_pagecount(reports['count'], 25))


@admin_ispreport_pages.route('/control/ispreports/flag/<path:url>')
@check_admin
def ispreports_flag(url):
    url = fix_path(url)
    req = g.api.reports_flag(url, request.args.get('status','abuse'))
    if req['success'] != True:
        flash("An error occurred flagging \"{0}\": \"{1}\"".format(url, req['error']))
    return redirect(url_for('.ispreports',page=request.args.get('page',1)))


@admin_ispreport_pages.route('/control/ispreports/unflag/<path:url>')
@check_admin
def ispreports_unflag(url):
    url = fix_path(url)
    req = g.api.reports_unflag(url)
    if req['success'] != True:
        flash("An error occurred unflagging \"{0}\": \"{1}\"".format(url, req['error']))
    return redirect(url_for('.ispreports',page=request.args.get('page',1)))

@admin_ispreport_pages.route('/control/ispreports/resend/<path:url>')
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


@admin_ispreport_pages.route('/control/ispreports/escalate/<int:id>')
@check_admin
def ispreports_escalate(id):
    report = ISPReport(g.conn, id)
    urlobj = report.get_url()

    g.conn.commit()
    if report['status'] != 'rejected':
        return "Cannot escalate report unless report has been rejected by ISP", 400
    return render_template('ispreports_escalate.html',
                           report=report,
                           emailreply=report.get_final_reply(),
                           url=urlobj,
                           )


@admin_ispreport_pages.route('/control/ispreports/escalate/<int:id>', methods=['POST'])
@check_admin
def ispreports_escalate_post(id):
    emailtext = request.form['emailtext']
    report = ISPReport(g.conn, id)
    urlobj = report.get_url()

    req = {
        'url': urlobj['url'],
        'reporter': {
            'name': "Blocked admin",
            'email': "blocked@openrightsgroup.org",
        },
        'original_network': report['network_name'],
        'message': emailtext,
        'previous': request.form['previous'],
        'additional_contact': request.form['additional_contact'],
        'report_type': "unblock",
        'date': get_timestamp(),
        'send_updates': 0,
        'allow_publish': 1,
        'allow_contact': 1,
        'networks': ["BBFC"],
        'auth': {
            'email': g.api.username,
            'signature': '',
        }
    }

    req['auth']['signature'] = g.api.sign(req,  ['url','date'])
    if current_app.config['DUMMY']:
        # demo mode - don't really submit
        logging.warn("Dummy mode: not really submitting")
        data = {'verification_required':  False, 'success': True}
    else:
        data = g.api.POST_JSON('ispreport/submit', req)

    logging.info("Submission: %s", data)

    return redirect(url_for('.ispreports'))


@admin_ispreport_pages.route('/control/ispreports/unblocked/<int:id>')
@check_reviewer
def ispreports_status_unblocked(id):
    email = ISPReportEmail.select_one(g.conn, id)
    report = email.get_report()
    url = report.get_url()

    report.set_status('unblocked', email)
    g.conn.commit()

    return redirect(url_for('.ispreports_view', url=url['url'], network_name=report['network_name']))


@admin_ispreport_pages.route('/control/ispreports/rejected/<int:id>')
@check_reviewer
def ispreports_status_rejected(id):
    email = ISPReportEmail.select_one(g.conn, id)
    report = email.get_report()
    url = report.get_url()

    report.set_status('rejected', email)
    g.conn.commit()

    return redirect(url_for('.ispreports_view', url=url['url'], network_name=report['network_name']))


@admin_ispreport_pages.route('/control/ispreports/<network_name>/<path:url>')
@admin_ispreport_pages.route('/control/ispreports/<network_name>/<int:msgid>/<path:url>')
@check_reviewer
def ispreports_view(url, network_name, msgid=None):
    url = fix_path(url)
    urlobj = Url.select_one(g.conn, url=url)
    ispreport = ISPReport.get_by_url_network(g.conn, url, network_name)
    isp = ispreport.get_isp()
    contact = ispreport.get_contact()
    messagelist = list(ispreport.get_emails_parsed())
    if msgid:
        email = ISPReportEmail.select_one(g.conn, id=msgid)
        msg = email.decode()
    else:
        if len(messagelist):
            email, msg = messagelist[0]
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
                           categories = list(urlobj.get_categories()),
                           all_categories=all_categories,
                           messagelist=messagelist,
                           selected_msg=msg,
                           selected_email=email,
                           report_next=ispreport.get_next(),
                           report_prev=ispreport.get_prev(),
                           reporter_categories=reporter_categories,
                           damage_categories=damage_categories,
                           report_damage_categories=list(urlobj.get_report_categories('damage')),
                           reporter_category=urlobj.get_reporter_category(),
                           verified= contact and contact['verified'],
                           bbfc_report=ispreport.get_report_for("BBFC")
                           )


@admin_ispreport_pages.route('/control/ispreports/category/update', methods=['POST'])
@check_reviewer
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

    if f.get('add_category_name'):
        check_level('moderator')  # requires moderator or above
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


@admin_ispreport_pages.route('/control/ispreports/reportcategory/update', methods=['POST'])
@check_reviewer
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
            return UrlReportCategoryAsgt(g.conn, data=row)
        return None


    if f.get('new_reporter_category'):
        check_level('moderator')  # requires moderator or above

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
    if f.get('add_category_name').strip():
        check_level('moderator')  # requires moderator or above

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


@admin_ispreport_pages.route('/control/ispreports/review/update', methods=['POST'])
@check_reviewer
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


@admin_ispreport_pages.route('/control/ispreport/stats')
@check_reviewer
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


@admin_ispreport_pages.route('/control/ispreport/csv-stats')
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

@admin_ispreport_pages.route('/control/ispreport/reply-stats')
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


@admin_ispreport_pages.route('/control/ispreport/consistency')
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


@admin_ispreport_pages.route('/control/ispreports/category-status')
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


@admin_ispreport_pages.route('/control/ispreports/blocked_after_report')
@check_reviewer
def ispreport_reported_blocked():
    q = Query(g.conn, """
    select isp_reports.id, urlid, url, network_name, isp_reports.status, isp_report_emails.id as email_id, isp_reports.unblocked, uls.status as url_status,
    isp_reports.created, isp_report_emails.created as unblock_email_timestamp, isp_reports.last_updated, uls.created as status_timestamp 
    from public.isp_reports
    inner join url_latest_status uls using (network_name, urlid)
    inner join urls using (urlid)
    left join public.isp_report_emails on resolved_email_id = isp_report_emails.id
    where (isp_reports.status = 'unblocked' and uls.status = 'blocked')
    order by id desc;
    """, [])

    return render_template('ispreport_blocked_after_report.html',
                           data=q)
