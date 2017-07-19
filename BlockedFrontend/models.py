
from NORM import DBObject

class SavedList(DBObject):
    TABLE = 'savedlists'
    FIELDS = [
            'username',
            'name'
            ]

    def get_items(self):
        return Item.select(self.conn, list_id=self['id'], _orderby='url')


class Item(DBObject):
    TABLE = 'items'
    FIELDS = [
            'list_id',
            'url',
            'title'
            ]

    def get_list(self):
        return SavedList.select_one(self.conn, self['list_id'])
