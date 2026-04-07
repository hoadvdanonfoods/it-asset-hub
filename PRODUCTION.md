# Deployment Guide: IT Asset Hub on PostgreSQL

This guide describes how to deploy the IT Asset Hub using PostgreSQL instead of the default SQLite database.

## 1. Prerequisites
- **PostgreSQL Server**: Version 13 or higher.
- **Python Driver**: Install `psycopg2-binary` or `psycopg2`.
  ```bash
  pip install psycopg2-binary
  ```

## 2. Database Configuration
Set the `DATABASE_URL` environment variable using the standard PostgreSQL format:
```bash
# Template
DATABASE_URL="postgresql://user:password@host:port/dbname"

# Example
DATABASE_URL="postgresql://admin:secret@localhost:5432/it_asset_hub"
```

The application automatically detects the database type and:
- Enables connection pooling (`pool_size=5`, `max_overflow=10`).
- Enables `pool_pre_ping` to ensure stale connections are dropped.
- Switches to case-insensitive searches using `.ilike()`.

## 3. Database Migration
If you are moving from SQLite to PostgreSQL:
1. **Initialize the Schema**: Use Alembic to create the tables.
   ```bash
   alembic upgrade head
   ```
2. **Data Migration**: To migrate existing data, we recommend using a data mapping tool like `pgloader` or a custom script, as SQLite and PostgreSQL have different SQL dialects for bulk inserts.

## 4. Backup & Maintenance
The built-in "Backup" feature in the System menu is designed for SQLite only. For PostgreSQL deployments:
- **Daily Backups**: Use `pg_dump` via a cron job.
  ```bash
  pg_dump -U user -d dbname > backup.sql
  ```
- **Restore**: Use `psql`.
  ```bash
  psql -U user -d dbname < backup.sql
  ```

## 5. Deployment Considerations
- **Search Performance**: PostgreSQL's `ILIKE` is powerful. For extremely large datasets (>100k assets), consider adding indexes on columns like `asset_code` and `serial_number`.
- **SSL**: If connecting to a remote database (e.g., AWS RDS or Supabase), append `?sslmode=require` to your `DATABASE_URL`.
