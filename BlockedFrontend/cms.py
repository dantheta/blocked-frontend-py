
import logging
import jinja2

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, Response

from utils import *
from models import Item, ISPReport
import models
from NORM import Query
from NORM.exceptions import ObjectNotFound

from resources import load_country_data

cms_pages = Blueprint('cms',
                      __name__,
                      template_folder='templates/cms')

REMOTE_CONTENT_TYPES = ['pages', 'layoutpages']

REMOTE_TEXT_CONTENT = {
    'index': 'homepage-text',
    'legal-blocks': 'legal-blocks',
    'seized-domains': 'seized-domains'
    }

PAGE_ITEMS = 25


def custom_routing(site):
    if site == 'blocked-eu':
        cms_pages.add_url_rule('/', 'legal_blocks', legal_blocks)
    else:
        cms_pages.add_url_rule('/', 'index', index)


def frontpage_lists():
    
    for item in Item.get_frontpage_random(g.conn, current_app.config['RANDOM_EXCLUDE_NETWORKS']):
        site = g.api.status_url(item['url'])
        savedlist = item.get_list()
        return site, savedlist


def frontpage_random():
    randomsite = g.api.GET('ispreport/candidates', {'count': 1})
    site = g.api.status_url(randomsite['results'][0])
    return site


def index():
    g.remote_content = g.remote.get_content('homepage-text')
    session['route'] = 'random'
    stats = g.api.stats()

    if current_app.config['RANDOMSITE'] == 'frontpagerandom':
        site = frontpage_random()
        savedlist = None
    elif current_app.config['RANDOMSITE'] == 'frontpagelists':
        site, savedlist = frontpage_lists()
    else:
        current_app.logger.warn("Unknown RANDOMSITE provider")
        abort(500)

    blockednetworks = [x['network_id'] for x in site['results']
                       if x['status'] == 'blocked']
    g.conn.commit()
    return render_template('index.html', site=site, savedlist=savedlist,
                           stats=stats['stats'],
                           blockednetworks=blockednetworks)


@cms_pages.route('/personal-stories')
@cms_pages.route('/personal-stories/<name>')
def personal_stories(name=None):
    if current_app.config['REMOTE_TYPE'] == 'cockpit':
        if not name:
            entries = g.remote.get_collection('personal_stories')
            return render_template('personal-stories-index.html',
                                   entries=entries)
        else:
            try:
                entry = g.remote.get_content(name, 'personal_stories', 'slug')
            except ValueError as exc:
                if exc.args[0].startswith('Entries'):
                    abort(404)
                raise
            return render_template('personal-stories-story.html',
                                   entry=entry)
    else:
        g.remote_content = g.remote.get_content('personal-stories')
        return render_template('personal-stories.html',
                               featured=models.ISPReport.get_featured(g.conn))


@cms_pages.route('/credits')
def credits():
    g.remote_content = g.remote.get_content('credits')
    return render_template('credits.html')


@cms_pages.route('/reported-sites/by-category')
def reported_sites_category():
    q = ISPReport.get_category_stats(g.conn)

    return render_template('reported_sites_category.html',
                           categories=q)


@cms_pages.route('/reported-sites')
@cms_pages.route('/reported-sites/<int:page>')
@cms_pages.route('/reported-sites/<isp>')
@cms_pages.route('/reported-sites/<isp>/<int:page>')
def reported_sites(isp=None, page=1):
    a = request.args
    if isp:
        if isp not in current_app.config['ISPS']:
            # search for case insensitive match and redirect
            for _isp in current_app.config['ISPS']:
                if _isp.lower() == isp.lower():
                    return redirect(url_for('.reported_sites',
                                            isp=_isp,
                                            state=a.get('state'),
                                            policy=a.get('policy'),
                                            cat=a.get('category'),
                                            list=a.get('list')
                                            ))
            # otherwise, return a 404
            abort(404)
    filter_args = {'state', 'category', 'list', 'policy', 'year'}

    g.remote_content = g.remote.get_content('reported-sites')
    data = g.api.reports(page-1, 
                         isp=isp,
                         state=a.get('state'),
                         category=a.get('category'),
                         list=a.get('list'),
                         policy=a.get('policy'),
                         year=a.get('year')
                         )
    reports = data['reports']

    count = data['count']
    pagecount = get_pagecount(count, 25)
    if page > pagecount or page < 1:
        abort(404)
    return render_template('reports.html',
                           current_isp=isp,
                           filters=filter_args & set(a.keys()),
                           page=page, count=count, pagecount=pagecount,
                           reports=reports)


@cms_pages.route('/reported-sites', methods=["POST"])
def reported_sites_post():
    f = request.form
    isp = f['isp']
    if isp:
        return redirect(url_for('.reported_sites', isp=isp, category=f.get('category')))
    else:
        return redirect(url_for('.reported_sites', category=f.get('category')))


@cms_pages.route('/bbfc-reports')
@cms_pages.route('/bbfc-reports/<int:page>')
def reported_sites_bbfc(page=1):
    g.remote_content = g.remote.get_content('bbfc-reports')
    data = g.api.reports(page-1, isp='BBFC')
    count = data['count']
    pagecount = get_pagecount(count, 25)
    if page > pagecount or page < 1:
        abort(404)
    return render_template('reports.html',
                           enable_filter_form=False,
                           current_isp='BBFC',
                           page=page,
                           count=count,
                           pagecount=pagecount,
                           reports=data['reports'])


@cms_pages.route('/bbfc-reports/view/<path:url>')
def bbfc_report_view(url):
    g.remote_content = g.remote.get_content('bbfc-report-view')

    url = fix_path(url)

    data = g.api.status_url(url, current_app.config['DEFAULT_REGION'])
    results = [x for x in data['results'] if x['isp_active']]

    try:
        urlobj = models.Url.select_one(g.conn, url=url)
        report = models.ISPReport.select_one(g.conn, urlid=urlobj['urlid'], network_name='BBFC')
        messages = report.get_emails_parsed()

        return render_template('bbfc_report_view.html',
                               url=url,
                               urlobj=urlobj,
                               report=report,
                               results_all=results,
                               messages=messages)
    except ObjectNotFound:
        abort(404)


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
        for _type in REMOTE_CONTENT_TYPES:
            try:
                g.remote_content = g.remote.get_content(page, _type)
                break
            except Exception:
                pass

        logging.debug("page content: %s", g.remote_content.keys())

        if _type == 'layoutpages':
            return render_template('remote_layout.html', content=g.remote_content)

        if set(g.remote_content.keys()).intersection(['TextAreaFour', 'TextAreaFive', 'TextAreaSix']):
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


@cms_pages.route('/cms/assets/<path:path>')
def cms_asset(path):
    if current_app.config['REMOTE_TYPE'] != 'cockpit':
        abort(500)

    try:
        req = g.remote.get_asset('/'+path)
    except ValueError as exc:
        abort(exc.args[0])
    return Response(req.iter_content(1024), req.status_code, 
                    {'Content-type': req.headers['Content-type'],
                    'Content-length': req.headers['Content-length']})


@cms_pages.route('/faqs')
def faqs():
    import itertools

    content = g.remote.get_content('faqs')
    articles = g.remote.get_collection(_type='faqs')
    grouped_faqs = itertools.groupby(articles, lambda x: x['heading'])

    return render_template('faqs.html', faqs=grouped_faqs, content=content)
