
from flask import Blueprint, render_template, redirect, request, \
    g, url_for, abort, config, current_app, session, Response


class OSACase:
    @staticmethod
    def submit_url(self, url, **kwargs):
        # this behavior gets shared between the admin and public interface
        
        req = g.api.submit_url(url, **kwargs)
        return {
            'urlid': req['urlid']
        }
