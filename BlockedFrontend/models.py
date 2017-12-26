
import itertools
import psycopg2.extensions
from psycopg2.extras import DictCursor

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

from NORM import DBObject
from NORM.exceptions import ObjectNotFound


class SavedList(DBObject):
    TABLE = 'savedlists'
    FIELDS = [
            'username',
            'name',
            'public',
            'frontpage'
            ]

    def get_items(self, **kw):
        return Item.select(self.conn, list_id=self['id'], _orderby='url', **kw)

    def count_items(self):
        return Item.count(self.conn, list_id=self['id'])


class Item(DBObject):
    TABLE = 'items'
    FIELDS = [
            'list_id',
            'url',
            'title',
            'blocked',
            'reported',
            'last_checked',
            ]

    def get_list(self):
        return SavedList.select_one(self.conn, self['list_id'])

    @classmethod
    def get_frontpage_random(cls, conn):
        c = conn.cursor(cursor_factory = DictCursor)
        c.execute("""select items.* 
            from items 
            inner join savedlists on list_id = savedlists.id
            where frontpage = true and blocked = true and reported = false
            order by random()""")
        for row in c:
            yield cls(conn, data=row)
        c.close()

    @classmethod
    def get_public_list_item(cls, conn, url):
        c = conn.cursor(cursor_factory = DictCursor)
        c.execute("""select items.*
                     from items
                     inner join savedlists on list_id = savedlists.id
                     where frontpage = true and url = %s""",
                     [url])
        row = c.fetchone()
        if row is None:
            raise ObjectNotFound
        c.close()
        return cls(conn, data=row)

class CourtJudgment(DBObject):
    TABLE = 'court_judgments'
    FIELDS = ['name','url','date']

    @classmethod
    def view_summary(cls, conn):
        """Yields groupby iterator, of judgment_id->courtorders"""
        c = conn.cursor(cursor_factory = DictCursor)
        c.execute("""select j.id, j.name, j.date, j.url, o.id as order_id, o.name as order_name, o.url as order_url, o.network_name, o.date as order_date
            from court_judgments j
            left join court_orders o on judgment_id = j.id
            order by j.name, o.name""")
        for row in itertools.groupby(c, lambda row: {x: row[x] for x in ['id','name','date','url']}):
            yield row
        c.close()

    def get_court_orders(self):
        for obj in CourtOrder.select(self.conn, judgment_id = self['id'], _orderby='name'):
            yield obj


class CourtOrder(DBObject):
    TABLE = 'court_orders'
    FIELDS = ['name','network_name','judgment_id','date','url']

class CourtOrderURL(DBObject):
    TABLE = 'court_order_urls'
    FIELDS = ['court_order_id','urlid']
