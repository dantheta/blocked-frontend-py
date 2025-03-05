from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, flash, jsonify, Response

from .models import *
from .auth import *
from .utils import *
from .resources import *
from .db import *

from NORM.exceptions import ObjectNotFound,ObjectExists

#################
#
#  Online safety act case administration
#
#################

admin_osa_pages = Blueprint('admin_osa', __name__)

@admin_osa_pages.route('/control/osa')
@check_moderator
def admin_osa_index():
	objlist = OSACase.select_with_urls(g.conn, _orderby='id desc')
	return render_template('osa/osa_index.html',
                            cases=objlist)

@admin_osa_pages.route('/control/osa/add')
@admin_osa_pages.route('/control/osa/edit/<int:id>')
@check_moderator
def admin_osa_edit(id=None):
    pass

@admin_osa_pages.route('/control/osa/update')
@admin_osa_pages.route('/control/osa/update/<int:id>')
@check_moderator
def admin_osa_update(id=None):
    pass

@admin_osa_pages.route('/control/osa/view/<int:id>')
@check_moderator
def admin_osa_view(id=None):
    pass

@admin_osa_pages.route('/control/osa/delete/<int:id>')
@check_moderator
def admin_osa_delete(id=None):
    pass
