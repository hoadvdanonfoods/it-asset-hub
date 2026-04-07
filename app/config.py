import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
EXTERNAL_ENV_FILE = os.getenv('IT_ASSET_HUB_ENV_FILE')
if EXTERNAL_ENV_FILE:
    load_dotenv(EXTERNAL_ENV_FILE, override=False)
load_dotenv(BASE_DIR / '.env', override=False)

DATA_DIR = Path(os.getenv('DATA_DIR', str(BASE_DIR / 'data')))
DEFAULT_DB_PATH = DATA_DIR / 'it_asset_hub.db'
DEFAULT_DATABASE_URL = f'sqlite:///{DEFAULT_DB_PATH}'

APP_NAME = os.getenv('APP_NAME', 'IT Asset Hub')
APP_VERSION = os.getenv('APP_VERSION', 'V2')
SECRET_KEY = os.getenv('SECRET_KEY', 'it-asset-hub-local-secret')
APP_HOST = os.getenv('APP_HOST', '127.0.0.1')
APP_PORT = int(os.getenv('APP_PORT', '8010'))
APP_BASE_URL = os.getenv('APP_BASE_URL', f'http://{APP_HOST}:{APP_PORT}')
DATABASE_URL = os.getenv('DATABASE_URL', DEFAULT_DATABASE_URL)
SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'session')
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'lax')
IS_PRODUCTION = os.getenv('IS_PRODUCTION', 'false').lower() == 'true'
DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
AUTO_CREATE_DEFAULT_ADMIN = os.getenv('AUTO_CREATE_DEFAULT_ADMIN', 'true').lower() == 'true'
AUTO_BACKFILL_ASSET_EVENTS = os.getenv('AUTO_BACKFILL_ASSET_EVENTS', 'true').lower() == 'true'
