import re
import unicodedata

from sqlalchemy import text

from app.db.session import engine


MASTER_TABLES = {
    'departments': """CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        note TEXT
    )""",
    'employees': """CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY,
        employee_code VARCHAR(50) NOT NULL UNIQUE,
        full_name VARCHAR(120) NOT NULL,
        department_id INTEGER,
        title VARCHAR(120),
        email VARCHAR(120),
        phone VARCHAR(50),
        is_active BOOLEAN DEFAULT 1,
        note TEXT,
        FOREIGN KEY(department_id) REFERENCES departments(id)
    )""",
    'asset_types': """CREATE TABLE IF NOT EXISTS asset_types (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        category_group VARCHAR(120),
        is_active BOOLEAN DEFAULT 1,
        note TEXT
    )""",
    'locations': """CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        site_group VARCHAR(120),
        is_active BOOLEAN DEFAULT 1,
        note TEXT
    )""",
    'asset_categories': """CREATE TABLE IF NOT EXISTS asset_categories (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME
    )""",
    'asset_statuses': """CREATE TABLE IF NOT EXISTS asset_statuses (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME
    )""",
    'vendors': """CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME
    )""",
    'incident_categories': """CREATE TABLE IF NOT EXISTS incident_categories (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME
    )""",
    'priorities': """CREATE TABLE IF NOT EXISTS priorities (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME
    )""",
    'maintenance_types': """CREATE TABLE IF NOT EXISTS maintenance_types (
        id INTEGER PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        description TEXT,
        is_active BOOLEAN DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME
    )""",
}

MASTER_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_departments_code ON departments (code)",
    "CREATE INDEX IF NOT EXISTS ix_employees_employee_code ON employees (employee_code)",
    "CREATE INDEX IF NOT EXISTS ix_asset_types_code ON asset_types (code)",
    "CREATE INDEX IF NOT EXISTS ix_locations_code ON locations (code)",
    "CREATE INDEX IF NOT EXISTS ix_asset_categories_code ON asset_categories (code)",
    "CREATE INDEX IF NOT EXISTS ix_asset_statuses_code ON asset_statuses (code)",
    "CREATE INDEX IF NOT EXISTS ix_vendors_code ON vendors (code)",
    "CREATE INDEX IF NOT EXISTS ix_incident_categories_code ON incident_categories (code)",
    "CREATE INDEX IF NOT EXISTS ix_priorities_code ON priorities (code)",
    "CREATE INDEX IF NOT EXISTS ix_maintenance_types_code ON maintenance_types (code)",
]

FK_COLUMNS = {
    'assets': [
        ('category_id', 'INTEGER'),
        ('status_id', 'INTEGER'),
        ('department_id', 'INTEGER'),
        ('location_id', 'INTEGER'),
        ('vendor_id', 'INTEGER'),
        ('current_assignment_id', 'INTEGER'),
    ],
    'incidents': [
        ('category_id', 'INTEGER'),
        ('priority_id', 'INTEGER'),
        ('department_id', 'INTEGER'),
        ('source', 'VARCHAR(30)'),
    ],
    'maintenances': [
        ('maintenance_type_id', 'INTEGER'),
        ('vendor_id', 'INTEGER'),
    ],
    'asset_assignments': [
        ('employee_id', 'INTEGER'),
    ],
}

FK_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_assets_category_id ON assets (category_id)",
    "CREATE INDEX IF NOT EXISTS ix_assets_status_id ON assets (status_id)",
    "CREATE INDEX IF NOT EXISTS ix_assets_department_id ON assets (department_id)",
    "CREATE INDEX IF NOT EXISTS ix_assets_location_id ON assets (location_id)",
    "CREATE INDEX IF NOT EXISTS ix_assets_vendor_id ON assets (vendor_id)",
    "CREATE INDEX IF NOT EXISTS ix_assets_current_assignment_id ON assets (current_assignment_id)",
    "CREATE INDEX IF NOT EXISTS ix_incidents_category_id ON incidents (category_id)",
    "CREATE INDEX IF NOT EXISTS ix_incidents_priority_id ON incidents (priority_id)",
    "CREATE INDEX IF NOT EXISTS ix_incidents_department_id ON incidents (department_id)",
    "CREATE INDEX IF NOT EXISTS ix_maintenances_maintenance_type_id ON maintenances (maintenance_type_id)",
    "CREATE INDEX IF NOT EXISTS ix_maintenances_vendor_id ON maintenances (vendor_id)",
    "CREATE INDEX IF NOT EXISTS ix_asset_assignments_employee_id ON asset_assignments (employee_id)",
    "CREATE INDEX IF NOT EXISTS ix_asset_status_history_asset_id ON asset_status_history (asset_id)",
    "CREATE INDEX IF NOT EXISTS ix_asset_status_history_old_status_id ON asset_status_history (old_status_id)",
    "CREATE INDEX IF NOT EXISTS ix_asset_status_history_new_status_id ON asset_status_history (new_status_id)",
    "CREATE INDEX IF NOT EXISTS ix_asset_status_history_changed_at ON asset_status_history (changed_at)",
]

SEED_ROWS = {
    'asset_statuses': [
        ('IN_STOCK', 'In Stock', 'Tài sản đang sẵn sàng cấp phát', 10),
        ('ASSIGNED', 'Assigned', 'Tài sản đang được cấp cho người dùng', 20),
        ('BORROWED', 'Borrowed', 'Tài sản đang cho mượn', 30),
        ('REPAIRING', 'Repairing', 'Tài sản đang sửa chữa', 40),
        ('RETIRED', 'Retired', 'Tài sản đã ngừng sử dụng', 50),
        ('DISPOSED', 'Disposed', 'Tài sản đã thanh lý', 60),
        ('LOST', 'Lost', 'Tài sản thất lạc', 70),
    ],
    'priorities': [
        ('LOW', 'Low', 'Ưu tiên thấp', 10),
        ('MEDIUM', 'Medium', 'Ưu tiên trung bình', 20),
        ('HIGH', 'High', 'Ưu tiên cao', 30),
        ('CRITICAL', 'Critical', 'Ưu tiên khẩn cấp', 40),
    ],
    'maintenance_types': [
        ('PREVENTIVE', 'Preventive', 'Bảo trì phòng ngừa', 10),
        ('CORRECTIVE', 'Corrective', 'Bảo trì khắc phục', 20),
    ],
}


def _get_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(conn, table_name: str, column_name: str, column_type: str) -> None:
    columns = _get_columns(conn, table_name)
    if column_name in columns:
        return
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def ensure_master_tables(conn) -> None:
    for sql in MASTER_TABLES.values():
        conn.execute(text(sql))
    conn.execute(
        text(
            """CREATE TABLE IF NOT EXISTS asset_status_history (
                id INTEGER PRIMARY KEY,
                asset_id INTEGER NOT NULL,
                old_status_id INTEGER,
                new_status_id INTEGER,
                old_status_code VARCHAR(50),
                new_status_code VARCHAR(50) NOT NULL,
                changed_by VARCHAR(120),
                changed_at DATETIME,
                note TEXT,
                FOREIGN KEY(asset_id) REFERENCES assets(id),
                FOREIGN KEY(old_status_id) REFERENCES asset_statuses(id),
                FOREIGN KEY(new_status_id) REFERENCES asset_statuses(id)
            )"""
        )
    )
    for sql in MASTER_INDEXES:
        conn.execute(text(sql))


def ensure_fk_columns(conn) -> None:
    for table_name, columns in FK_COLUMNS.items():
        for column_name, column_type in columns:
            _add_column_if_missing(conn, table_name, column_name, column_type)
    for sql in FK_INDEXES:
        conn.execute(text(sql))


def seed_master_data(conn) -> None:
    for table_name, rows in SEED_ROWS.items():
        for code, name, description, sort_order in rows:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {table_name} (code, name, description, is_active, sort_order, created_at, updated_at)
                    SELECT :code, :name, :description, 1, :sort_order, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {table_name} WHERE code = :code
                    )
                    """
                ),
                {
                    'code': code,
                    'name': name,
                    'description': description,
                    'sort_order': sort_order,
                },
            )


LOOKUP_FIELDS = {
    'employees': ('employee_code', 'full_name'),
    'departments': ('code', 'name'),
    'locations': ('code', 'name'),
    'asset_categories': ('code', 'name'),
    'asset_statuses': ('code', 'name'),
    'priorities': ('code', 'name'),
    'vendors': ('code', 'name'),
    'incident_categories': ('code', 'name'),
    'maintenance_types': ('code', 'name'),
}

AUTO_SEEDABLE_TABLES = {'asset_categories', 'departments', 'locations', 'employees'}


def _slugify_code(value: str | None, fallback_prefix: str) -> str:
    raw = (value or '').strip()
    slug = re.sub(r'[^a-z0-9]+', '_', raw.lower()).strip('_')
    return (slug or fallback_prefix)[:50]


def _ensure_master_row(conn, table_name: str, raw_value: str | None):
    normalized = _normalize_lookup_value(table_name, raw_value)
    if not normalized:
        return None
    if table_name not in AUTO_SEEDABLE_TABLES:
        return None

    if table_name == 'asset_categories':
        code = _slugify_code(normalized, 'category')
        conn.execute(
            text(
                """
                INSERT INTO asset_categories (code, name, description, is_active, sort_order, created_at, updated_at)
                SELECT :code, :name, :description, 1, 999, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                WHERE NOT EXISTS (
                    SELECT 1 FROM asset_categories WHERE lower(code) = lower(:code) OR lower(name) = lower(:name)
                )
                """
            ),
            {'code': code, 'name': normalized, 'description': 'Auto-created from legacy asset data during migration backfill'},
        )
        row = conn.execute(text("SELECT id FROM asset_categories WHERE lower(code) = lower(:code) OR lower(name) = lower(:name) LIMIT 1"), {'code': code, 'name': normalized}).fetchone()
        return row[0] if row else None

    if table_name == 'departments':
        code = _slugify_code(normalized, 'department')
        conn.execute(
            text(
                """
                INSERT INTO departments (code, name, is_active, note)
                SELECT :code, :name, 1, :note
                WHERE NOT EXISTS (
                    SELECT 1 FROM departments WHERE lower(code) = lower(:code) OR lower(name) = lower(:name)
                )
                """
            ),
            {'code': code, 'name': normalized, 'note': 'Auto-created from legacy asset/incident data during migration backfill'},
        )
        row = conn.execute(text("SELECT id FROM departments WHERE lower(code) = lower(:code) OR lower(name) = lower(:name) LIMIT 1"), {'code': code, 'name': normalized}).fetchone()
        return row[0] if row else None

    if table_name == 'locations':
        code = _slugify_code(normalized, 'location')
        conn.execute(
            text(
                """
                INSERT INTO locations (code, name, is_active, note)
                SELECT :code, :name, 1, :note
                WHERE NOT EXISTS (
                    SELECT 1 FROM locations WHERE lower(code) = lower(:code) OR lower(name) = lower(:name)
                )
                """
            ),
            {'code': code, 'name': normalized, 'note': 'Auto-created from legacy asset data during migration backfill'},
        )
        row = conn.execute(text("SELECT id FROM locations WHERE lower(code) = lower(:code) OR lower(name) = lower(:name) LIMIT 1"), {'code': code, 'name': normalized}).fetchone()
        return row[0] if row else None

    if table_name == 'employees':
        code = _slugify_code(normalized, 'employee')
        conn.execute(
            text(
                """
                INSERT INTO employees (employee_code, full_name, is_active, note)
                SELECT :code, :name, 1, :note
                WHERE NOT EXISTS (
                    SELECT 1 FROM employees WHERE lower(employee_code) = lower(:code) OR lower(full_name) = lower(:name)
                )
                """
            ),
            {'code': code, 'name': normalized, 'note': 'Auto-created from legacy assignment data during migration backfill'},
        )
        row = conn.execute(text("SELECT id FROM employees WHERE lower(employee_code) = lower(:code) OR lower(full_name) = lower(:name) LIMIT 1"), {'code': code, 'name': normalized}).fetchone()
        return row[0] if row else None

    return None


def _normalize_lookup_value(table_name: str, raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    normalized = raw_value.strip()
    if not normalized or normalized.lower() == 'none':
        return None
    if table_name == 'asset_statuses':
        aliases = {
            'active': 'ASSIGNED',
            'inactive': 'IN_STOCK',
            'in_repair': 'REPAIRING',
            'in repair': 'REPAIRING',
            'repair': 'REPAIRING',
            'repairing': 'REPAIRING',
            'broken': 'REPAIRING',
            'retired': 'RETIRED',
            'disposed': 'DISPOSED',
            'lost': 'LOST',
            'borrowed': 'BORROWED',
            'assigned': 'ASSIGNED',
            'in_stock': 'IN_STOCK',
            'in stock': 'IN_STOCK',
        }
        return aliases.get(normalized.lower(), normalized.upper())
    if table_name in {'departments', 'locations'}:
        folded = ''.join(c for c in unicodedata.normalize('NFKD', normalized) if not unicodedata.combining(c))
        folded = folded.replace('đ', 'd').replace('Đ', 'D')
        return re.sub(r'[^A-Za-z0-9]+', '', folded).upper()
    return re.sub(r'\s+', ' ', normalized).strip()


def _lookup_id(conn, table_name: str, column_name: str, raw_value: str | None, unmatched_tracker: dict | None = None):
    normalized = _normalize_lookup_value(table_name, raw_value)
    if not normalized:
        return None
    field1, field2 = LOOKUP_FIELDS.get(table_name, ('code', 'name'))
    row = conn.execute(
        text(
            f"SELECT id FROM {table_name} WHERE lower({field1}) = lower(:value) OR lower({field2}) = lower(:value) LIMIT 1"
        ),
        {'value': normalized},
    ).fetchone()
    if row:
        return row[0]

    seeded_id = _ensure_master_row(conn, table_name, normalized)
    if seeded_id:
        return seeded_id

    if unmatched_tracker is not None:
        key = (table_name, column_name)
        unmatched_tracker.setdefault(key, {})
        unmatched_tracker[key][normalized] = unmatched_tracker[key].get(normalized, 0) + 1
    return None


def _print_unmatched_summary(unmatched_tracker: dict) -> None:
    for (table_name, column_name), values in sorted(unmatched_tracker.items()):
        total = sum(values.values())
        unique = len(values)
        top_values = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:10]
        preview = ', '.join(f'{value} ({count})' for value, count in top_values)
        suffix = ' ...' if unique > len(top_values) else ''
        print(f"[backfill] unmatched {table_name}.{column_name}: {total} rows, {unique} unique -> {preview}{suffix}")


def _dedupe_master_rows(conn, table_name: str, code_column: str, name_column: str, ref_updates: list[tuple[str, str]], extra_updates: list[str] | None = None) -> None:
    rows = conn.execute(text(f"SELECT id, {code_column}, {name_column} FROM {table_name} ORDER BY id ASC")).fetchall()
    grouped: dict[str, list] = {}
    for row in rows:
        normalized_name = _normalize_lookup_value(table_name, row[2])
        if not normalized_name:
            continue
        grouped.setdefault(normalized_name, []).append(row)

    for duplicates in grouped.values():
        if len(duplicates) <= 1:
            continue
        canonical = duplicates[0]
        for duplicate in duplicates[1:]:
            for ref_table, ref_column in ref_updates:
                conn.execute(
                    text(f"UPDATE {ref_table} SET {ref_column} = :target_id WHERE {ref_column} = :source_id"),
                    {'target_id': canonical[0], 'source_id': duplicate[0]},
                )
            for sql in extra_updates or []:
                conn.execute(text(sql), {'target_id': canonical[0], 'source_id': duplicate[0]})
            conn.execute(text(f"DELETE FROM {table_name} WHERE id = :source_id"), {'source_id': duplicate[0]})


def dedupe_master_data(conn) -> None:
    _dedupe_master_rows(conn, 'departments', 'code', 'name', [('assets', 'department_id'), ('incidents', 'department_id'), ('employees', 'department_id')])
    _dedupe_master_rows(conn, 'locations', 'code', 'name', [('assets', 'location_id')])


def backfill_master_data(conn) -> None:
    unmatched_tracker: dict[tuple[str, str], dict[str, int]] = {}
    asset_rows = conn.execute(
        text(
            "SELECT id, asset_type, status, department, location FROM assets "
            "WHERE category_id IS NULL OR status_id IS NULL OR department_id IS NULL OR location_id IS NULL"
        )
    ).fetchall()
    for row in asset_rows:
        category_id = _lookup_id(conn, 'asset_categories', 'asset_type', row[1], unmatched_tracker)
        status_id = _lookup_id(conn, 'asset_statuses', 'status', row[2], unmatched_tracker)
        department_id = _lookup_id(conn, 'departments', 'department', row[3], unmatched_tracker)
        location_id = _lookup_id(conn, 'locations', 'location', row[4], unmatched_tracker)
        conn.execute(
            text(
                """
                UPDATE assets
                SET category_id = COALESCE(category_id, :category_id),
                    status_id = COALESCE(status_id, :status_id),
                    department_id = COALESCE(department_id, :department_id),
                    location_id = COALESCE(location_id, :location_id)
                WHERE id = :id
                """
            ),
            {
                'id': row[0],
                'category_id': category_id,
                'status_id': status_id,
                'department_id': department_id,
                'location_id': location_id,
            },
        )

    incident_rows = conn.execute(
        text("SELECT id, priority, requester_department FROM incidents WHERE priority_id IS NULL OR department_id IS NULL")
    ).fetchall()
    for row in incident_rows:
        priority_id = _lookup_id(conn, 'priorities', 'priority', row[1], unmatched_tracker)
        department_id = _lookup_id(conn, 'departments', 'requester_department', row[2], unmatched_tracker)
        conn.execute(
            text(
                """
                UPDATE incidents
                SET priority_id = COALESCE(priority_id, :priority_id),
                    department_id = COALESCE(department_id, :department_id)
                WHERE id = :id
                """
            ),
            {'id': row[0], 'priority_id': priority_id, 'department_id': department_id},
        )

    assignment_rows = conn.execute(
        text("SELECT id, assigned_user FROM asset_assignments WHERE employee_id IS NULL")
    ).fetchall()
    for row in assignment_rows:
        employee_id = _lookup_id(conn, 'employees', 'assigned_user', row[1], unmatched_tracker)
        conn.execute(
            text("UPDATE asset_assignments SET employee_id = COALESCE(employee_id, :employee_id) WHERE id = :id"),
            {'id': row[0], 'employee_id': employee_id},
        )

    current_assignment_rows = conn.execute(
        text(
            """
            SELECT a.id,
                   (
                       SELECT aa.id
                       FROM asset_assignments aa
                       WHERE aa.asset_id = a.id AND (aa.unassigned_at IS NULL) AND lower(COALESCE(aa.status, 'assigned')) IN ('assigned', 'borrowed')
                       ORDER BY aa.assigned_at DESC, aa.id DESC
                       LIMIT 1
                   ) AS assignment_id
            FROM assets a
            WHERE current_assignment_id IS NULL
            """
        )
    ).fetchall()
    for row in current_assignment_rows:
        if row[1] is not None:
            conn.execute(
                text("UPDATE assets SET current_assignment_id = :assignment_id WHERE id = :id"),
                {'id': row[0], 'assignment_id': row[1]},
            )

    if unmatched_tracker:
        _print_unmatched_summary(unmatched_tracker)


def ensure_schema() -> None:
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
        for statement in legacy_statements:
            try:
                conn.execute(text(statement))
            except Exception:
                pass
        for statement in backfill_statements:
            try:
                conn.execute(text(statement))
            except Exception:
                pass
        ensure_master_tables(conn)
        ensure_fk_columns(conn)
        seed_master_data(conn)
        try:
            conn.execute(text("UPDATE assets SET status = 'assigned' WHERE lower(COALESCE(status, '')) = 'active' AND COALESCE(assigned_user, '') <> ''"))
            conn.execute(text("UPDATE assets SET status = 'in_stock' WHERE lower(COALESCE(status, '')) IN ('active', 'inactive') AND COALESCE(assigned_user, '') = ''"))
            conn.execute(text("UPDATE assets SET status = 'repairing' WHERE lower(COALESCE(status, '')) IN ('in_repair', 'repair', 'repairing', 'broken')"))
            conn.execute(text("UPDATE assets SET status = lower(status) WHERE upper(COALESCE(status, '')) IN ('IN_STOCK', 'ASSIGNED', 'BORROWED', 'REPAIRING', 'RETIRED', 'DISPOSED', 'LOST')"))
        except Exception:
            pass
        backfill_master_data(conn)
        dedupe_master_data(conn)
