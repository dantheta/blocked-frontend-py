
from flask import current_app, request
from psycopg2.extras import DictCursor
import psycopg2
import psycopg2.pool

__all__ = ['db_connect_pool','cursor','db_disconnect']

POOL = None

def setup():
    global POOL
    POOL = psycopg2.pool.ThreadedConnectionPool(2, 12, current_app.config['DB'], cursor_factory=DictCursor)
    return

def db_connect_single():
    return psycopg2.connect(current_app.config['DB'], cursor_factory=DictCursor)
    
def db_connect_pool() :   
    return POOL.getconn()
    
def db_disconnect(conn):
    # TODO: transaction cleanup
    # current_app.logger.debug("Transaction status: %s", conn.get_transaction_status())
    if conn.get_transaction_status() in (2,3):
        current_app.logger.warn("Transaction status: %s", conn.get_transaction_status())

    POOL.putconn(conn)
    

def cursor(conn):
    c = conn.cursor(cursor_factory = DictCursor)
