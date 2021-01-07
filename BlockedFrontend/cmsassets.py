
from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, Response


cms_assets = Blueprint('cmsassets',
                      __name__,
                      static_folder='static')


@cms_assets.route('/cms/assets/<path:path>')
def cms_asset(path):
    if current_app.config['REMOTE_TYPE'] != 'cockpit':
        abort(500)

    try:
        req = g.remote.get_asset('/'+path)
    except ValueError as exc:
        abort(exc.args[0])
    return Response(req.iter_content(1024), req.status_code,
                    {'Content-type': req.headers['Content-type'],
                     'Content-length': req.headers['Content-length']})