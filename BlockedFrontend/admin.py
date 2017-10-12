

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session


admin_pages = Blueprint('admin', __name__, template_folder='templates/admin')

@admin_pages.route('/admin', methods=['GET'])
def admin():
    if not g.admin:
        return render_template('login.html')

    return render_template('admin.html')

@admin_pages.route('/admin', methods=['POST'])
def admin_post():
    if not (current_app.config.get('ADMIN_USER') and current_app.config.get('ADMIN_PASSWORD')):
        abort(403)

    if current_app.config['ADMIN_USER'] == request.form['username'] and \
        current_app.config['ADMIN_PASSWORD'] == request.form['password']:

        session['admin'] = True
        return redirect(url_for('.admin'))

    return render_template('login.html', message='Incorrect username or password')

@admin_pages.route('/admin/logout')
def logout():
    del session['admin']
    return redirect(url_for('.admin'))
