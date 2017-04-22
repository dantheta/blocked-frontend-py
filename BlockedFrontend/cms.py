
import jinja2

from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort


cms_pages = Blueprint('cms', __name__,
    template_folder='templates/cms')
# static page routing
@cms_pages.route('/')
@cms_pages.route('/<page>')
def index(page='index'):
    if '/' in page:
        return "Invalid page name", 400
    try:
        return render_template(page + '.html')
    except jinja2.TemplateNotFound:
        raise
        abort(404)
    except Exception as exc:
        print repr(exc)
        abort(500)
