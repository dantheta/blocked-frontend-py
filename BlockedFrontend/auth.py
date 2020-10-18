
from flask import g, abort
from functools import wraps

__all__ = ['AdminPermissionException', 'check_admin', 'check_moderator', 'check_reviewer',
           'level_compare', 'is_level', 'check_level']

LEVELS = ['user', 'reviewer', 'moderator', 'admin']


class AdminPermissionException(Exception):
    pass


def level_compare(current, required):
    """Compare admin levels by position in LEVELS list"""
    l1 = LEVELS.index(current)
    l2 = LEVELS.index(required)
    return l1 >= l2

# decorator to check admin


def check_admin(s):
    @wraps(s)
    def wrapped(*args, **kw):
        check_level('admin')
        return s(*args, **kw)
    return wrapped


def check_moderator(s):
    @wraps(s)
    def wrapped(*args, **kw):
        check_level('moderator')
        return s(*args, **kw)
    return wrapped


def check_reviewer(s):
    @wraps(s)
    def wrapped(*args, **kw):
        check_level('reviewer')
        return s(*args, **kw)
    return wrapped


def is_level(level='admin'):
    return level_compare(g.admin_level, level)


def check_level(required):
    if not (g.admin and level_compare(g.admin_level, required)):
        abort(403)
