import logging
import jinja2

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, Response

from utils import *
import models
from NORM import Query
from NORM.exceptions import ObjectNotFound

from resources import load_country_data

injunct_pages = Blueprint('injunct',
                          __name__,
                          template_folder='templates/injunctions',
                          static_folder='static')


@injunct_pages.route('/')
@injunct_pages.route('/legal-blocks')
def legal_orders():

    g.remote_content = g.remote.get_content('legal-blocks-orders')
    region = current_app.config['DEFAULT_REGION']
    q = Query(g.conn,
              """
              select judgment_id as id, judgment_name as name, judgment_date as date, citation, 
    
                count(distinct flag_url_id) errors_detected,
                count(distinct url_group_name) services_targeted,
                sum(block_count) as block_count
    
                from active_court_blocks 
                where (region = %s or region is null)
                group by judgment_id , judgment_name , judgment_date , citation
              """,
              [region])

    return render_template('legal-block-orders.html',
                           judgments=q,
                           region=region)


@injunct_pages.route('/legal-blocks/errors')
@injunct_pages.route('/legal-blocks/errors/<int:page>')
def legal_errors(page=1):
    sort = request.args.get('sort', 'url')
    o = request.args.get('o', 'a')

    if sort not in ('url', 'reason', 'created'):
        abort(400)

    # error totals - large stats panel

    q = Query(g.conn,
              """
              select count(distinct urls.urlid) total,
              count(distinct case when cjuf.id is not null then cjuf.id else null end) error_count
    
              from url_latest_status uls
              inner join urls on uls.urlid = urls.urlid
              inner join isps on isps.name = uls.network_name
              left join frontend.court_judgment_urls cju on urls.url = cju.url
              left join frontend.court_judgment_url_flags cjuf on
                cjuf.judgment_url_id = cju.id and cjuf.reason != 'block_appears_correct'
              where blocktype='COPYRIGHT' and uls.status = 'blocked' and urls.status = 'ok' 
                and isps.regions && %s::varchar[]
                and (isps.isp_type = 'mobile' or isps.filter_level = 'No Adult')
                and urls.url ~* '^https?://[^/]+$'
                -- 
              """,
              [[current_app.config['DEFAULT_REGION']]]
              )
    stats1 = q.fetchone()
    q.close()

    # summary of block errors by reason
    stats2 = Query(g.conn,
                   """
                   select reason, count(distinct urls.urlid) error_count
                   from url_latest_status uls
                   inner join urls on uls.urlid = urls.urlid
                   inner join isps on isps.name = uls.network_name
                   inner join frontend.court_judgment_urls cju on urls.url = cju.url
                   inner join frontend.court_judgment_url_flags cjuf on cjuf.judgment_url_id = cju.id
                   where blocktype='COPYRIGHT' and uls.status = 'blocked' and urls.status = 'ok' 
                       and isps.regions && %s::varchar[]
                       and urls.url ~* '^https?://[^/]+$'
                       and (isps.isp_type = 'mobile' or isps.filter_level = 'No Adult')
                       -- and cjuf.reason != 'block_appears_correct'
            
                   group by reason""",
                   [[current_app.config['DEFAULT_REGION']]]
                   )

    # main error listing
    q_stats3_count = Query(g.conn,
                           """
                           select count(*) ct from (select distinct cju.url, reason, cjuf.created, cj.citation,
                                   cj.case_number, cj.url 
                               from url_latest_status uls
                               inner join urls on uls.urlid = urls.urlid
                               inner join isps on isps.name = uls.network_name
                               inner join frontend.court_judgment_urls cju on cju.url = urls.url
                               inner join frontend.court_judgment_url_flags cjuf on cjuf.judgment_url_id = cju.id
                               inner join frontend.court_judgments cj on cj.id = cju.judgment_id
                               where blocktype='COPYRIGHT' and uls.status = 'blocked' and urls.status = 'ok' 
                                   and isps.regions && %s::varchar[]
                                   and urls.url ~* '^https?://[^/]+$'        
                                   and (isps.isp_type = 'mobile' or isps.filter_level = 'No Adult')
                                   and cjuf.reason != 'block_appears_correct'
                                   ) x
                           """,
                           [[current_app.config['DEFAULT_REGION']]])

    stats3_count = q_stats3_count.fetchone()['ct']
    pagecount = get_pagecount(stats3_count, PAGE_ITEMS)

    stats3 = Query(g.conn,
                   """
                   select distinct cju.url, reason, cjuf.created, cj.citation, cj.case_number, cj.url as judgment_url
                   from url_latest_status uls
                   inner join urls on uls.urlid = urls.urlid
                   inner join isps on isps.name = uls.network_name
                   inner join frontend.court_judgment_urls cju on cju.url = urls.url
                   inner join frontend.court_judgment_url_flags cjuf on cjuf.judgment_url_id = cju.id
                   inner join frontend.court_judgments cj on cj.id = cju.judgment_id
                   where blocktype='COPYRIGHT' and uls.status = 'blocked' and urls.status = 'ok' 
                       and isps.regions && %s::varchar[]
                       and urls.url ~* '^https?://[^/]+$'        
                       and (isps.isp_type = 'mobile' or isps.filter_level = 'No Adult')
                       and cjuf.reason != 'block_appears_correct'
           
                   order by {0} {1}
                   limit {3} offset {2}""".format(sort, 'asc' if o == 'a' else 'desc', (page-1)*PAGE_ITEMS, PAGE_ITEMS),
                   [[current_app.config['DEFAULT_REGION']]]
                   )

    # stats listing by ISP
    stats4 = Query(g.conn,
                   """
                   select distinct isps.name, isps.description, count(distinct urls.urlid) total, 
                       count(distinct case when cjuf.id is not null then cjuf.id else null end) error_count
                   from url_latest_status uls
                   inner join urls on uls.urlid = urls.urlid
                   inner join isps on isps.name = uls.network_name
                   inner join frontend.court_judgment_urls cju on cju.url = urls.url
                   left join frontend.court_judgment_url_flags cjuf on cjuf.judgment_url_id = cju.id
                   inner join frontend.court_judgments cj on cj.id = cju.judgment_id
                   where blocktype='COPYRIGHT' and uls.status = 'blocked' and urls.status = 'ok' 
                       and isps.regions && %s::varchar[]
                       and urls.url ~* '^https?://[^/]+$'  
                       and (isps.isp_type = 'mobile' or isps.filter_level = 'No Adult')      
                       and cjuf.reason != 'block_appears_correct'
           
                   group by isps.name, isps.description
                   order by count(distinct urls.urlid) desc
                   """.format(sort),
                   [[current_app.config['DEFAULT_REGION']]]
                   )

    g.conn.commit()
    return render_template('legal-block-errors.html',
                           stats1=stats1,
                           stats2=stats2,
                           stats3=stats3,
                           stats4=stats4,

                           page=page,
                           pagecount=pagecount,
                           count=stats3_count,
                           )


@injunct_pages.route('/legal-blocks/orders')
def legal_orders_old():
    return redirect(url_for('.legal_orders'), 301)


@injunct_pages.route('/legal-blocks/<int:page>')
@injunct_pages.route('/legal-blocks/<region>')
@injunct_pages.route('/legal-blocks/<region>/<int:page>')
def legal_blocks_old(page=1, region=None):
    if region:
        return redirect(url_for('.legal_blocks', region=region, page=page), 301)
    return redirect(url_for('.legal_blocks', page=page), 301)


@injunct_pages.route('/legal-blocks/sites')
@injunct_pages.route('/legal-blocks/sites/<int:page>')
@injunct_pages.route('/legal-blocks/sites/<region>')
@injunct_pages.route('/legal-blocks/sites/<region>/<int:page>')
def legal_blocks(page=1, region=None):
    g.remote_content = g.remote.get_content('legal-blocks')
    if current_app.config['SITE_THEME'] == 'blocked-uk':
        style = 'injunction'
    else:
        style = 'urlrow'
    if not region:
        region = current_app.config['DEFAULT_REGION']
    data = g.api.recent_blocks(page-1, region, style, request.args.get('sort', 'url'))
    blocks = data['results']
    count = data['count']
    urlcount = data['urlcount']
    return render_template('legal-blocks.html',
                           countries=load_country_data(),
                           region=region,
                           page=page, count=count, blocks=blocks, urlcount=urlcount,
                           sortorder=request.args.get('sort', 'url'),
                           pagecount=get_pagecount(urlcount, 25)
                           )


@injunct_pages.route('/legal-blocks/order/<int:id>')
@injunct_pages.route('/legal-blocks/order/<int:id>/<int:page>')
def legal_order_sites(id, page=1):
    judgment = models.CourtJudgment(g.conn, id)

    return render_template('legal-block-report.html',
                           judgment=judgment,
                           blocks=judgment.get_report(current_app.config['DEFAULT_REGION']))


@injunct_pages.route('/legal-blocks/export')
@injunct_pages.route('/legal-blocks/export/<region>')
def export_blocks(region=None):
    if not region:
        region = current_app.config['DEFAULT_REGION']
    if current_app.config['SITE_THEME'] == 'blocked-uk':
        return export_blocks_by_injunction(region)
    else:
        return export_blocks_by_url(region)


def export_blocks_by_url(region):
    import csv
    import tempfile
    import itertools

    tmpfile = tempfile.SpooledTemporaryFile('w+')
    writer = csv.writer(tmpfile)
    writer.writerow(['#', "Title: Legal blocks"])
    writer.writerow(['#', "List saved from blocked.org.uk"])
    writer.writerow(['#', "URL: " + current_app.config['SITE_URL'] + url_for('.legal_blocks')])
    writer.writerow([])
    writer.writerow(['URL', 'Report URL', 'Networks'])

    def get_legal_blocks():
        page = 0
        while True:
            data = g.api.recent_blocks(page, region)

            for item in data['results']:
                yield item['url'], item['network_name']
            page += 1
            if page > get_pagecount(data['count'], 25):
                break

    for url, networkiter in itertools.groupby(get_legal_blocks(), lambda row: row[0]):
        networklist = [x[1] for x in networkiter]
        networklist.sort()
        writer.writerow([url, current_app.config['SITE_URL'] + url_for('site.site', url=url)] + networklist)

    tmpfile.flush()
    length = tmpfile.tell()
    tmpfile.seek(0)

    def returnvalue(*args):
        for line in tmpfile:
            yield line

    return Response(returnvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=legal-blocks.csv',
        'Content-length': str(length)
    })


def export_blocks_by_injunction(region):
    import csv
    import tempfile
    import itertools

    COLS = [
        'url',
        'judgment_name',
        'judgment_date',
        'judgment_url',
        'wiki_url',
        'judgment_sites_description',
        'citation',
        'url_group_name',
        'first_blocked',
        'last_blocked',
        'error_status',
        'additional_error_information',
    ]

    c = g.conn.cursor()
    c.execute("""select name from isps 
              where regions && %s::varchar[] and show_results=1
              order by name""",
              [[region]])
    networks = [row['name'] for row in c]
    c.close()

    tmpfile = tempfile.SpooledTemporaryFile('w+')
    writer = csv.writer(tmpfile)
    writer.writerow(['#', "Title: Legal blocks"])
    writer.writerow(['#', "List saved from blocked.org.uk"])
    writer.writerow(['#', "URL: " + current_app.config['SITE_URL'] + url_for('.legal_blocks')])
    writer.writerow([])
    # writer.writerow(['URL', 'Report URL', 'Networks'])
    writer.writerow([x.replace('_', ' ').title() for x in COLS]
                    + ['Networks:'] + networks)

    def get_legal_blocks():
        page = 0
        while True:
            data = g.api.recent_blocks(page, region, 'injunction')
            for item in data['results']:
                yield [
                          item[x].encode('utf8') if isinstance(item[x], unicode) else item[x]
                          for x in COLS
                      ] + [""] + [
                          "Y" if x in item['networks'] else ""
                          for x in networks
                      ]
            page += 1
            if page > get_pagecount(data['urlcount'], 25):
                break

    for row in get_legal_blocks():
        writer.writerow(row)

    tmpfile.flush()
    length = tmpfile.tell()
    tmpfile.seek(0)

    def returnvalue(*args):
        for line in tmpfile:
            yield line

    g.conn.commit()
    return Response(returnvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=legal-blocks.csv',
        'Content-length': str(length)
    })

