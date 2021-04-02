

# Default configuration

# Copy to a new file, edit, and set BLOCKEDFRONTEND_SETTINGS env var

DEBUG = False
LOGLEVEL = 'INFO'

API_EMAIL = ''
API_SECRET = ''

SITE_URL="http://localhost:5000"
SITE_THEME='blocked-uk'

# module flags
MODULE_UNBLOCK = True
MODULE_CATEGORY = True
MODULE_SAVEDLIST = True
MODULE_ADMIN = True

UPDATE_PASSWORD = None

REMOTE_TYPE = "modx"
REMOTE_SRC = None
REMOTE_AUTH = None
REMOTE_PAGES = []
REMOTE_RELOAD = False

CACHEBUST = 'l'

CACHE_PATH = '/tmp/remotecontent.sqlite'
CACHE_TIME = 3600

# disable PIWIK by default, enable on live site
PIWIK = False

DUMMY = False

RANDOM_EXCLUDE_NETWORKS = '{}' # PG array for excluding randomly selected URLs based on network

REMOTE_CONTENT_STYLE = 'style="background-color: light-blue"'

ISPS = [
    'BT',
    'Sky',
    'TalkTalk',
    'O2',
    'EE',
    'Vodafone',
    'VirginMedia',
    'Three',
    'Plusnet',
    'Cloudflare family',
    'OpenDNS'
    ]

ALL_ISPS = ISPS + [
    'Uno',
    'AAISP',
]

STATUS_NAMES = {
    'error': 'Error',
    'dnserror': 'DNS Error',
    'sslerror': 'SSL Error',
    'ok': 'OK',
    
    }

SITE_CATEGORIES = {
    'anonymizers': "Anonymizers",
    'dating': "Dating and/or chat",
    'drugs': "Drugs",
    'weapons': "Weapons and/or violence",
    'pornography': "Pornography and adult sexual content",
    'suicide': "Suicide",
    'alcohol': "Alcohol brand promotion",
    'blood & gore': "Blood and gore",
    'gambling': "Gambling",
    'tobacco': "Tobacco"
}

BBFC_REPORT_ACCEPTED_CUTOFF = 3

RANDOMSITE = 'frontpagelists'

DEFAULT_REGION = 'gb'

MAIL_DOMAIN = 'example.com'
