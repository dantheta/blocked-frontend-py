import datetime

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session

from models import ISPReport, Category
from NORM.exceptions import ObjectNotFound
from utils import *
from resources import *

stats_pages = Blueprint('stats', __name__,
    template_folder='templates/stats')


@stats_pages.route('/stats')
def stats():
    if current_app.config['SITE_THEME'] == 'blocked-eu':
        return stats_eu()
    else:
        return stats_gb()

def stats_eu():
    import operator
    results = g.api.country_stats()
    countries = load_country_data()

    # exclude EU region and sort by country name
    stats = sorted([x for x in results['stats'] if x['region'] != 'eu'],
                   key=operator.itemgetter('region'),
                   cmp=lambda x,y: cmp(countries[x], countries[y]))

    labels = [countries[x['region']] for x in stats ]
    values = [x['blocked_url_count'] for x in stats ]

    return render_template('stats-eu.html',
                           labels = labels,
                           values = values,
                           countries=countries)


def stats_gb():
    result = g.api.isp_stats()
    g.remote_content = g.remote.get_content('stats')
    ispstats = result['isp-stats']
    isps = ispstats.keys()
    isps.sort()


    table_data = {
        'notonly_table_1':  load_csv('notonly_table_1'),
        'notonly_table_2':  load_csv('notonly_table_2'),
        'allkinds_table_1': load_csv('allkinds_table_1'),
        }

    reply_stats = list(ISPReport.get_reply_stats(g.conn))
    g.conn.commit()

    return render_template('stats.html',
        isps=isps,
        total=[ ispstats[x]['total']  for x in isps ],
        blocked=[ ispstats[x]['blocked'] for x in isps ],

        domain_isp_stats = g.api.domain_isp_stats(),

        table_data = table_data,
        reply_stats = reply_stats
        
        )


@stats_pages.route('/stats/probes')
def probe_stats():
    data = g.api.status_probes(current_app.config['DEFAULT_REGION'])
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
        )
