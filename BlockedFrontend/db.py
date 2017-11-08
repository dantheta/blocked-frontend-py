
from flask import current_app
import psycopg2

__all__ = ['db_connect']

def db_connect():
    return psycopg2.connect(current_app.config['DB'])
