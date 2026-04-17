import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
EXTERNAL_ENV_FILE = os.getenv('IT_ASSET_HUB_ENV_FILE')
if EXTERNAL_ENV_FILE:
    load_dotenv(EXTERNAL_ENV_FILE, override=False)
load_dotenv(BASE_DIR / '.env', override=False)

DATA_DIR = Path(os.getenv('DATA_DIR', str(BASE_DIR / 'data')))
LOG_DIR = Path(os.getenv('LOG_DIR', str(DATA_DIR / 'logs')))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
DEFAULT_DB_PATH = DATA_DIR / 'it_asset_hub.db'
DEFAULT_DATABASE_URL = f'sqlite:///{DEFAULT_DB_PATH}'

APP_NAME = os.getenv('APP_NAME', 'IT Asset Hub')
APP_VERSION = os.getenv('APP_VERSION', 'V2')
IS_PRODUCTION = os.getenv('IS_PRODUCTION', 'false').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', 'it-asset-hub-local-secret')
APP_HOST = os.getenv('APP_HOST', '127.0.0.1')
APP_PORT = int(os.getenv('APP_PORT', '8010'))
APP_BASE_URL = os.getenv('APP_BASE_URL', f'http://{APP_HOST}:{APP_PORT}')
DATABASE_URL = os.getenv('DATABASE_URL', DEFAULT_DATABASE_URL)
SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'session')
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'lax')
SESSION_MAX_AGE_SECONDS = int(os.getenv('SESSION_MAX_AGE_SECONDS', '28800'))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('LOGIN_RATE_LIMIT_WINDOW_SECONDS', '900'))
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv('LOGIN_RATE_LIMIT_MAX_ATTEMPTS', '5'))
DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
AUTO_CREATE_DEFAULT_ADMIN = os.getenv('AUTO_CREATE_DEFAULT_ADMIN', 'true').lower() == 'true'
AUTO_BACKFILL_ASSET_EVENTS = os.getenv('AUTO_BACKFILL_ASSET_EVENTS', 'true').lower() == 'true'

# Zalo Bot Notification
ZALO_BOT_URL = os.getenv('ZALO_BOT_URL', '')
ZALO_BOT_TOKEN = os.getenv('ZALO_BOT_TOKEN', '')
ZALO_NOTIFICATION_TARGET = os.getenv('ZALO_NOTIFICATION_TARGET', '')

if IS_PRODUCTION and SECRET_KEY == 'it-asset-hub-local-secret':
    raise RuntimeError('SECRET_KEY must be set in production and must not use the local default secret')

# if IS_PRODUCTION and not SESSION_COOKIE_SECURE:
#     raise RuntimeError('SESSION_COOKIE_SECURE must be true in production')

if IS_PRODUCTION and DEFAULT_ADMIN_PASSWORD == 'admin123':
    raise RuntimeError('DEFAULT_ADMIN_PASSWORD must not use the default value in production')

if IS_PRODUCTION and AUTO_CREATE_DEFAULT_ADMIN:
    raise RuntimeError('AUTO_CREATE_DEFAULT_ADMIN must be false in production')
