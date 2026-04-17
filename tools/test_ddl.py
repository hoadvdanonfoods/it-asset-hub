import os
from dotenv import load_dotenv
load_dotenv('.env')

from sqlalchemy import create_engine, text
engine = create_engine(os.getenv('DATABASE_URL'))

legacy_statements = [
    "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN can_view_dashboard BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN can_view_assets BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN can_view_maintenance BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN can_view_incidents BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN can_view_resources BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_create_assets BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_edit_assets BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_import_assets BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_export_assets BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_create_maintenance BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_edit_maintenance BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_export_maintenance BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_create_incidents BOOLEAN DEFAULT 1",
    "ALTER TABLE users ADD COLUMN can_edit_incidents BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_export_incidents BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_manage_users BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_manage_system BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_manage_resources BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_view_documents BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN can_manage_documents BOOLEAN DEFAULT 0",
    "ALTER TABLE users ADD COLUMN session_version INTEGER DEFAULT 1",
    "ALTER TABLE users ADD COLUMN password_changed_at DATETIME",
    "ALTER TABLE assets ADD COLUMN assigned_at VARCHAR(25)",
    "ALTER TABLE assets ADD COLUMN unassigned_at VARCHAR(25)",
    "ALTER TABLE incidents ADD COLUMN requester_department VARCHAR(120)",
]

with engine.begin() as conn:
    for stmt in legacy_statements:
        try:
            with conn.begin_nested():
                conn.execute(text(stmt))
                print(f"SUCCESS: {stmt}")
        except Exception as e:
            print(f"FAILED: {stmt} -> {e}")
