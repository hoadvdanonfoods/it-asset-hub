import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('AUTO_CREATE_DEFAULT_ADMIN', 'false')

import app.db.models  # noqa: E402 — ensures all models register with Base
from app.db.base import Base
from app.db.models import Asset, AssetAssignment, AssetEvent, AssetStatusHistory


@pytest.fixture(scope='session')
def engine():
    e = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def test_asset(db):
    asset = Asset(
        asset_code='TEST-001',
        asset_name='Test Laptop',
        asset_type='Laptop',
        status='in_stock',
    )
    db.add(asset)
    db.flush()
    return asset
