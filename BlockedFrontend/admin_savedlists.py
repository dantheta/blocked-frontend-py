
import os
import re
import psycopg2
import logging
import datetime
import itertools

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from models import *
from auth import *
from utils import *
from resources import *
from db import *

from NORM.exceptions import ObjectNotFound,ObjectExists

admin_savedlist_pages = Blueprint('admin_savedlists', __name__, template_folder='templates/admin')


@admin_savedlist_pages.route('/control/savedlists')
@check_admin
def savedlists():
    return render_template('listindex.html',
                           lists=SavedList.select(g.conn, _orderby='name')
                           )


@admin_savedlist_pages.route('/control/savedlists/add')
@check_admin
def savedlist_add():
    return render_template('list_add.html')


@admin_savedlist_pages.route('/control/savedlists/create', methods=['POST'])
@check_admin
def savedlist_create():
    f = request.form

    savedlist = SavedList(g.conn)
    savedlist.update({
        'username': session.get('username','admin'),
        'name': f['name'],
        'public': False,
        'frontpage': False
    })
    savedlist.store()

    if 'upload' in request.files and request.files['upload'].filename:
        for line in request.files['upload'].stream:
            if not line.strip():
                continue

            url = normalize_url(line.strip())

            try:
                urlobj = Url.select_one(g.conn, url=url)
            except ObjectNotFound:
                urlobj = {}


            item = Item(g.conn)
            item.update({
                'list_id': savedlist.id,
                'url': url,
                'title': urlobj.get('title')
            })
            item.store()

    flash("List {0} created".format(f['name']))
    g.conn.commit()
    return redirect(url_for('.savedlists'))


@admin_savedlist_pages.route('/control/savedlists/delete/<int:id>')
@check_admin
def savedlist_delete(id):
    savedlist = SavedList(g.conn, id=id)
    savedlist.delete()
    g.conn.commit()
    return redirect(url_for('.savedlists'))


@admin_savedlist_pages.route('/control/savedlists/show/<int:id>')
@check_admin
def savedlist_show(id):
    savedlist = SavedList(g.conn, id=id)
    savedlist['public'] = True
    savedlist.store()
    g.conn.commit()
    return redirect(url_for('.savedlists'))


@admin_savedlist_pages.route('/control/savedlists/hide/<int:id>')
@check_admin
def savedlist_hide(id):
    savedlist = SavedList(g.conn, id=id)
    savedlist['public'] = False
    savedlist.store()
    g.conn.commit()
    return redirect(url_for('.savedlists'))


@admin_savedlist_pages.route('/control/savedlists/<int:id>/frontpage/<int:state>')
@check_admin
def savedlist_frontpage(id, state):
    savedlist = SavedList(g.conn, id=id)
    savedlist['frontpage'] = bool(state)
    savedlist.store()
    g.conn.commit()
    return redirect(url_for('.savedlists'))


@admin_savedlist_pages.route('/control/savedlists/merge', methods=['POST'])
@check_admin
def savedlist_merge():
    ids = request.form.getlist('merge')
    logging.info("Merge: %s", ids)
    if not isinstance(ids, list):
        abort(500)
    ids.sort()
    first = SavedList(g.conn, id=ids[0])
    c = g.conn.cursor()
    for id in ids[1:]:
        # try to update in bulk
        c.execute("savepoint point1")
        try:
            c.execute("update items set list_id = %s where list_id = %s",
                      [first['id'], id])
        except psycopg2.IntegrityError:
            c.execute("rollback to point1")
        else:
            # bulk move succeeded, onto the next list
            SavedList(g.conn, id=id).delete()
            continue

        # otherwise, move one-by-one and delete on duplicate
        for item in Item.select(g.conn, list_id = id):
            try:
                c.execute("savepoint point1")
                item['list_id'] = first['id']
                item.store()
            except ObjectExists:
                c.execute("rollback to point1")
                item.delete()
        SavedList(g.conn, id=id).delete()
    g.conn.commit()
    flash("Selected lists have been merged into '{}'".format(first['name']))
    return redirect(url_for('.savedlists'))
