import os
from dotenv import load_dotenv

load_dotenv('.env')

from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User
from app.config import DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_USERNAME
from app.security import hash_password

db = SessionLocal()
try:
    user = db.scalar(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
    if user:
        user.password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        user.password = '[hashed]'
        db.commit()
        print(f"Successfully reset password for {DEFAULT_ADMIN_USERNAME} to the new secure DEFAULT_ADMIN_PASSWORD from .env")
    else:
        print(f"User {DEFAULT_ADMIN_USERNAME} not found in the database. Cannot reset password.")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
