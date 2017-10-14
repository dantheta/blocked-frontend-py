

# Default configuration

# Copy to a new file, edit, and set BLOCKEDFRONTEND_SETTINGS env var

DEBUG = False

API_EMAIL = ''
API_SECRET = ''

SITE_URL="http://localhost:5000"

UPDATE_PASSWORD = None

REMOTE_SRC = None
REMOTE_AUTH = None
REMOTE_PAGES = []
REMOTE_RELOAD = False

CACHE_PATH = '/tmp/remotecontent.sqlite'
CACHE_TIME = 3600

BLOCKED_CUTOFF_DAYS = 28

# disable PIWIK by default, enable on live site
PIWIK = False

DUMMY = False

ADMIN_USER = None
ADMIN_PASSWORD = None

REMOTE_CONTENT_STYLE = 'style="background-color: light-blue"'

ISPS = [
    'BT',
    'Sky',
    'TalkTalk',
    'O2',
    'EE',
    'Vodafone'
    ]

STATUS_NAMES = {
    'error': 'Error',
    'dnserror': 'DNS Error',
    'sslerror': 'SSL Error',
    'ok': 'OK',
    
    }
