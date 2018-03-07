
import itertools
import psycopg2.extensions
from psycopg2.extras import DictCursor

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

from NORM import DBObject,Query
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
    FIELDS = ['name',
              'judgment_url',
              'url',
              'date',
              'citation',
              'case_number',
              'restriction_type',
              'instruction_type',
              'jurisdiction',
              'power_id',
              'court_authority',
              'injunction_obtained_by',
              'injunction_obtained_by_url',
              'injunction_represented_by',
              'other_docs',
              'sites_description',
              ]

    def get_court_orders(self):
        return CourtOrder.select(self.conn, judgment_id=self['id'], _orderby='network_name')

    def get_court_order_networks(self):
        return [x['network_name'] for x in self.get_court_orders()]

    def get_court_orders_by_network(self):
        """Returns a dictionary of network: court order"""
        return {obj['network_name']: obj for obj in self.get_court_orders()}

    def get_urls(self):
        return CourtJudgmentURL.select(self.conn, judgment_id=self['id'], _orderby='url')

    def get_grouped_urls(self):
        q = Query(self.conn, """select u.*, g.name as group_name
            from court_judgment_urls u
            left join court_judgment_url_groups g on g.id = u.group_id
            where u.judgment_id = %s
            order by g.name, u.url
            """, [self['id']])
        urliter = (CourtJudgmentURL(self.conn, data=row) for row in q)
        return itertools.groupby(urliter, lambda row: row['group_name'])

    def get_grouped_urls_with_expiry(self):
        """Uses view onto backend's URLs table"""
        q = Query(self.conn, """select u.*, g.name as group_name, pu.whois_expiry
            from court_judgment_urls u
            left join urls pu on pu.url = u.url
            left join court_judgment_url_groups g on g.id = u.group_id
            where u.judgment_id = %s
            order by g.name, u.url
            """, [self['id']])
        urliter = (CourtJudgmentURL(self.conn, data=row) for row in q)
        return itertools.groupby(urliter, lambda row: row['group_name'])

    def get_url_groups(self):
        return CourtJudgmentURLGroup.select(self.conn, judgment_id=self['id'], _orderby='name')

    def get_power(self):
        if self['power_id'] is None:
            return None
        return CourtPowers.select_one(self.conn, self['power_id'])

class CourtJudgmentURL(DBObject):
    FIELDS = ['judgment_id','url', 'group_id']
    TABLE = 'court_judgment_urls'

    def get_court_judgment(self):
        return CourtJudgment(self.conn, id=self['judgment_id'])

class CourtJudgmentURLGroup(DBObject):
    TABLE = 'court_judgment_url_groups'
    FIELDS = ['name','judgment_id']

class CourtOrder(DBObject):
    TABLE = 'court_orders'
    FIELDS = ['judgment_id', 'network_name','url','date','expiry_date']

class CourtPowers(DBObject):
    TABLE = 'court_powers'
    FIELDS = ['name','legislation']

