import re
import logging

from flask import Blueprint, render_template, redirect, request, \
    jsonify, g, url_for, session, current_app, Response, abort, flash

from .utils import *

from . import models
import NORM.exceptions
from NORM import Query

from .auth import *
from .db import *
from .resources import load_data

list_pages = Blueprint('list', __name__,
                       template_folder='templates/savedlists')


@list_pages.route('/list', methods=['POST'])
@check_moderator
def create_list():
    """Create a saved list"""
    f = request.form

    newlist = models.SavedList(g.conn)
    newlist.update({
        'name': f['name'],
        'username': f['username'],
        'public': True,
        })
    try:
        newlist.store()
    except NORM.exceptions.ObjectExists:
        # actually an integrityerror in disguise
        g.conn.rollback()
        return render_template('message.html', 
            title="List creation error",
            message="A list with this name already exists.  Please try again with a different list name.")

    n = 0
    page = 0
    while True:

        logging.info("Search page: %d", page)
        networks = f.get('network', None)
        if networks:
            networks=[networks]
        tld = f.get('tld', None)

        data = g.api.search_url(f['search'], page, exclude_adult = f.get('exclude_adult','0'), networks=networks, tld=tld)

        for site in data['sites']:
            newitem = models.Item(g.conn)
            newitem.update({
                'list_id': newlist['id'],
                'title': site['title'],
                'url': site['url']
                })
            newitem.store()

        n += len(data['sites'])
        if n >= data['count']:
            break
        page += 1

    g.conn.commit()

    return redirect(url_for('.show_list', name=f['name']))


@list_pages.route('/list/<name>', methods=['GET'])
@list_pages.route('/list/<name>/<int:page>', methods=['GET'])
def show_list(name, page=1):
    pagesize=20
    network = request.args.get('network')
    status = request.args.get('status')

    session['route'] = 'savedlist'
    if page < 1:
        return redirect(url_for('.show_list', name=name))
    try:
        savedlist = models.SavedList.select_one(g.conn, name=name)
    except NORM.exceptions.ObjectNotFound:
        abort(404)
    if not (savedlist['public'] or g.admin):
        abort(403)
   
    if network:
        itemcount = savedlist.count_items_on_network(network,
                                                     status=status,
                                                     domain=request.args.get('tld'),
                                                     exclude=request.args.get('exclude'))
        items = savedlist.get_items_on_network(network,
                                               status=status,
                                               domain=request.args.get('tld'),
                                               _limit=(pagesize, (page-1)*pagesize),
                                               exclude=request.args.get('exclude'))
    else:
        itemcount = savedlist.count_items(status=status, domain=request.args.get('tld'))
        items = savedlist.get_items(status=status, domain=request.args.get('tld'), _limit=(pagesize, (page-1)*pagesize))

    session['savedlist'] = (name, get_pagecount(itemcount, pagesize))
    g.conn.commit()
    return render_template('show_list.html',
            savedlist = savedlist,
            itemcount = itemcount,
            page = page,
            pagesize = pagesize,
            pagecount = get_pagecount(itemcount, pagesize), 
            items = items,
            reasons = load_data('flagreasons'),
            args = get_args_helper(['name','network','status','tld'],
                                   {'name': name, 'page': page})
            )


@list_pages.route('/lists')
def show_lists():
    return redirect(url_for('category.sites_search'))

@list_pages.route('/lists/check')
@check_moderator
def recheck_list():
    lst = models.SavedList.select_one(g.conn, name=request.args['name'])
    n = 0
    for item in lst.get_items():
        data = g.api.submit_url(item['url'], queue='public.gb')
        current_app.logger.info("Submitted: %s, queued=%s", item['url'], data['queued'])
        if data['queued']:
            n = n + 1

    flash("Submitted {0} URLs for list {1}".format(n, request.args['name']))
    return redirect(url_for('.show_list', name=request.args['name']))


@list_pages.route('/list/delete/<int:id>', methods=['GET','POST'])
@check_moderator
def item_delete(id):
    item = models.Item(g.conn, id=id)
    savedlist = item.get_list()
    if request.form.get('all'):
        item.delete_from_all()
    else:
        item.delete()
    g.conn.commit()
    if request.method == 'POST':
        return jsonify(success=True,listid=savedlist['id'])

    return redirect(url_for('.show_list', name=savedlist['name']))

@list_pages.route('/list/delete_and_flag/<int:id>', methods=['GET','POST'])
@check_moderator
def item_delete_and_flag(id, reason=None):
    item = models.Item(g.conn, id=id)
    savedlist = item.get_list()
    
    if request.method == 'POST':
        reason = request.form['reason']
    
    req = {
        'url': item['url'],
        'reporter': {
            'name': 'user@blocked.org.uk',
            'email': 'user@blocked.org.uk',
            },
        'message': '',
        'category': None,
        'report_type': ",".join(make_list(reason)),
        'date': get_timestamp(),
        'send_updates': 0,
        'allow_publish': 0,
        'allow_contact': 0,
        'auth': {
            'email': g.api.username,
            'signature': '',
            },
        'networks': ['ORG']
        }
    req['auth']['signature'] = g.api.sign(req,  ['url','date'])
    data = g.api.POST_JSON('ispreport/submit', req)
    if not data['success']:
        return jsonify(success=False, listid=savedlist['id'])
    
    # remove item from all lists
    item.delete_from_all()
    
    g.conn.commit()
    if request.method == 'POST':
        return jsonify(success=True,listid=savedlist['id'])

    return redirect(url_for('.show_list', name=savedlist['name']))    

@list_pages.route('/list/add', methods=['POST'])
@check_moderator
def item_add():
    f = request.form

    # search for URL, add to list if found

    savedlist = models.SavedList.select_one(g.conn, f['list_id'])
    newitem = models.Item(g.conn)
    newitem.update({
        'url': f['url'],
        'list_id': f['list_id'],
        'title': ''
        })
    newitem.store()
    g.conn.commit()
    return redirect(url_for('.show_list', name=savedlist['name']))

@list_pages.route('/list/<name>/export')
def export_list(name):
    import csv
    import tempfile
    try:
        savedlist = models.SavedList.select_one(g.conn, name=name)
    except NORM.exceptions.ObjectNotFound:
        abort(404)

    tmpfile = tempfile.SpooledTemporaryFile('w+')
    writer = csv.writer(tmpfile)
    writer.writerow(['#', "Title: " + savedlist['name']])
    writer.writerow(['#', "List saved from blocked.org.uk"])
    writer.writerow(['#', "URL: " + current_app.config['SITE_URL'] + url_for('.show_list', name=name) ])
    writer.writerow([])
    writer.writerow(['URL', 'Report URL'])
    if request.args.get('network'):
        it = savedlist.get_items_on_network(request.args['network'])
    else:
        it = savedlist.get_items()
    for item in it:
        writer.writerow([item['url'], current_app.config['SITE_URL']+ url_for('site.site', url=item['url']) ])

    tmpfile.flush()
    length = tmpfile.tell()
    tmpfile.seek(0)

    def returnvalue(*args):
        for line in tmpfile:
            yield line

    return Response(returnvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename='+name+'.csv',
        'Content-length': str(length)
        })
    


