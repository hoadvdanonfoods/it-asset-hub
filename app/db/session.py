from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith('sqlite')
engine_args = {
    'pool_pre_ping': not is_sqlite,
}
if is_sqlite:
    engine_args['connect_args'] = {'check_same_thread': False}
else:
    # PostgreSQL production-ready pooling
    engine_args['pool_size'] = 5
    engine_args['max_overflow'] = 10

engine = create_engine(DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
