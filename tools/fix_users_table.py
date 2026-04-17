import os
from dotenv import load_dotenv
load_dotenv('.env')

from sqlalchemy import create_engine, text
engine = create_engine(os.getenv('DATABASE_URL'))

try:
    with engine.begin() as conn:
        with conn.begin_nested():
            conn.execute(text("ALTER TABLE users ADD COLUMN session_version INTEGER DEFAULT 1"))
        print("Successfully added session_version column")
except Exception as e:
    print(f"Error adding column: {e}")

try:
    with engine.begin() as conn:
        with conn.begin_nested():
            conn.execute(text("ALTER TABLE users ADD COLUMN password_changed_at DATETIME"))
        print("Successfully added password_changed_at column")
except Exception as e:
    print(f"Error adding column: {e}")
