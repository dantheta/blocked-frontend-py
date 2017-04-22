
import os

from flask import Blueprint, render_template, redirect, request, abort
from utils import *

reload_blueprint = Blueprint('reload', __name__)

@reload_blueprint.route('/_refresh')
@reload_blueprint.route('/_refresh/<remote>')
def refresh(remote='github'):
    import subprocess
    if app.config['UPDATE_PASSWORD'] != request.args['key']:
        abort(403)

    proc=subprocess.Popen(['git','pull',remote,'master'],
        cwd=os.path.dirname(os.path.abspath(sys.argv[0])),
        )
    proc.wait()
    return "OK"
