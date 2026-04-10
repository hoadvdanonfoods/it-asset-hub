from sqlalchemy import text

from app.db.session import engine


def ensure_schema() -> None:
    statements = [
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
        "ALTER TABLE assets ADD COLUMN assigned_at VARCHAR(25)",
        "ALTER TABLE assets ADD COLUMN unassigned_at VARCHAR(25)",
        "ALTER TABLE incidents ADD COLUMN requester_department VARCHAR(120)",
        """CREATE TABLE asset_assignments (
            id INTEGER PRIMARY KEY,
            asset_id INTEGER NOT NULL,
            assigned_user VARCHAR(120) NOT NULL,
            assigned_by VARCHAR(120),
            assigned_at DATETIME,
            unassigned_at DATETIME,
            returned_by VARCHAR(120),
            note TEXT,
            status VARCHAR(20),
            FOREIGN KEY(asset_id) REFERENCES assets(id)
        )""",
        "CREATE INDEX ix_asset_assignments_asset_id ON asset_assignments (asset_id)",
        """CREATE TABLE asset_events (
            id INTEGER PRIMARY KEY,
            asset_id INTEGER NOT NULL,
            event_type VARCHAR(40),
            title VARCHAR(200),
            description TEXT,
            actor VARCHAR(120),
            created_at DATETIME,
            FOREIGN KEY(asset_id) REFERENCES assets(id)
        )""",
        "CREATE INDEX ix_asset_events_asset_id ON asset_events (asset_id)",
        "CREATE INDEX ix_asset_events_created_at ON asset_events (created_at)",
        """CREATE TABLE incident_events (
            id INTEGER PRIMARY KEY,
            incident_id INTEGER NOT NULL,
            event_type VARCHAR(40),
            title VARCHAR(200),
            description TEXT,
            actor VARCHAR(120),
            created_at DATETIME,
            FOREIGN KEY(incident_id) REFERENCES incidents(id)
        )""",
        "CREATE INDEX ix_incident_events_incident_id ON incident_events (incident_id)",
        "CREATE INDEX ix_incident_events_created_at ON incident_events (created_at)",
        """CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            category VARCHAR(80),
            description TEXT,
            original_filename VARCHAR(255) NOT NULL,
            stored_filename VARCHAR(255) NOT NULL UNIQUE,
            stored_path VARCHAR(500) NOT NULL,
            mime_type VARCHAR(120),
            file_size INTEGER,
            uploaded_by VARCHAR(120),
            created_at DATETIME,
            is_active BOOLEAN DEFAULT 1
        )""",
        "CREATE INDEX ix_documents_title ON documents (title)",
        "CREATE INDEX ix_documents_category ON documents (category)",
        """CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY,
            created_at DATETIME,
            actor VARCHAR(120),
            module VARCHAR(40),
            action VARCHAR(60),
            entity_type VARCHAR(60),
            entity_id VARCHAR(120),
            result VARCHAR(20),
            reason VARCHAR(255),
            metadata_json TEXT
        )""",
        "CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at)",
        "CREATE INDEX ix_audit_logs_actor ON audit_logs (actor)",
        "CREATE INDEX ix_audit_logs_module ON audit_logs (module)",
        "CREATE INDEX ix_audit_logs_action ON audit_logs (action)",
        "CREATE INDEX ix_audit_logs_result ON audit_logs (result)",
    ]
    backfill_statements = [
        "UPDATE users SET is_active = 1 WHERE is_active IS NULL",
        "UPDATE users SET can_view_dashboard = 1 WHERE can_view_dashboard IS NULL",
        "UPDATE users SET can_view_assets = 1 WHERE can_view_assets IS NULL",
        "UPDATE users SET can_view_maintenance = 1 WHERE can_view_maintenance IS NULL",
        "UPDATE users SET can_view_incidents = 1 WHERE can_view_incidents IS NULL",
        "UPDATE users SET can_view_resources = 0 WHERE can_view_resources IS NULL",
        "UPDATE users SET can_create_assets = 0 WHERE can_create_assets IS NULL",
        "UPDATE users SET can_edit_assets = 0 WHERE can_edit_assets IS NULL",
        "UPDATE users SET can_import_assets = 0 WHERE can_import_assets IS NULL",
        "UPDATE users SET can_export_assets = 0 WHERE can_export_assets IS NULL",
        "UPDATE users SET can_create_maintenance = 0 WHERE can_create_maintenance IS NULL",
        "UPDATE users SET can_edit_maintenance = 0 WHERE can_edit_maintenance IS NULL",
        "UPDATE users SET can_export_maintenance = 0 WHERE can_export_maintenance IS NULL",
        "UPDATE users SET can_create_incidents = 1 WHERE can_create_incidents IS NULL",
        "UPDATE users SET can_edit_incidents = 0 WHERE can_edit_incidents IS NULL",
        "UPDATE users SET can_export_incidents = 0 WHERE can_export_incidents IS NULL",
        "UPDATE users SET can_manage_users = 0 WHERE can_manage_users IS NULL",
        "UPDATE users SET can_manage_system = 0 WHERE can_manage_system IS NULL",
        "UPDATE users SET can_manage_resources = 0 WHERE can_manage_resources IS NULL",
        "UPDATE users SET can_view_documents = 0 WHERE can_view_documents IS NULL",
        "UPDATE users SET can_manage_documents = 0 WHERE can_manage_documents IS NULL",
        "UPDATE users SET can_view_resources = 1, can_create_assets = 1, can_edit_assets = 1, can_import_assets = 1, can_export_assets = 1, can_create_maintenance = 1, can_edit_maintenance = 1, can_export_maintenance = 1, can_create_incidents = 1, can_edit_incidents = 1, can_export_incidents = 1, can_manage_users = 1, can_manage_system = 1, can_manage_resources = 1, can_view_documents = 1, can_manage_documents = 1 WHERE role = 'admin'",
    ]
    with engine.begin() as conn:
        for statement in statements:
            try:
                conn.execute(text(statement))
            except Exception:
                pass
        for statement in backfill_statements:
            try:
                conn.execute(text(statement))
            except Exception:
                pass
