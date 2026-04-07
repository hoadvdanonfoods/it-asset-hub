from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith('sqlite')
engine = create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False} if is_sqlite else {},
    pool_pre_ping=not is_sqlite,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
