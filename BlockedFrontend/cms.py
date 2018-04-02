
import logging
import psycopg2
import jinja2

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, Response

from utils import *
from models import Item
from NORM import Query

from resources import load_country_data

cms_pages = Blueprint('cms', __name__,
    template_folder='templates/cms')

REMOTE_TEXT_CONTENT = {
    'index': 'homepage-text',
    'legal-blocks': 'legal-blocks',
    'seized-domains': 'seized-domains'
    }

def custom_routing(site):
    if site == 'blocked-eu':
        cms_pages.add_url_rule('/', 'legal_blocks', legal_blocks)
    else:
        cms_pages.add_url_rule('/', 'index', index)

def frontpage_lists():
    conn = psycopg2.connect(current_app.config['DB'])
    for item in Item.get_frontpage_random(conn):
        site = request.api.status_url(item['url'])
        savedlist = item.get_list()
        return site, savedlist
        
def frontpage_random():
    randomsite = request.api.GET('ispreport/candidates',{'count':1})
    site = request.api.status_url(randomsite['results'][0])
    return site

def index():
    g.remote_content = g.remote.get_content('homepage-text')
    session['route'] = 'random'
    stats = request.api.stats()

    if current_app.config['RANDOMSITE'] == 'frontpagerandom':
        site = frontpage_random()
        savedlist = None
    elif current_app.config['RANDOMSITE'] == 'frontpagelists':
        site, savedlist = frontpage_lists()

    blockednetworks = [ x['network_id'] for x in site['results']
        if x['status'] == 'blocked' ]
    return render_template('index.html', site=site, savedlist=savedlist,
                           stats=stats['stats'],
                           blockednetworks=blockednetworks)

@cms_pages.route('/personal-stories')
def personal_stories():
    g.remote_content = g.remote.get_content('personal-stories')
    return render_template('personal-stories.html')

@cms_pages.route('/credits')
def credits():
    g.remote_content = g.remote.get_content('credits')
    return render_template('credits.html')

@cms_pages.route('/legal-blocks')
@cms_pages.route('/legal-blocks/<int:page>')
@cms_pages.route('/legal-blocks/<region>')
@cms_pages.route('/legal-blocks/<region>/<int:page>')
def legal_blocks(page=1, region=None):
    g.remote_content = g.remote.get_content('legal-blocks')
    if current_app.config['SITE_THEME'] == 'blocked-uk':
        style = 'injunction'
    else:
        style = 'urlrow'
    if not region:
        region = current_app.config['DEFAULT_REGION']
    data = request.api.recent_blocks(page-1, region, style, request.args.get('sort','url'))
    blocks = data['results']
    count = data['count']
    urlcount = data['urlcount']
    return render_template('legal-blocks.html',
            countries = load_country_data(),
            region=region,
            page=page, count=count, blocks=blocks, urlcount=urlcount, sortorder=request.args.get('sort','url'),
            pagecount = get_pagecount(urlcount, 25)
            )

@cms_pages.route('/reported-sites')
@cms_pages.route('/reported-sites/<int:page>')
@cms_pages.route('/reported-sites/<isp>')
@cms_pages.route('/reported-sites/<isp>/<int:page>')
def reported_sites(isp=None, page=1):
    if isp:
        if isp not in current_app.config['ISPS']:
            # search for case insensitive match and redirect
            for _isp in current_app.config['ISPS']:
                if _isp.lower() == isp.lower():
                    return redirect( url_for('.reported_sites', isp=_isp) )
            # otherwise, return a 404
            abort(404)
    g.remote_content = g.remote.get_content('reported-sites')
    data = request.api.reports(page-1, isp=isp)
    data2 = request.api.ispreport_stats()
    count = data['count']
    pagecount = get_pagecount(count, 25)
    if page > pagecount or page < 1:
        abort(404)
    return render_template('reports.html',
            current_isp=isp,
            stats=data2['unblock-stats'],
            networks = g.remote.get_networks(),
            page=page, count=count, pagecount=pagecount, 
            reports=data['reports'])

@cms_pages.route('/reported-sites', methods=["POST"])
def reported_sites_post():
    f = request.form
    isp = f['isp']
    if isp:
        return redirect( url_for('.reported_sites', isp=isp) )
    else:
        return redirect( url_for('.reported_sites') )

@cms_pages.route('/legal-blocks/export')
@cms_pages.route('/legal-blocks/export/<region>')
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
    writer.writerow(['#', "URL: " + current_app.config['SITE_URL'] + url_for('.legal_blocks') ])
    writer.writerow([])
    writer.writerow(['URL', 'Report URL', 'Networks'])

    def get_legal_blocks():
        page = 0
        while True:
            data = request.api.recent_blocks(page, region)
            
            for item in data['results']:
                yield item['url'], item['network_name']
            page += 1
            if page > get_pagecount(data['count'], 25):
                break

    for url, networkiter in itertools.groupby(get_legal_blocks(), lambda row: row[0]):
        networklist = [x[1] for x in networkiter]
        networklist.sort()
        writer.writerow([url, current_app.config['SITE_URL']+ url_for('site.site', url=url) ] + networklist)

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
        'networks'
    ]

    tmpfile = tempfile.SpooledTemporaryFile('w+')
    writer = csv.writer(tmpfile)
    writer.writerow(['#', "Title: Legal blocks"])
    writer.writerow(['#', "List saved from blocked.org.uk"])
    writer.writerow(['#', "URL: " + current_app.config['SITE_URL'] + url_for('.legal_blocks')])
    writer.writerow([])
    #writer.writerow(['URL', 'Report URL', 'Networks'])
    writer.writerow([x.replace('_',' ').title() for x in COLS])

    def get_legal_blocks():
        page = 0
        while True:
            data = request.api.recent_blocks(page, region, 'injunction')
            for item in data['results']:                
                yield [item[x] for x in COLS if x != 'networks'] + item['networks']
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

    return Response(returnvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=legal-blocks.csv',
        'Content-length': str(length)
    })


# static page routing
@cms_pages.route('/<page>')
def wildcard(page='index'):
    if '/' in page:
        return "Invalid page name", 400
    if page == 'favicon.ico':
        return "", 404


    g.remote_content = {}
    if page in REMOTE_TEXT_CONTENT:
        try:
            g.remote_content = g.remote.get_content(REMOTE_TEXT_CONTENT[page])
        except Exception:
            pass

    if page in current_app.config['REMOTE_PAGES']:
        # page uses generic template from local filesystem, and pretty much requires
        # remote content
        g.remote_content = g.remote.get_content(page)

        logging.info("page content: %s", g.remote_content.keys())
        if set(g.remote_content.keys()).intersection(
            ['TextAreaFour','TextAreaFive','TextAreaSix']
            ):
            return render_template('remote_content2x3.html',
                content=g.remote_content
                )
        return render_template('remote_content1x3.html',    
            content=g.remote_content
            )

    try:
        # template exists in local filesystem, but can accept remote content
        return render_template(page + '.html')
    except jinja2.TemplateNotFound:
        abort(404)

@cms_pages.route('/legal-blocks/errors')
def legal_errors():
    conn = psycopg2.connect(current_app.config['DB'])    
    q = Query(conn, """
        select count(distinct urls.urlid) total, count(distinct case when cjuf.id is not null then cjuf.id else 0 end) error_count

        from url_latest_status uls
        inner join urls on uls.urlid = urls.urlid
        left join frontend.court_judgment_urls cju on urls.url = cju.url
        left join frontend.court_judgment_url_flags cjuf on cjuf.urlid = cju.id
        where blocktype='COPYRIGHT' and uls.status = 'blocked'""", 
        [])
    stats1 = q.fetchone()
    q.close()
    
    stats2 = Query(conn, """
        select reason, count(*) error_count
        from frontend.court_judgment_urls cju 
        inner join frontend.court_judgment_url_flags cjuf on cjuf.urlid = cju.id
        group by reason""", 
        [])
    
    stats3 = Query(conn, """
        select cju.url, reason, cjuf.created, cj.citation, cj.case_number, cj.url as judgment_url
        from frontend.court_judgment_urls cju 
        inner join frontend.court_judgment_url_flags cjuf on cjuf.urlid = cju.id
        inner join frontend.court_judgments cj on cj.id = cju.judgment_id
        order by url""", [])
    
    conn.commit()
    return render_template('legal-block-errors.html',
                           stats1=stats1,
                           stats2=stats2,
                           stats3=stats3 )
