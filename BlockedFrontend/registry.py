
from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from models import *
from utils import *

import NORM
from NORM.exceptions import ObjectNotFound,ObjectExists

registry_pages = Blueprint('registry', __name__, template_folder='templates/registry')


@registry_pages.route('/')
@registry_pages.route('/seizures')
@registry_pages.route('/seizures/<int:page>')
def registry_seizures(page=1):
    g.remote_content = g.remote.get_content('registry_seizures')

    pagesize = 25
    offset = (page-1)*pagesize

    res = NORM.Query(g.conn,
                     "select count(distinct urlid), max(created) from public.url_latest_status "
                     "left join public.url_hierarchy h using (urlid) "
                     "where blocktype = 'SUSPENSION' and (parent_urlid = h.urlid or h.urlid is null) ",
                     [])
    row = res.fetchone()
    (count, newdate) = row
    newdate = newdate.date()
    pagecount = get_pagecount(count, pagesize)

    sql = ("select url, max(category) as category, min(uls.created)::date created, max(uls.last_blocked) last_blocked, string_agg(isps.description, ';') isp_description "
           "from public.url_latest_status uls "
           "inner join urls using (urlid) "
           "inner join isps on network_name = isps.name "
           "left join public.url_hierarchy h using (urlid) "
           "where blocktype = 'SUSPENSION' and (parent_urlid = h.urlid or h.urlid is null) "
           "group by url "
           "order by created desc, url "
           "limit {0} offset {1}".format(pagesize, offset))
    q = NORM.Query(g.conn, sql, [])
    g.conn.commit()

    return render_template("registry_seizures.html",
                           seizures=q,
                           page=page,
                           count=count,
                           pagecount=pagecount,
                           pagesize=pagesize,
                           newdate=newdate)
