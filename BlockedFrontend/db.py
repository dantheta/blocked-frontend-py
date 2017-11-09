
from flask import current_app
from psycopg2.extras import DictCursor
import psycopg2

__all__ = ['db_connect','cursor']

def db_connect():
    return psycopg2.connect(current_app.config['DB'], cursor_factory=DictCursor)

def cursor(conn):
    c = conn.cursor(cursor_factory = DictCursor)
