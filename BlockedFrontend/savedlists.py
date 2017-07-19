import re
import logging
import psycopg2

from flask import Blueprint, render_template, redirect, request, \
    jsonify, g, url_for, session, current_app

from utils import *

import models


list_pages = Blueprint('list', __name__)

@list_pages.before_request
def setup_db():
    request.conn = psycopg2.connect(current_app.config['DB'])


@list_pages.route('/list', methods=['POST'])
def create_list():
    """Create a saved list"""
    f = request.form

    newlist = models.SavedList(request.conn)
    newlist.update({
        'name': f['name'],
        'username': f['username'],
        })
    newlist.store()
    n = 0
    page = 0
    while True:

        logging.info("Search page: %d", page)
        data = request.api.search_url(f['search'], page)

        for site in data['sites']:
            newitem = models.Item(request.conn)
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

    request.conn.commit()

    return redirect(url_for('.show_list', name=f['name']))


@list_pages.route('/list/<name>', methods=['GET'])
@list_pages.route('/list/<name>/<int:page>', methods=['GET'])
def show_list(name, page=0):
    pagesize=20
    savedlist = models.SavedList.select_one(request.conn, name=name)
    itemcount = savedlist.count_items()
    items = savedlist.get_items(_limit=(pagesize, page*pagesize))

    return render_template('show_list.html',
            savedlist = savedlist,
            itemcount = itemcount,
            page = page,
            pagesize = pagesize,
            items = items
            )


@list_pages.route('/list/delete/<int:id>')
def item_delete(id):
    item = models.Item(request.conn, id=id)
    savedlist = item.get_list()
    item.delete()
    request.conn.commit()
    return redirect(url_for('.show_list', name=savedlist['name']))

@list_pages.route('/list/add', methods=['POST'])
def item_add():
    f = request.form

    # search for URL, add to list if found

    savedlist = models.SavedList.select_one(request.conn, f['list_id'])
    newitem = models.Item(request.conn)
    newitem.update({
        'url': f['url'],
        'list_id': f['list_id'],
        'title': ''
        })
    newitem.store()
    request.conn.commit()
    return redirect(url_for('.show_list', name=savedlist['name']))
