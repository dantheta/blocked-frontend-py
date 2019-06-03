
import os
import logging
import datetime

from flask import Flask
import click

from BlockedFrontend.api import ApiClient, APIError
from BlockedFrontend.db import db_connect_single
from BlockedFrontend.utils import parse_timestamp
from BlockedFrontend.models import User,SavedList,Item
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
               where frontpage=true")
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
@click.argument('count', default=200)
def run_update(count=200):
    conn = db_connect_single()
    c = conn.cursor()
    c2 = conn.cursor()
    c.execute("select distinct url, last_checked from items inner join savedlists on list_id = savedlists.id \
               where public=true \
               order by last_checked nulls first limit "+ str(count))

    # only evaluate based on test results from the last two weeks
    for row in c:
        try:
            data = api.status_url(row['url'])

            # decide if site is still blocked, for the purposes of frontend list selection
            blocked = any([ (x['status'] == 'blocked') for x in data['results']])
            networks = [x['network_id'] for x in data['results'] if x['status'] == 'blocked' ]
            reported = len(data['reports']) > 0

            logging.info("Status: %s, blocked=%s, reported=%s, networks=%s", row['url'], blocked, reported, networks)

            c2.execute("update items set blocked=%s, reported=%s, networks=%s, last_checked=now() where url=%s",
                       [ blocked, reported, networks, row['url'] ])
        except APIError as exc:
            if 'UrlLookupError' in exc.args[0]:
                # URL no longer present on the backend?
                c2.execute("delete from items where url = %s", [row['url']])
        conn.commit()
    c.close()

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
    password = user.reset_password()
    user.store()
    conn.commit()
    app.logger.info("Created admin with password: %s", password)
    
@app.cli.command()
def create_mobile_inconsistency_lists():
    from NORM import Query
    conn = db_connect_single()

    lists = {}
    q = Query(conn, "select * from public.isps where isp_type = 'mobile' and show_results=1",[])
    for row in q:
        lists[ row['name'] ] = SavedList.find_or_create(conn,
                                                        ['name'],
                                                        {
                                                            'name': 'Mobile Inconsistency - blocked only on {0}'.format(row['name']),
                                                            'username': 'admin',
                                                            'public': False
                                                        })
        lists[row['name']].store()
        conn.commit()
        app.logger.info("Set up list: %s", lists[row['name']]['name'])

    q = Query(conn,
              """select urls.urlid, urls.url, urls.title, urls.last_reported,
                    count(*), array_agg(network_name) as network_name
                 from public.urls
                 inner join public.url_latest_status uls using (urlid)
                 inner join public.isps on isps.name = uls.network_name
                 where uls.status = 'blocked' and isp_type = 'mobile' and show_results=1 and urls.status = 'ok'
                 group by urlid, url, title, last_reported
                 having count(*) = 1""", [])
    for row in q:
        item = Item(conn)
        item.update({
            'url': row['url'],
            'title': row['title'],
            'blocked': True,
            'reported': True if row['last_reported'] else False,
            'list_id': lists[ row['network_name'][0] ]['id']
        })
        item.store()
    conn.commit()

    q = Query(conn,
              """select urls.urlid, urls.url, urls.title, urls.last_reported,
                    count(*) ct, array_agg(network_name) as network_name
                 from public.urls
                 inner join public.url_latest_status uls using (urlid)
                 inner join public.isps on isps.name = uls.network_name
                 where uls.status = 'blocked' and isp_type = 'mobile' and show_results=1 and urls.status = 'ok'
                 group by urlid, url, title, last_reported
                 having count(*) > 1""", [])

    for row in q:
        ls = SavedList.find_or_create(conn,
                                      ['name'],
                                      {
                                          'name': 'Mobile Inconsistency - blocked on {0} networks'.format(row['ct']),
                                          'username': 'admin',
                                          'public': False
                                      })
        ls.store()

        item = Item(conn)
        item.update({
            'url': row['url'],
            'title': row['title'],
            'blocked': True,
            'reported': True if row['last_reported'] else False,
            'list_id': ls['id']
        })
        item.store()
    conn.commit()
