import re
import logging

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, session

from utils import *
from models import SavedList, Item
from db import *

from NORM.exceptions import ObjectNotFound

site_pages = Blueprint('site', __name__,
                       template_folder='templates/site')

@site_pages.route('/check', methods=['GET'])
@site_pages.route('/check/<mode>', methods=['GET'])
def check(mode=None):
    if 'route' in session:
        del session['route']
    g.remote_content = g.remote.get_content('check')
    return render_template('check.html',
            live = (mode == 'live'),
            )


@site_pages.route('/check', methods=['POST'])
def check_post():
    url = request.form['url']
    if not url.lower().startswith(('http://', 'https://')):
        url = 'http://' + url

    if request.form['submit'] == 'false':
        return redirect(url_for('.site', url=url))
    req = {
        'url': url,
    }
    req['signature'] = request.api.sign(req, ['url'])
    data = request.api.POST('submit/url', req)
    if data['queued'] == True:
        return render_template('site.html',
                               results_blocked=[], results_past=[], results_all=[],
                               activecount=0,
                               pastcount=0,
                               can_unblock=None,
                               domain=get_domain(url),
                               url=url,
                               md5=data['hash'],
                               live=True
                               )
    return redirect(url_for('.site', url=url))


@site_pages.route('/site')
@site_pages.route('/site/<path:url>')
@site_pages.route('/results')
def site(url=None):
    if not url:
        url = request.args['url']

    try:
        thanks = session.pop('thanks')
    except KeyError:
        thanks = False
    try:
        thanksmsg = session.pop('thanksmsg')
    except KeyError:
        thanksmsg = None

    # workaround for apache folding // into /
    url = re.sub(':/(?!/)', '://', url)

    data = request.api.status_url(url)
    activecount = 0
    pastcount = 0
    can_unblock = None
    prev_unblock_type = None

    results = [x for x in data['results'] if x['isp_active']]
    for item in results:
        if item['status'] == 'blocked':
            activecount += 1
            if item['last_report_timestamp']:
                if can_unblock is None:
                    can_unblock = False
                    prev_unblock_type = 'unblock'
            else:
                can_unblock = True
        else:
            if item['last_blocked_timestamp']:
                pastcount += 1

    report_types = set()
    for report in data['reports']:
        if report['report_type'] != 'unblock':
            can_unblock = False
            prev_unblock_type = 'flag'
            report_types.update(report['report_type'].split(','))

    if data.get('blacklisted') in (True, 'true'):
        can_unblock = False
        logging.info("Site is blacklisted")
        prev_unblock_type = 'blacklist'

    if session.get('route') == 'savedlist':
        logging.info("Selecting savedlist")
        savedlist = SavedList.select_one(db_connect(), name=session['savedlist'][0])
    else:
        try:
            item = Item.select_one(db_connect(), url=url)
            savedlist = item.get_list()
            if not savedlist['public']:
                savedlist = None
        except ObjectNotFound:
            savedlist = None

    return render_template('site.html',
                           results_blocked=(result for result in results if result['status'] == 'blocked'),
                           results_past=(result for result in results if
                                         result['status'] != 'blocked' and result['last_blocked_timestamp']),
                           results_all=(result for result in results if
                                        result['status'] != 'blocked' and not result['last_blocked_timestamp']),

                           activecount=activecount,
                           pastcount=pastcount,
                           can_unblock=can_unblock,
                           domain=get_domain(url),
                           url=url,
                           report_types=report_types,
                           prev_unblock_type=prev_unblock_type,
                           savedlist=savedlist,

                           networks=g.remote.get_networks(),
                           thanks=thanks,
                           thanksmsg=thanksmsg
                           )


