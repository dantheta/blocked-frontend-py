import datetime

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session

from utils import *
from resources import *

stats_pages = Blueprint('stats', __name__,
    template_folder='templates/stats')


@stats_pages.route('/stats')
def stats():
    if current_app.config['SITE_THEME'] == 'blocked-eu':
        abort(404)
    else:
        return stats_gb()

def stats_gb():
    result = request.api.isp_stats()
    ispstats = result['isp-stats']
    isps = ispstats.keys()
    isps.sort()

    category_stats = request.api.category_stats()

    return render_template('stats.html',
        ispstats=ispstats,
        isps=isps,
        total=[ ispstats[x]['total']  for x in isps ],
        blocked=[ ispstats[x]['blocked'] for x in isps ],
        category_stats=category_stats['stats'],
        categories = ["{1} ({0})".format(x['network_name'], x['category']) for x in category_stats['stats']],

        domain_stats = request.api.domain_stats(),

        domain_isp_stats = request.api.domain_isp_stats()
        
        )


@stats_pages.route('/stats/probes')
def probe_stats():
    data = request.api.status_probes(current_app.config['DEFAULT_REGION'])
    country_names = load_country_data()


    now = datetime.datetime.now()
    for d in data['status']:
        d['parsed_timestamp'] = parse_timestamp(d['lastseen'])
        if d['parsed_timestamp']:
            d['age'] = now - d['parsed_timestamp']
        else:
            d['age'] = None
        d['country'] = country_names.get([x for x in d['regions'] if x != 'eu'][0])

    return render_template('stats/probes.html',
        data=data,
        country_names=country_names,
        networks=g.remote.get_networks(),
        )
