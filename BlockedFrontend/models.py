
import psycopg2.extensions

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

from NORM import DBObject

class SavedList(DBObject):
    TABLE = 'savedlists'
    FIELDS = [
            'username',
            'name',
            'public'
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
            'title'
            ]

    def get_list(self):
        return SavedList.select_one(self.conn, self['list_id'])
