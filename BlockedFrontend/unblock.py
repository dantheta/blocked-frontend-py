
import logging
import datetime

from flask import Blueprint, render_template, redirect, request, current_app, session
from utils import *


unblock_pages = Blueprint('unblock', __name__)


@unblock_pages.route('/unblock')
def unblock():
    url = request.args['url']
    return render_template('unblock.html',
        url=url,
        domain=get_domain(url),
        name=session.get('name',''),
        email=session.get('email','')
        )

@unblock_pages.route('/unblock2', methods=['POST','GET'])
def unblock2():
    def process_block(block):
        block['last_blocked_timestamp'] = parse_timestamp(block['last_blocked_timestamp'])
        block['last_report_timestamp'] = parse_timestamp(block['last_report_timestamp'])
        return block

    if request.method == 'POST':
        data = request.form
        for k in 'name','email':
            session[k] = data[k]
    else:
        data = request.args.copy()
        data['name'] = session['name']
        data['email'] = session['email']

    req = {
        'url': data['url'],
        }

    req['signature'] = request.api.sign(req, ['url'])
    urldata = request.api.GET('status/url', req)
    logging.info("urldata: %s", urldata)

    cutoff_time = datetime.datetime.now() - datetime.timedelta(current_app.config['BLOCKED_CUTOFF_DAYS'])
    blocks = [ process_block(blk) for blk 
        in urldata['results']
        if blk['status'] == 'blocked' 
            #and parse_timestamp(blk['last_blocked_timestamp']) >= cutoff_time
        ]

    valid_blocks = sum([
        1 if blk['last_blocked_timestamp'] >= cutoff_time else 0
        for blk 
        in blocks
        ])

    return render_template('unblock2.html',
        data=data,
        url=data['url'],
        cutoff_time = cutoff_time,
        blocks=blocks,
        valid_blocks=valid_blocks,
        domain=get_domain(data['url']), 
        )

@unblock_pages.route('/feedback')
def feedback():
    return render_template('feedback.html',
        url = request.args['url'],
        domain=get_domain(request.args['url'])
        )
        

@unblock_pages.route('/submit-unblock', methods=['POST'])
def submit_unblock():
    if not request.form.get('checkedsite'):
        return None #TODO: message template
    form = request.form
    req = {
        'url': form['url'],
        'reporter': {
            'name': form['name'],
            'email': form['email'],
            },
        'message': form['message'],
        'report_type': ",".join(make_list(form['report_type'])),
        'date': get_timestamp(),
        'send_updates': 1 if form.get('send_updates') else 0,
        'auth': {
            'email': request.api.username,
            'signature': '',
            }
        }
    if 'networks' in form:
        req['networks'] = make_list(form['networks'])
    req['auth']['signature'] = request.api.sign(req,  ['url','date'])
    data = request.api.POST_JSON('ispreport/submit', req)
    if 'ORG' in form.get('networks',[]):
        return redirect('/thanks?f=1')
    else:
        if data['verification_required']:
            return redirect('/thanks?u=1&v=1')
        else:
            return redirect('/thanks?u=1&v=0')

@unblock_pages.route('/thanks')
def thanks():
    return render_template('thanks.html',
        u=request.args.get('u'),
        f=request.args.get('f'),
        v=request.args.get('v'),
        )

@unblock_pages.route('/verify')
def verify():
    f = request.args
    req = {
        'email': f['email'],
        'token': f['token'],
        'date': request.api.get_timestamp()
        }

    req['auth'] = request.api.sign(req, ['token','date'])

    data = request.api.POST('verify/email', req)
    if data['success'] == False:
        return render_template('message.html',
            message = "We have been unable to locate a user account with this link.  <br />Please check that you have the correct verification link from your email.",
            title = 'Email validation',
            )
    else:
        return redirect('/thanks?u=1&v=0')

@unblock_pages.route('/recheck')
def recheck():
    url = request.args['url']
    req = {
        'url': url,
        }
    req['signature'] = request.api.sign(req, ['url'])
    urldata = request.api.POST('submit/url', req)
    logging.info("urldata: %s", urldata)
    return "OK"

