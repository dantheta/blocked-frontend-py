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

import NORM
from NORM.exceptions import ObjectNotFound,ObjectExists

registry_pages = Blueprint('registry', __name__, template_folder='templates/registry')


@registry_pages.route('/')
@registry_pages.route('/suspensions')
@registry_pages.route('/suspensions/<int:page>')
def registry_suspensions(page=1):
    pagesize = 25
    offset = (page-1)*pagesize

    res = NORM.Query(g.conn, "select count(*), max(created) from public.registry_suspension_urls", [])
    row = res.fetchone()
    count = row[0]
    pagecount = get_pagecount(count, pagesize)
    newdate = row[1]

    sql = "select * from public.registry_suspension_urls limit {0} offset {1}".format(pagesize, offset)
    print sql
    suspensions = NORM.Query(g.conn, sql, [])
    g.conn.commit()
    return render_template('registry_suspensions.html',
                           suspensions=suspensions,
                           page=page,
                           count=count,
                           newdate=newdate,
                           pagesize=pagesize,
                           pagecount=pagecount)
