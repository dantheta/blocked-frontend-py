
import random
import logging
import datetime

from flask import Blueprint, render_template, redirect, request, current_app, session, url_for
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

    blocks = [ process_block(blk) for blk 
        in urldata['results']
        if blk['status'] == 'blocked' 
        ]

    return render_template('unblock2.html',
        data=data,
        url=data['url'],
        blocks=blocks,
        domain=get_domain(data['url']), 
        )

@unblock_pages.route('/feedback')
def feedback():
    return render_template('feedback.html',
        url = request.args['url'],
        domain=get_domain(request.args['url'])
        )
        

def selectnext(searchdata, url):
    candidates = [ x['url'] for x in searchdata['sites']
        if x['last_reported'] is None and x['url'] != url]
    logging.info("Candidates found: %s", len(candidates))
    if len(candidates) > 0:
        return random.choice(candidates)

def nextsite(current_url):
    logging.info("Route: %s", session.get('route'))
    if session.get('route') == 'category':
        session['thanks'] = True # save under a rock for the /site page

        # get random/next site from category
        req = {
            'id': session['category'][0],
            'recurse': 1,
            'active': 1,
            'page': session['category'][1],
            }
        req['signature'] = request.api.sign(req, ['id'])
        searchdata = request.api.GET('category/sites/'+str(session['category'][0]), req)
        nextsite = selectnext(searchdata, current_url)
        if nextsite:
            return redirect(url_for('category.site', url=nextsite))

    elif session.get('route') == 'keyword':
        session['thanks'] = True # save under a rock for the /site page

        logging.info("running search: %s", session['keyword'])
        req = {'q': session['keyword'][0], 'page': session['keyword'][1]}
        req['signature'] = request.api.sign(req, ['q'])
        searchdata = request.api.GET('search/url', req)
        nextsite = selectnext(searchdata, current_url)
        if nextsite:
            return redirect(url_for('category.site', url=nextsite))

    elif session.get('route') == 'random':
        session['thanks'] = True # save under a rock for the /site page
        logging.info("Getting random site")
        data = request.api.GET('ispreport/candidates',{'count':1})
        return redirect(url_for('category.site', url=data['results'][0]))



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
        'allow_publish': 1 if form.get('allow_publish') else 0,
        'auth': {
            'email': request.api.username,
            'signature': '',
            }
        }
    if 'networks' in form:
        req['networks'] = make_list(form['networks'])
    req['auth']['signature'] = request.api.sign(req,  ['url','date'])

    if current_app.config['DUMMY']:
        # demo mode - don't really submit
        logging.warn("Dummy mode: not really submitting")
        data = {'verification_required':  False}
    else:
        data = request.api.POST_JSON('ispreport/submit', req)

    logging.info("Submission: %s", data)

    if 'ORG' in form.get('networks',[]):
        ret = nextsite(form['url'])
        if ret is not None:
            session['thanksmsg'] = 'flag'
            return ret
        return redirect('/thanks?f=1')
    else:
        if data['verification_required']:
            return redirect('/thanks?u=1&v=1')
        else:
            ret = nextsite(form['url'])
            if ret is not None:
                session['thanksmsg'] = 'unblock'
                return ret
                
            # default response
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
        'token': f['token'],
        'date': request.api.timestamp()
        }

    req['signature'] = request.api.sign(req, ['token','date'])

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

