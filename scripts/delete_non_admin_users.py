import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models import User
from app.config import DEFAULT_ADMIN_USERNAME
from sqlalchemy import delete

def run():
    db = SessionLocal()
    try:
        stmt = delete(User).where(User.username != DEFAULT_ADMIN_USERNAME)
        result = db.execute(stmt)
        db.commit()
        print(f"Deleted {result.rowcount} users.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    run()
