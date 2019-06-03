import logging

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, session, current_app

from utils import *
from resources import *
from models import SavedList, Item, CourtJudgmentURL
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
    url = request.form['url'].strip()
    if not url.lower().startswith(('http://', 'https://')):
        url = 'http://' + url

    if request.form['submit'] == 'false':
        return redirect(url_for('.site', url=url))

    data = g.api.submit_url(url)

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

    country_names = load_country_data()

    try:
        thanks = session.pop('thanks')
    except KeyError:
        thanks = False
    try:
        thanksmsg = session.pop('thanksmsg')
    except KeyError:
        thanksmsg = None

    # workaround for apache folding // into /
    url = fix_path(url)

    data = g.api.status_url(url, current_app.config['DEFAULT_REGION'])
    activecount = 0
    pastcount = 0
    can_unblock = None
    prev_unblock_type = None

    try:
        alt_url_data = [ x for x in data['related'] if x['rel'] == "scheme"][0]
    except IndexError:
        alt_url_data = None

    url_status = data['url-status']

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
        savedlist = SavedList.select_one(g.conn, name=session['savedlist'][0])
    else:
        try:
            item = Item.get_public_list_item(g.conn, url)
            savedlist = item.get_list()
        except ObjectNotFound:
            savedlist = None

    try:
        judgment_url = CourtJudgmentURL.select_one(g.conn, url=url)
        judgment = judgment_url.get_court_judgment()
        judgment_orders = judgment.get_court_orders_by_network()
        judgment_url_flag = judgment_url.get_flag()
        can_unblock = False
    except ObjectNotFound:
        judgment = None
        judgment_orders = {}
        judgment_url_flag = None
        pass
    print judgment_orders
    g.conn.commit()
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
                           reports=data.get('reports',[]),
                           prev_unblock_type=prev_unblock_type,
                           savedlist=savedlist,

                           url_status = url_status,

                           networks=g.remote.get_networks(),
                           thanks=thanks,
                           thanksmsg=thanksmsg,

                           country_names=country_names,

                           judgment = judgment,
                           judgment_orders=judgment_orders,
                           cjuf = judgment_url_flag,
                           
                           alt_url_data = alt_url_data,

                           page_title = data.get('title'),

                           categories = data.get('categories_full', [])
                           )


@site_pages.route('/stream-results-dummy')
def stream_results_dummy():
    from hashlib import md5
    from flask import Response
    import json
    import time

    url = request.args['url']

    def dummy():
        networks = ['BT', 'Sky', 'TalkTalk', 'AAISP']
        yield json.dumps({
            'type': 'status',
            'tag': 'dummy',
            'hash': md5(url).hexdigest(),
            'url': url
        }) + "\r\n"

        for network in networks:
            yield json.dumps({
                'network_name': network,
                'status': 'ok',
                'status_timestamp': get_timestamp(),
                'last_blocked_timestamp': None,
                'first_blocked_timestamp': None,
                'category': None
            }) + "\r\n"
        oldts = get_timestamp()
        time.sleep(2)
        for network in networks:
            yield json.dumps({
                'network_name': network,
                'status': 'blocked',
                'status_timestamp': get_timestamp(),
                'last_blocked_timestamp': get_timestamp(),
                'first_blocked_timestamp': None,
                'category': 'violence'
            }) + "\r\n"
            time.sleep(1)
        for network in networks:
            yield json.dumps({
                'network_name': network,
                'status': 'ok',
                'status_timestamp': get_timestamp(),
                'last_blocked_timestamp': oldts,
                'first_blocked_timestamp': None,
                'category': 'violence'
            }) + "\r\n"
            time.sleep(1)

    return Response(dummy(), content_type='application/json')


@site_pages.route('/stream-results')
def stream_results():
    from flask import Response, stream_with_context
    # hash = request.form['hash']
    url = request.args['url']

    def stream():
        req = {
            'url': url,
            'timeout': 20,
        }
        req['date'] = g.api.timestamp()
        req['signature'] = g.api.sign(req, ['url', 'date'])
        for row in g.api.GET('stream/results', req, _stream=True):
            print row
            yield row + "\r\n"

    return Response(stream_with_context(stream()))
