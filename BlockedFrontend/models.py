
import itertools
import psycopg2.extensions
from psycopg2.extras import DictCursor

import flask

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

    def get_items(self, status=None, domain=None, **kw):
        if status == 'unblocked':
            kw.update({'blocked': False})
        elif status == 'blocked':
            kw.update({'blocked': True})
        if domain:
            kw.update({'url': ('~*', '://[^/]+\.{0}(/|$)'.format(domain))})
        return Item.select(self.conn, list_id=self['id'], _orderby='url', **kw)

    def get_items_on_network(self, network, status=None, domain=None, _limit=None, exclude=None):
        args = [network, self['id']]
        if status == 'unblocked':
            args.append(False)
        elif status == 'blocked':
            args.append(True)

        sql = flask.render_template_string(
                 """select distinct items.*
                    from items
                    inner join public.urls using (url)
                    inner join public.url_latest_status uls on uls.urlid = urls.urlid and uls.network_name {{ network_op|safe }} %s and uls.status = 'blocked'
                    where list_id = %s 
                    {% if status %}
                        and items.blocked = %s
                    {% endif %}
                    {% if domain %}
                        and items.url ~* '://[^/]+\.{{domain}}(/|$)'
                    {% endif %}
                    order by url
                    {% if limit %}
                        limit {{ limit.0|int }} offset {{ limit.1|int }}
                    {% endif %}""",
                 network_op = "<>" if exclude else "=",
                 status = status,
                 domain=domain,
                 limit=_limit)

        q = Query(self.conn, sql, args)
        for row in q:
            yield Item(self.conn, data=row)

        q.close()

    def count_items(self, status=None, domain=None):
        kw = {}
        if status == 'unblocked':
            kw.update({'blocked': False})
        elif status == 'blocked':
            kw.update({'blocked': True})
        if domain:
            kw.update({'url': ('~*', '://[^/]+\.{0}(/|$)'.format(domain))})
        return Item.count(self.conn, list_id=self['id'], **kw)

    def count_items_on_network(self, network, status=None, domain=None, exclude=None):

        args = [network, self['id']]
        if status == 'unblocked':
            args.append(False)
        elif status == 'blocked':
            args.append(True)

        sql = flask.render_template_string(
                 """select count(distinct items.id) ct
                    from items
                    inner join public.urls using (url)
                    inner join public.url_latest_status uls on uls.urlid = urls.urlid and uls.network_name {{ network_op|safe }} %s and uls.status = 'blocked'
                    where list_id = %s 
                    {% if status %}
                        and items.blocked = %s
                    {% endif %}
                    {% if domain %}
                        and items.url ~* '://[^/]+\.{{domain}}(/|$)'
                    {% endif %}
                    """,
                 network_op = "<>" if exclude else "=",
                 status = status,
                 domain=domain)

        q = Query(self.conn, sql, args)
        row = q.fetchone()
        q.close()
        return row['ct']




    @classmethod
    def select_with_totals(cls, conn, public, network=None, exclude=False):
        args = [public]
        crit = ''
        if network:
            if isinstance(network, list):
                args.extend(network)
                crit = "and uls.network_name in ({0})".format(",".join( ["%s"] * len(network) ) )
            else:
                args.append(network)
                crit = 'and uls.network_name {0} %s'.format('<>' if exclude else '=')

        q = Query(conn,
                  """select savedlists.id, savedlists.name, savedlists.username, savedlists.public, savedlists.frontpage,
                         count(distinct items.id) item_count,
                         count(distinct isp_reports.urlid) reported_count,
                         sum(case when uls.first_blocked is not null then 1 else 0 end) block_count, -- historical blocks
                         sum(case when uls.first_blocked is not null and (isp_reports.unblocked = 1 or isp_reports.status = 'unblocked') then 1 else 0 end) unblock_count,
                         sum(case when uls.status = 'blocked' then 1 else 0 end) active_block_count, -- active blocks
                         count( distinct case when uls.status = 'blocked' then items.id else null end) item_block_count -- active blocks
                     from savedlists
                     left join items on list_id = savedlists.id
                     left join urls using (url)
                     left join public.url_latest_status uls on uls.urlid = urls.urlid
                     left join public.isp_reports_sent isp_reports on isp_reports.urlid = uls.urlid and uls.network_name = isp_reports.network_name
                     where savedlists.public = %s {0}
                     group by savedlists.id, savedlists.name
                     order by savedlists.name""".format(crit),
                     args)

        for row in q:
            yield cls(conn, data=row)
        q.close()


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

    def delete_from_all(self):
        for delitem in Item.select(self.conn, url=self['url']):
            delitem.delete()

    @classmethod
    def get_frontpage_random(cls, conn, exclude_networks=''):
        c = conn.cursor(cursor_factory = DictCursor)
        c.execute("""select items.* 
            from items 
            inner join savedlists on list_id = savedlists.id
            where frontpage = true and blocked = true and reported = false and networks <> %s and networks is not null
            order by random()""",
            [exclude_networks])
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
              'rightsholder_id',
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

    def get_rightsholder(self):
        if self['rightsholder_id']:
            return Rightsholder(self.conn, self['rightsholder_id'])

    def get_urls_with_status(self, region):
        q = Query(self.conn, """select u.url, count(distinct url_latest_status_id) as block_count
            from court_judgment_urls u
            left join active_copyright_blocks urls on u.url = urls.url and regions && %s::varchar[]
            where u.judgment_id = %s
            group by u.url
            order by u.url
            """, [ [region], self['id']])
        return q

    def get_groups_with_status(self, region):
        q = Query(self.conn, """select 
                case when cjug.name is null then '(unclassified)' else cjug.name end as name, 
                count(distinct url_latest_status_id) as block_count
            from court_judgment_urls u
            left join court_judgment_url_groups cjug on cjug.id = u.group_id
            left join active_copyright_blocks urls on u.url = urls.url and regions && %s::varchar[]
            where u.judgment_id = %s 
            group by 
                case when cjug.name is null then '(unclassified)' else cjug.name end
            order by 
                case when cjug.name is null then '(unclassified)' else cjug.name end
            """, [ [region], self['id']])
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

    def get_grouped_urls_with_status(self, region):
        q = Query(self.conn, """select 
                case when cjug.name is null then '(unclassified)' else cjug.name end as group_name, 
                u.url,
                count(distinct url_latest_status_id) as block_count
            from court_judgment_urls u
            left join court_judgment_url_groups cjug on cjug.id = u.group_id
            left join active_copyright_blocks urls on u.url = urls.url and regions && %s::varchar[]
            where u.judgment_id = %s 
            group by 
                case when cjug.name is null then '(unclassified)' else cjug.name end,
                u.url
            order by 
                case when cjug.name is null then '(unclassified)' else cjug.name end,
                u.url
            """, [ [region], self['id']])
        urliter = (CourtJudgmentURL(self.conn, data=row) for row in q)
        return itertools.groupby(urliter, lambda row: row['group_name'])

    def get_grouped_urls_with_expiry(self):
        """Uses view onto backend's URLs table"""
        q = Query(self.conn, """select u.*, g.name as group_name, pu.whois_expiry, cjuf.id as flag_id,
            (select count(*) from court_judgment_url_flag_history fh where fh.judgment_url_id = u.id) 
            + (case when cjuf.id is not null then 1 else 0 end) as flag_count,
            reason
            from court_judgment_urls u
            left join urls pu on pu.url = u.url
            left join court_judgment_url_groups g on g.id = u.group_id
            left join court_judgment_url_flags cjuf on u.id = cjuf.judgment_url_id
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

    def get_report(self, region):
        q = Query(self.conn, """
                select distinct 
                    judgment_id, judgment_name, judgment_date, wiki_url, judgment_url, citation, judgment_sites_description,
                     reason as error_status, abusetype, first_blocked, last_blocked, networks,
                    case when url_group_name is null then '(Unclassified)' else url_group_name end url_group_name,
                    case when networks = '{NULL}' then NULL else url end url 
                from active_court_blocks 
                where (region = %s or region is null) AND judgment_id = %s
                """,
              [region, self['id']]
              )
        return q


class CourtJudgmentURL(DBObject):
    FIELDS = ['judgment_id','url', 'group_id']
    TABLE = 'court_judgment_urls'

    def get_court_judgment(self):
        return CourtJudgment(self.conn, id=self['judgment_id'])
        
    def get_flag(self):
        return CourtJudgmentURLFlag.select_one(self.conn, judgment_url_id=self['id'])

    def get_url(self):
        try:
            url = Url.select_one(self.conn, url=self['url'])
            return url
        except ObjectNotFound:
            return None

    def get_urlid(self):
        url = self.get_url()
        if url is None:
            return None
        return url['urlid']
        

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
        

class Tags(DBObject):
    TABLE = 'public.tags'
    FIELDS = ['name','description','type']
    
    

class Url(DBObject):
    TABLE = 'urls'
    UPDATABLE = False
    FIELDS = ['urlid','urlid','tags','source','status','inserted','lastpolled',
            'hash','whois_expiry','whois_expiry_last_checked','url_type',
            'last_reported','first_blocked','last_blocked','title']

    @property
    def id(self):
        return self['urlid']

    def get_categories(self):
        q = Query(self.conn, """select cat.*, urlcat.id as url_category_id, urlcat.enabled, urlcat.userid as url_category_userid, urlcat.primary_category
            from public.categories cat
            inner join public.url_categories urlcat on cat.id = urlcat.category_id
            where urlid = %s
            order by enabled desc, name""",
            [ self['urlid'] ])
        for row in q:
            yield Category(self.conn, data=row)
        q.close()
      
    def get_latest_status(self):
        q = Query(self.conn, 
                  "select * from public.url_latest_status where urlid = %s",
                  [ self['urlid'] ])
        out = {}
        for row in q:
            network = row['network_name']
            out[network] = row
        q.close()
        return out

    def get_category_comments(self):
        q = Query(self.conn, 
                  """select url_category_comments.*, users.id as userid, users.username as username
                     from public.url_category_comments
                     inner join frontend.users on url_category_comments.userid = users.id
                     where urlid = %s
                     order by id""",
                  [ self['urlid'] ])
        for row in q:
            yield UrlCategoryComment(self.conn, data=row)
        q.close()

    def get_report_comments(self):
        q = Query(self.conn,
                  """select url_report_category_comments.*, 
                            cat1.name as reporter_category_name, 
                            cat2.name as damage_category_name,
                            users.id as userid, users.username as username
                     from public.url_report_category_comments
                     inner join frontend.users on userid = users.id
                     left join public.url_report_categories cat1 on reporter_category_id = cat1.id
                     left join public.url_report_categories cat2 on damage_category_id = cat2.id
                     where urlid = %s
                     order by id""",
                  [ self['urlid'] ])
        for row in q:
            yield UrlReportCategoryComment(self.conn, data=row)
        q.close()

    def get_reporter_category(self):
        obj = list(self.get_report_categories('reporter'))
        if len(obj):
            return obj[0]
        

    def get_report_categories(self, category_type):
        q = Query(self.conn,
                  """select url_report_categories.*
                     from public.url_report_categories 
                        inner join public.url_report_category_asgt on (category_id = url_report_categories.id)
                     where urlid = %s and category_type = %s
                     order by name""",
                  [ self['urlid'], category_type ])
        for row in q:
            yield UrlReportCategory(self.conn, data=row)
        q.close()

      
class Category(DBObject):
    TABLE = 'public.categories'
    FIELDS = ['display_name','org_category_id','block_count', 'blocked_url_count',
              'total_block_count', 'total_blocked_url_count',
              'tree', 'name','namespace']
              
    @classmethod
    def select_active(cls, conn):
        q = Query(conn, """select *
            from public.selected_categories 
            order by namespace, name""", [])
        for row in q:
            yield cls(conn, data=row)
        q.close()
                    
    @classmethod
    def select_with_counts(cls, conn):
        q = Query(conn,
                  """select categories.id, name, count(*) ct
                     from public.categories
                     inner join public.url_categories on category_id = categories.id
                     where namespace = 'ORG'
                     group by categories.id, name
                     order by categories.id, name""", [])
        for row in q:
            yield cls(conn, data=row)
        q.close()
              
class UrlCategory(DBObject):
    TABLE = 'public.url_categories'
    FIELDS = ['urlid','category_id','enabled','userid']              
    
    def get_category(self):
        return Category(self.conn, self['category_id'])
        
        
                          

class UrlCategoryComment(DBObject):
    TABLE = 'public.url_category_comments'
    FIELDS = ['url_id','description','userid']

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
        'status_message',
    ]

class ISP(DBObject):
    TABLE = 'public.isps'
    FIELDS = ['name','description']

class ISPReport(DBObject):
    TABLE = 'public.isp_reports'
    FIELDS = [
        'name',
        'email',
        'urlid',
        'network_name',
        'message',
        'report_type',
        'unblocked',
        'notified',
        'send_updates',
        'submitted',
        'contact_id',
        'allow_publish',
        'status',
        'site_category',
        'allow_contact',
        'mailname',
        'resolved_email_id',
        'resolved_userid',

        'category_notes',
        'review_notes',
        'matches_policy',
        'reporter_category_id',
    ]

    @classmethod
    def get_by_url_network(klass, conn, url, network_name):
        q = Query(conn, """select isp_reports.* 
            from public.isp_reports isp_reports
            inner join urls on urls.urlid = isp_reports.urlid
            where url = %s and network_name = %s""", 
            [url, network_name])
        row = q.fetchone()
        return klass(conn, data=row)

    @classmethod
    def get_featured(klass, conn):
        q = Query(conn,
                  """select isp_reports.*, urls.url
                     from public.isp_reports
                     inner join urls using (urlid)
                     where featured_block = true
                     order by random()
                     limit 10""", [])
        for row in q:
            yield klass(conn, data=row)


    @staticmethod
    def get_category_stats(conn):
        q = Query(conn,
                  """select name, count(distinct case when primary_category = true then url_categories.id else null end ) primary_ct, count(*) ct
                     from public.categories
                     inner join public.url_categories on url_categories.category_id = categories.id
                     where categories.namespace = 'ORG' and url_categories.enabled = true
                     group by name
                     order by name""", [])
        return q

    @staticmethod
    def get_reply_stats(conn):
        reply_stats = Query(conn,
              """select network_name, extract('year' from isp_reports.created)::int as year,
                    count(distinct isp_reports.id) reports_sent,
                    count(distinct isp_report_emails.report_id) auto_replies_logged,
                    count(isp_report_emails.id) replies_logged,
                    avg(case when (status='unblocked' or status='rejected' or unblocked=1) and isp_report_emails.id = isp_reports.resolved_email_id then isp_reports.last_updated - isp_reports.submitted else null end) avg_response_time,
                    sum(case when status = 'sent' and unblocked = 0 then 1 else 0 end) count_open,
                    sum(case when unblocked = 0 and status = 'sent' and isp_report_emails.report_id is null then 1 else 0 end) count_unresolved,
                    sum(case when unblocked = 0 and status = 'sent' and isp_report_emails.report_id is null and isp_reports.matches_policy is false then 1 else 0 end) count_unresolved_badblock,
                    sum(case when unblocked = 0 and status = 'rejected' and matches_policy is false then 1 else 0 end) count_resolved_badblock,
                    sum(case when unblocked = 0 and status = 'sent' and isp_report_emails.report_id is null and (isp_reports.matches_policy is true or isp_reports.matches_policy is null) then 1 else 0 end) count_unresolved_policyblock
                    from public.isp_reports_sent isp_reports
                    left join public.isp_report_emails on report_id = isp_reports.id
                    where network_name not in ('ORG', 'BBFC')
                    group by network_name, extract('year' from isp_reports.created)::int""",
              [])
        return reply_stats

    def get_url(self):
        return Url(self.conn, self['urlid'])
            
    def get_isp(self):
        return ISP.select_one(self.conn, name=self['network_name'])
            
    def get_emails(self):
        return ISPReportEmail.select(self.conn, report_id=self['id'])
        
    def get_emails_parsed(self):
        return ( (email, email.decode()) for email in self.get_emails() )
        
    def set_status(self, newstatus, email, userid):
        assert newstatus in ('unblocked', 'rejected', 'no-decision')
        self['last_updated'] = max([self['last_updated'] or self['created'], email['created'] if email else None])
        self['status'] = newstatus
        self['resolved_userid'] = userid
        if email:
            self['resolved_email_id'] = email['id']
        else:
            self['resolved_email_id'] = None

        q = Query(self.conn, """update public.isp_reports set 
            status = %s, last_updated = %s, resolved_email_id = %s, resolved_userid = %s
            where id = %s""",
            [self['status'], self['last_updated'], self['resolved_email_id'], self['resolved_userid'],
             self['id']]
            )

    def reset_status(self, status):
        self['status'] = status
        self['resolved_email_id'] = None
        self['resolved_userid'] = None

        q = Query(self.conn, """update public.isp_reports set 
            status = %s,  resolved_email_id = %s, resolved_userid = %s
            where id = %s""",
                  [self['status'], None, None, self['id']]
                  )

    def update_flag(self, name, value):
        assert name in ('matches_policy','egregious_block','featured_block','maybe_harmless'), \
                "{0} is not an accepted flag".format(name)
        q = Query(self.conn, """update public.isp_reports 
                                set {0} = %s
                                where id = %s """.format(name),
                             [ value, self['id'] ])
        self[name] = value

        
    def get_url(self):
        return Url.select_one(self.conn, urlid=self['urlid'])
        
    def get_comments(self):
        q = Query(self.conn, """select isp_report_comments.*, users.id as userid, users.username as username
                     from public.isp_report_comments
                     inner join frontend.users on isp_report_comments.userid = users.id
                     where report_id = %s
                     order by id""",
                  [ self['id'] ])
        for row in q:
            yield ISPReportComment(self.conn, data=row)
        q.close()
     
    def get_prev(self):
        q = Query(self.conn, """select url, network_name from public.isp_reports inner join public.urls using (urlid)
            where id > %s order by id limit 1""",
            [self['id']])
        row = q.fetchone()
        q.close()
        if row is None:
            return None
        return {
            'url': row[0],
            'network_name': row[1]
            }

     
    def get_next(self):
        q = Query(self.conn, """select url, network_name from public.isp_reports inner join public.urls using (urlid)
            where id < %s order by id desc limit 1""",
            [self['id']])
        row = q.fetchone()
        q.close()
        if row is None:
            return None
        return {
            'url': row[0],
            'network_name': row[1]
            }

    def get_contact(self):
        q = Query(self.conn, """select * from public.contacts where id = %s""", [self['contact_id']])
        row = q.fetchone()
        q.close()
        return row
        
    def get_related(self):
        """Get all reports for the same URL"""
        return ISPReport.select(self.conn, urlid=self['urllid'])
        
    def get_reported_networks(self):
        return [x['network_name'] for x in self.get_related()]
        
    def get_report_for(self, network_name):
        try:
            for rpt in ISPReport.select(self.conn, urlid=self['urlid'], network_name=network_name, _orderby='-id'):
                if rpt['status'] != 'cancelled':
                    return rpt
        except ObjectNotFound:
            pass

        return None

    def get_final_reply(self):
        return ISPReportEmail(self.conn, self['resolved_email_id'])


    @classmethod
    def get_reviewers(cls, conn):
        q = Query(conn, """
            select distinct users.* from frontend.users 
            inner join public.isp_report_users iru on iru.userid = users.id
            inner join public.isp_reports on (isp_reports.id = iru.report_id or isp_reports.urlid = iru.urlid)
            """, [])
        for row in q:
            yield User(conn, data=row)
        q.close()

class ISPReportEmail(DBObject):
    TABLE = 'public.isp_report_emails'
    FIELDS = [
        'report_id',
        'message',
    ]
            
    def decode(self):
        import email
        
        ret = email.message_from_string(self['message'])
        return ret
        
    def get_report(self):
        return ISPReport.select_one(self.conn, self['report_id'])

class ISPReportComment(DBObject):
    TABLE = 'public.isp_report_comments'
    FIELDS = [
        'report_id',
        'matches_policy',
        'review_notes',
        'userid'
        ]

class UrlReportCategory(DBObject):
    TABLE = 'public.url_report_categories'
    FIELDS = [
        'name',
        'category_type'
        ]
        
class UrlReportCategoryAsgt(DBObject):
    TABLE = 'public.url_report_category_asgt'
    FIELDS = [
        'urlid',
        'category_id',
        'userid'
        ]
        
class UrlReportCategoryComment(DBObject):
    TABLE = 'public.url_report_category_comments'
    FIELDS = [
        'urlid',
        'damage_category_id',
        'reporter_category_id',
        'review_notes',
        'userid'
        ]

class SearchIgnoreTerm(DBObject):
    TABLE = 'public.search_ignore_terms'
    FIELDS = [
        'term',
        'enabled'
        ]

class Rightsholder(DBObject):
    TABLE = 'rightsholders'
    FIELDS = [
        'name',
        'address1',
        'address2',
        'city',
        'county',
        'postal_code',
        'country',
        'phone',
        'email'
    ]

    @classmethod
    def get_list(cls, conn):
        for obj in cls.select(conn, _orderby='name'):
            yield (obj['id'], "{0} ({1})".format(obj['name'], obj['country']))

    def get_court_judgments(self):
        return CourtJudgment.select(self.conn, rightsholder_id=self['id'])
