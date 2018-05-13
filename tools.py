
import os
import logging
import datetime

from flask import Flask

from BlockedFrontend.api import ApiClient, APIError
from BlockedFrontend.db import db_connect_single
from BlockedFrontend.utils import parse_timestamp
from BlockedFrontend.models import User
from NORM.exceptions import ObjectNotFound

conn = None

app = Flask("BlockedFrontend")

app.config.from_object('BlockedFrontend.default_settings')
if 'BLOCKEDFRONTEND_SETTINGS' in os.environ:
    app.config.from_envvar('BLOCKEDFRONTEND_SETTINGS')


api = ApiClient(
    app.config['API_EMAIL'],
    app.config['API_SECRET']
    )
if 'API' in app.config:
    api.API = app.config['API']

logging.basicConfig(
        level=logging.DEBUG if app.config['DEBUG'] else logging.INFO,
        datefmt="[%Y-%m-%dT%H:%M:%S]",
        format="%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s"
    )


@app.cli.command()
def run_submit():
    conn = db_connect_single()
    c = conn.cursor()
    c.execute("select distinct url from items \
               inner join savedlists on list_id = savedlists.id \
               where frontpage=true and blocked=true")
    for row in c:
        req = {
            'url': row['url'],
        }
        req['signature'] = api.sign(req, ['url'])
        data = api.POST('submit/url', req)
        logging.info("Submitted: %s, queued=%s", row['url'], data['queued'])
    c.close()
    conn.disconnect()


@app.cli.command()
def run_update():
    conn = db_connect_single()
    c = conn.cursor()
    c2 = conn.cursor()
    c.execute("select distinct url, last_checked from items inner join savedlists on list_id = savedlists.id \
               where frontpage=true \
               order by last_checked nulls first limit 500")

    # only evaluate based on test results from the last two weeks
    cutoff = datetime.datetime.now() - datetime.timedelta(14)
    for row in c:
        try:
            data = api.status_url(row['url'])

            # decide if site is still blocked, for the purposes of frontend list selection
            blocked = any([ (x['status'] == 'blocked' and parse_timestamp(x['status_timestamp']) > cutoff)
                            for x in data['results']])
            reported = len(data['reports']) > 0

            logging.info("Status: %s, blocked=%s, reported=%s", row['url'], blocked, reported)

            c2.execute("update items set blocked=%s, reported=%s, last_checked=now() where url=%s",
                       [ blocked, reported, row['url'] ])
        except APIError as exc:
            if 'UrlLookupError' in exc.args[0]:
                # URL no longer present on the backend?
                c2.execute("delete from items where url = %s", [row['url']])
    c.close()
    conn.commit()

@app.cli.command()
def create_admin():
    conn = db_connect_single()
    
    try:
        _ = User.select_one(conn, username='admin')
        app.logger.info("User admin already exists")
        return
    except ObjectNotFound:
        pass
        
    user = User(conn)
    user.update({
        'username': 'admin',
        'email':'admin@localhost',
        'user_type':'admin',
        })
    password = User.reset_password()
    user.store()
    conn.commit()
    app.logger.info("Created admin with password: %s", password)
    
