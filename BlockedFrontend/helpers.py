
from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, Response

from .models import Url

class OSACase:
    @staticmethod
    def submit_url(self, url, **kwargs):
        # this behavior gets shared between the admin and public interface
        
        if config.DEBUG:
            url = Url.select_one(g.conn, url=request.form['url'])
            return {
                'urlid': url.id
                }
        
        req = g.api.submit_url(url, **kwargs)
        return {
            'urlid': req['urlid']
        }
