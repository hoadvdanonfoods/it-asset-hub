import re

with open("app/db/migrations.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace DEFAULT 1 and DEFAULT 0
content = re.sub(r'DEFAULT 1', 'DEFAULT true', content)
content = re.sub(r'DEFAULT 0', 'DEFAULT false', content)

# Replace 'SELECT :code, :name, :description, 1, :sort_order'
content = content.replace("SELECT :code, :name, :description, 1, :sort_order", "SELECT :code, :name, :description, true, :sort_order")

# Replace inserts for 'asset_categories', 'departments', 'locations', 'employees'
content = content.replace("SELECT :code, :name, :description, 1, 999", "SELECT :code, :name, :description, true, 999")
content = content.replace("SELECT :code, :name, 1, :note", "SELECT :code, :name, true, :note")

# Fix PRAGMA table_info
old_get_columns = """def _get_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}"""

new_get_columns = """def _get_columns(conn, table_name: str) -> set[str]:
    dialect = conn.engine.dialect.name
    if dialect == 'postgresql':
        rows = conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :table_name"),
            {'table_name': table_name}
        ).fetchall()
        return {row[0] for row in rows}
    else:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {row[1] for row in rows}"""

content = content.replace(old_get_columns, new_get_columns)

with open("app/db/migrations.py", "w", encoding="utf-8") as f:
    f.write(content)

print("migrations.py updated successfully.")
