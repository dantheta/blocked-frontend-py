
from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, Response

import logging

from .models import Url

class OSACase:
    @staticmethod
    def submit_url(url, **kwargs):
        # this behavior gets shared between the admin and public interface
        
        if current_app.config['DEBUG']:
            url = Url.select_one(g.conn, url=request.form['url'])
            return {
                'urlid': url.id
                }
        
        req = g.api.submit_url(url, **kwargs)
        return {
            'urlid': req['urlid']
        }

    @staticmethod
    def snapshot_url(url):
        import waybackpy

        if current_app.testing:
            import time
            time.sleep(1)
            return {'archive_url': "ok " + url, 'status': 'success'}
        
        call = waybackpy.WaybackMachineSaveAPI(url)
        try:
            archive_url = call.save()
            return {'archive_url': archive_url, 'status': 'success'}
        except waybackpy.exceptions.WaybackError as wbexc:
            logging.error("wayback status: %s", repr(wbexc))
            return {'status': 'error', 'error': repr(wbexc)}
        
        
        
