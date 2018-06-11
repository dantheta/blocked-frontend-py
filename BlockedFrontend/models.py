
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

class User(DBObject):
    TABLE = 'users'
    FIELDS = ['username',
              'email',
              'password',
              'user_type',
              'enabled',
              ]
    PASSWORD_LENGTH=12
    
    @staticmethod
    def _encode(s):
        if isinstance(s, unicode):
            return s.encode('utf8')
        else:
            return s
    
    def check_password(self, testpass):
        import bcrypt
        m = self._encode(testpass)
        if bcrypt.hashpw(self._encode(testpass), self._encode(self['password'])) == self._encode(self['password']):
            return True
            
    def set_password(self, password):
        import bcrypt
        salt = bcrypt.gensalt()
        self['password'] = bcrypt.hashpw(self._encode(password), salt)
        
    def reset_password(self, length=PASSWORD_LENGTH):
        newpass = self.random_password(length)
        self.set_password(newpass)
        return newpass
        
    @classmethod
    def authenticate(klass, conn, username, password):
        user = klass.select_one(conn, username=username, enabled=True)
        if user.check_password(password):
            return user
        
    @staticmethod
    def random_password(length=PASSWORD_LENGTH):
        import random, string
        
        return "".join(random.sample(string.letters+string.digits, length))

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

    def get_urls_with_status(self, region):
        q = Query(self.conn, """select u.url, count(distinct uls.id) as block_count
            from court_judgment_urls u
            left join urls on u.url = urls.url and urls.url ~* '^https?://[^/]+$' and urls.status = 'ok'
            left join url_latest_status uls on urls.urlid = uls.urlid
                and uls.status = 'blocked' and uls.blocktype = 'COPYRIGHT'
            left join isps on isps.name = uls.network_name and isps.regions && %s::varchar[]
            where u.judgment_id = %s
            group by u.url
            order by u.url
            """, [self['id'], [region]])
        return q

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
        q = Query(self.conn, """select u.*, g.name as group_name, pu.whois_expiry, cjuf.id as flag_id,
            (select count(*) from court_judgment_url_flag_history fh where fh.urlid = u.id) 
            + (case when cjuf.id is not null then 1 else 0 end) as flag_count,
            reason
            from court_judgment_urls u
            left join urls pu on pu.url = u.url
            left join court_judgment_url_groups g on g.id = u.group_id
            left join court_judgment_url_flags cjuf on u.id = cjuf.urlid
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
        
    def get_flag(self):
        return CourtJudgmentURLFlag.select_one(self.conn, urlid=self['id'])
        

class CourtJudgmentURLGroup(DBObject):
    TABLE = 'court_judgment_url_groups'
    FIELDS = ['name','judgment_id']

class CourtOrder(DBObject):
    TABLE = 'court_orders'
    FIELDS = ['judgment_id', 'network_name','url','date','expiry_date']

class CourtPowers(DBObject):
    TABLE = 'court_powers'
    FIELDS = ['name','legislation']

class CourtJudgmentURLFlag(DBObject):
    TABLE = 'court_judgment_url_flags'
    FIELDS = ['reason','date_observed','abusetype','description','urlid']
    
    def get_url(self):
        return CourtJudgmentUrl(self.conn, self['urlid'])
        

class Test(DBObject):
    TABLE = 'tests.test_cases'
    FIELDS = [
        'name',
        'status',
        'tags',
        'filter',
        'sent',
        'total',
        'received',
        'isps',
        'check_interval',
        'last_check',
        'repeat_interval',
        'last_run',
        'batch_size',
        'last_id',
    ]
