from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session

stats_pages = Blueprint('stats', __name__,
    template_folder='templates/stats')

@stats_pages.route('/stats')
def index():
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
        categories = ["{1} ({0})".format(x['network_name'], x['category']) for x in category_stats['stats']]
        
        )
