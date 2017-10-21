

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session

from models import *
from auth import *

admin_pages = Blueprint('admin', __name__, template_folder='templates/admin')

@admin_pages.before_request
def setup_db():
    request.conn = psycopg2.connect(current_app.config['DB'])

@admin_pages.route('/control', methods=['GET'])
def admin():
    if not g.admin:
        return render_template('login.html')

    return render_template('admin.html')

@admin_pages.route('/control', methods=['POST'])
def admin_post():
    if not (current_app.config.get('ADMIN_USER') and current_app.config.get('ADMIN_PASSWORD')):
        abort(403)

    if current_app.config['ADMIN_USER'] == request.form['username'] and \
        current_app.config['ADMIN_PASSWORD'] == request.form['password']:

        session['admin'] = True
        return redirect(url_for('.admin'))

    return render_template('login.html', message='Incorrect username or password')

@admin_pages.route('/control/logout')
@check_admin
def logout():
    del session['admin']
    return redirect(url_for('.admin'))


@admin_pages.route('/control/savedlists')
@check_admin
def savedlists():
    return render_template('listindex.html',
        lists=SavedList.select(request.conn, _orderby='name')
        )

@admin_pages.route('/control/savedlists/delete/<int:id>')
@check_admin
def savedlist_delete(id):
    savedlist = SavedList(request.conn, id=id)
    savedlist.delete()
    request.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/show/<int:id>')
@check_admin
def savedlist_show(id):
    savedlist = SavedList(request.conn, id=id)
    savedlist['public'] = True
    savedlist.store()
    request.conn.commit()
    return redirect(url_for('.savedlists'))

@admin_pages.route('/control/savedlists/hide/<int:id>')
@check_admin
def savedlist_hide(id):
    savedlist = SavedList(request.conn, id=id)
    savedlist['public'] = False
    savedlist.store()
    request.conn.commit()
    return redirect(url_for('.savedlists'))
