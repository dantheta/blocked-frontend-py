
from flask import g, abort
from functools import wraps

__all__ = ['AdminPermissionException','check_admin']

class AdminPermissionException(Exception):
    pass

# decorator to check admin

def check_admin(s):
    @wraps(s)
    def wrapped(*args, **kw):
        if not g.admin:
            abort(403)
            #raise AdminPermissionException("Admin permissions are required to access this page")
        return s(*args, **kw)
    return wrapped
