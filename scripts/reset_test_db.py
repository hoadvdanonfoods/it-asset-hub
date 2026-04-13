#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from app.config import DATA_DIR, DATABASE_URL


def sqlite_db_path() -> Path:
    prefix = 'sqlite:///'
    if not DATABASE_URL.startswith(prefix):
        raise SystemExit(f'Reset script currently supports SQLite only. DATABASE_URL={DATABASE_URL}')
    raw_path = DATABASE_URL[len(prefix):]
    return Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(description='Reset local test database for IT Asset Hub.')
    parser.add_argument('--no-backup', action='store_true', help='Do not create a backup before reset')
    parser.add_argument('--clear-uploads', action='store_true', help='Also remove uploaded files under data/uploads')
    parser.add_argument('--clear-camera-checklists', action='store_true', help='Also remove generated camera checklist files')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    db_path = sqlite_db_path()
    if not db_path.is_absolute():
        db_path = (repo_root / db_path).resolve()

    data_dir = DATA_DIR if DATA_DIR.is_absolute() else (repo_root / DATA_DIR).resolve()
    backups_dir = data_dir / 'backups'
    uploads_dir = data_dir / 'uploads'
    checklist_dir = data_dir / 'camera_checklists'

    data_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)

    if db_path.exists() and not args.no_backup:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = backups_dir / f'{db_path.stem}-before-reset-{timestamp}{db_path.suffix}'
        shutil.copy2(db_path, backup_path)
        print(f'Backed up DB to: {backup_path}')

    if db_path.exists():
        db_path.unlink()
        print(f'Removed DB: {db_path}')
    else:
        print(f'DB not found, nothing to remove: {db_path}')

    if args.clear_uploads and uploads_dir.exists():
        shutil.rmtree(uploads_dir)
        uploads_dir.mkdir(parents=True, exist_ok=True)
        print(f'Cleared uploads: {uploads_dir}')

    if args.clear_camera_checklists and checklist_dir.exists():
        shutil.rmtree(checklist_dir)
        checklist_dir.mkdir(parents=True, exist_ok=True)
        print(f'Cleared camera checklists: {checklist_dir}')

    from app.main import app  # noqa: F401
    print('Reinitialized schema successfully.')
    print(f'Fresh DB ready at: {db_path}')
    print('Default local login should follow current app bootstrap rules.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
