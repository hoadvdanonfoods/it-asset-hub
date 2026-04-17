from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import base64
import io
import json

import openpyxl
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Asset,
    AssetAssignment,
    AssetEvent,
    AssetStatusHistory,
    AssetType,
    Department,
    Employee,
    Location,
    AssetStatus,
)

DATE_FMT = '%Y-%m-%d'

ASSET_STATUSES = ['in_stock', 'assigned', 'borrowed', 'repairing', 'retired', 'disposed', 'lost']
ASSET_STATUS_TRANSITIONS = {
    'in_stock': {'in_stock', 'assigned', 'borrowed', 'repairing', 'retired', 'disposed', 'lost'},
    'assigned': {'assigned', 'repairing', 'in_stock', 'retired', 'disposed', 'lost', 'borrowed'},
    'borrowed': {'borrowed', 'in_stock', 'repairing', 'retired', 'disposed', 'lost', 'assigned'},
    'repairing': {'repairing', 'in_stock', 'retired', 'disposed', 'lost', 'assigned'},
    'retired': {'retired', 'in_stock'},
    'disposed': {'disposed', 'in_stock'},
    'lost': {'lost', 'in_stock'},
}
STATUS_LABELS = {
    'in_stock': 'In Stock',
    'assigned': 'Assigned',
    'borrowed': 'Borrowed',
    'repairing': 'Repairing',
    'retired': 'Retired',
    'disposed': 'Disposed',
    'lost': 'Lost',
}
IMPORT_HEADERS = [
    'Mã thiết bị',
    'Tên thiết bị',
    'Loại thiết bị',
    'Model',
    'Serial',
    'IP',
    'Bộ phận',
    'Người dùng',
    'Vị trí',
    'Ngày mua',
    'Hết bảo hành',
    'Trạng thái',
    'Ghi chú',
]
REQUIRED_IMPORT_HEADERS = ['Mã thiết bị', 'Tên thiết bị', 'Loại thiết bị']


@dataclass
class AssetImportDTO:
    asset_code: str
    asset_name: str
    asset_type: str
    model: str | None = None
    serial_number: str | None = None
    ip_address: str | None = None
    department: str | None = None
    assigned_user: str | None = None
    location: str | None = None
    purchase_date: str | None = None
    warranty_expiry: str | None = None
    status: str = 'active'
    notes: str | None = None

    @classmethod
    def from_row(cls, row_map: dict[str, str]):
        return cls(
            asset_code=row_map.get('Mã thiết bị', '').strip(),
            asset_name=row_map.get('Tên thiết bị', '').strip(),
            asset_type=row_map.get('Loại thiết bị', '').strip(),
            model=row_map.get('Model', '').strip() or None,
            serial_number=row_map.get('Serial', '').strip() or None,
            ip_address=row_map.get('IP', '').strip() or None,
            department=row_map.get('Bộ phận', '').strip() or None,
            assigned_user=row_map.get('Người dùng', '').strip() or None,
            location=row_map.get('Vị trí', '').strip() or None,
            purchase_date=row_map.get('Ngày mua', '').strip() or None,
            warranty_expiry=row_map.get('Hết bảo hành', '').strip() or None,
            status=normalize_asset_status(row_map.get('Trạng thái', '').strip() or 'in_stock'),
            notes=row_map.get('Ghi chú', '').strip() or None,
        )


# ---------------------------------------------------------------------------
# Pure utilities (no DB)
# ---------------------------------------------------------------------------

def normalize_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime(DATE_FMT)
    return str(value).strip()


def normalize_asset_status(value: str | None) -> str:
    raw = (value or '').strip().lower()
    aliases = {
        'active': 'assigned',
        'inactive': 'in_stock',
        'in_repair': 'repairing',
        'repair': 'repairing',
        'in-repair': 'repairing',
        'in repair': 'repairing',
        'broken': 'repairing',
        'archive': 'retired',
        'archived': 'retired',
        'instock': 'in_stock',
        'in stock': 'in_stock',
    }
    normalized = aliases.get(raw, raw or 'in_stock')
    return normalized if normalized in ASSET_STATUSES else 'in_stock'


def parse_date(value: str | None):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except ValueError:
        return None


def days_to_warranty(asset: Asset) -> int | None:
    expiry = parse_date(asset.warranty_expiry)
    if not expiry:
        return None
    return (expiry - datetime.utcnow().date()).days


def assert_valid_status_transition(old_status: str | None, new_status: str | None) -> None:
    current = normalize_asset_status(old_status)
    target = normalize_asset_status(new_status)
    allowed = ASSET_STATUS_TRANSITIONS.get(current, {current})
    if target not in allowed:
        raise ValueError(f'Không cho phép chuyển trạng thái từ {current} sang {target}.')


def preview_token_from_rows(rows: list[tuple[int, AssetImportDTO]], filename: str) -> str:
    payload = {'filename': filename, 'rows': [(idx, asdict(dto)) for idx, dto in rows]}
    return base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode('utf-8')).decode('ascii')


def rows_from_preview_token(token: str) -> tuple[list[tuple[int, AssetImportDTO]], str]:
    decoded = base64.urlsafe_b64decode(token.encode('ascii'))
    payload = json.loads(decoded.decode('utf-8'))
    return [(int(item[0]), AssetImportDTO(**item[1])) for item in payload['rows']], payload.get('filename', 'import.xlsx')


# ---------------------------------------------------------------------------
# DB resolvers (read-only queries)
# ---------------------------------------------------------------------------

def resolve_department_id(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return None
    return db.scalar(select(Department.id).where(or_(Department.name == raw, Department.code == raw)).limit(1))


def resolve_asset_type_value(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return '', None
    row = db.execute(select(AssetType.id, AssetType.name).where(or_(AssetType.name == raw, AssetType.code == raw)).limit(1)).first()
    if row:
        return row[1], row[0]
    return raw, None


def resolve_location_id(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return None
    return db.scalar(select(Location.id).where(or_(Location.name == raw, Location.code == raw)).limit(1))


def resolve_status_value(db: Session, value: str | None):
    normalized = normalize_asset_status(value)
    row = db.execute(select(AssetStatus.id, AssetStatus.code).where(or_(AssetStatus.code == normalized, AssetStatus.code == normalized.upper(), AssetStatus.name == value)).limit(1)).first()
    return normalized, (row[0] if row else None)


def resolve_employee_id(db: Session, value: str | None):
    raw = (value or '').strip()
    if not raw:
        return None
    return db.scalar(select(Employee.id).where(or_(Employee.full_name == raw, Employee.employee_code == raw)).limit(1))


def allowed_transitions_for(asset: Asset | None) -> set[str]:
    current = normalize_asset_status(getattr(asset, 'status', None) if asset else None)
    return ASSET_STATUS_TRANSITIONS.get(current, {current})


def get_active_assignment(db: Session, asset: Asset) -> AssetAssignment | None:
    return db.scalar(
        select(AssetAssignment)
        .where(AssetAssignment.asset_id == asset.id, AssetAssignment.status.in_(['assigned', 'borrowed']))
        .order_by(AssetAssignment.assigned_at.desc())
    )


def filtered_assets(db: Session, q: str | None = None, asset_type: str | None = None, department: str | None = None, status: str | None = None, warranty: str | None = None, filter: str | None = None):
    stmt = select(Asset)
    if q:
        like = f'%{q.strip()}%'
        stmt = stmt.where(or_(Asset.asset_code.ilike(like), Asset.asset_name.ilike(like), Asset.ip_address.ilike(like), Asset.assigned_user.ilike(like), Asset.serial_number.ilike(like)))
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    else:
        stmt = stmt.where(Asset.asset_type != 'Camera')
    if department:
        stmt = stmt.where(Asset.department == department)
    if status:
        stmt = stmt.where(Asset.status == status)
    if filter == 'missing_info':
        stmt = stmt.where(or_(Asset.serial_number.is_(None), Asset.serial_number == '', Asset.location.is_(None), Asset.location == ''))
    if warranty:
        today_str = datetime.utcnow().date().isoformat()
        stmt = stmt.where(Asset.warranty_expiry.is_not(None), Asset.warranty_expiry != '')
        if warranty == 'expired':
            stmt = stmt.where(Asset.warranty_expiry < today_str)
        elif warranty == 'expiring_30':
            stmt = stmt.where(Asset.warranty_expiry.between(today_str, (datetime.utcnow().date() + timedelta(days=30)).isoformat()))
        elif warranty == 'expiring_90':
            stmt = stmt.where(Asset.warranty_expiry.between(today_str, (datetime.utcnow().date() + timedelta(days=90)).isoformat()))
    return db.scalars(stmt.order_by(Asset.asset_code.asc())).all()


def load_import_rows(file_bytes: bytes) -> list[tuple[int, AssetImportDTO]]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError('File import đang rỗng.')
    headers = [normalize_text(value) for value in rows[0]]
    missing_headers = [name for name in REQUIRED_IMPORT_HEADERS if name not in headers]
    if missing_headers:
        raise ValueError(f'Thiếu cột bắt buộc: {", ".join(missing_headers)}')
    dtos = []
    for index, row in enumerate(rows[1:], start=2):
        row_map: dict[str, str] = {}
        has_data = False
        for header, cell in zip(headers, row):
            if not header:
                continue
            value = normalize_text(cell)
            if value:
                has_data = True
            row_map[header] = value
        if not has_data:
            continue
        dtos.append((index, AssetImportDTO.from_row(row_map)))
    return dtos


def build_import_preview(rows: list[tuple[int, AssetImportDTO]], db: Session, filename: str) -> dict:
    created = 0
    updated = 0
    skipped: list[str] = []
    sample_rows = []
    for row_number, dto in rows:
        if not dto.asset_code or not dto.asset_name or not dto.asset_type:
            skipped.append(f'Dòng {row_number}: thiếu Mã thiết bị / Tên thiết bị / Loại thiết bị')
            sample_rows.append({'row_number': row_number, 'asset_code': dto.asset_code, 'asset_name': dto.asset_name, 'asset_type': dto.asset_type, 'action': 'skip'})
            continue
        asset = db.scalar(select(Asset).where(Asset.asset_code == dto.asset_code))
        action = 'update' if asset else 'create'
        if action == 'create':
            created += 1
        else:
            updated += 1
        if len(sample_rows) < 20:
            sample_rows.append({'row_number': row_number, 'asset_code': dto.asset_code, 'asset_name': dto.asset_name, 'asset_type': dto.asset_type, 'action': action})
    return {
        'filename': filename,
        'created': created,
        'updated': updated,
        'skipped': skipped[:30],
        'total_rows': len(rows),
        'sample_rows': sample_rows,
        'token': preview_token_from_rows(rows, filename),
    }


# ---------------------------------------------------------------------------
# Core business logic (DB writes)
# ---------------------------------------------------------------------------

def log_asset_event(db: Session, asset_id: int, event_type: str, title: str, description: str | None = None, actor: str | None = None) -> None:
    db.add(AssetEvent(asset_id=asset_id, event_type=event_type, title=title, description=description, actor=actor))


def record_status_history(db: Session, asset: Asset, old_status: str | None, old_status_id: int | None, new_status: str | None, new_status_id: int | None, actor: str | None, note: str | None = None) -> None:
    normalized_old = normalize_asset_status(old_status)
    normalized_new = normalize_asset_status(new_status)
    if normalized_old == normalized_new and old_status_id == new_status_id:
        return
    db.add(AssetStatusHistory(
        asset_id=asset.id,
        old_status_id=old_status_id,
        new_status_id=new_status_id,
        old_status_code=normalized_old,
        new_status_code=normalized_new,
        changed_by=actor,
        note=note,
    ))


def close_active_assignment(db: Session, asset: Asset, actor: str | None, source: str, close_status: str = 'returned') -> str | None:
    now_dt = datetime.utcnow()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M')
    current_assignment = get_active_assignment(db, asset)
    previous_user = asset.assigned_user
    if current_assignment:
        current_assignment.status = close_status
        current_assignment.unassigned_at = now_dt
        current_assignment.returned_by = actor
    elif previous_user:
        fallback = AssetAssignment(
            asset_id=asset.id,
            employee_id=resolve_employee_id(db, previous_user),
            assigned_user=previous_user,
            assigned_by=actor,
            assigned_at=now_dt,
            unassigned_at=now_dt,
            returned_by=actor,
            note=f'{source} (đóng cấp phát lệch dữ liệu)',
            status=close_status,
        )
        db.add(fallback)
    if previous_user:
        title = 'Thu hồi asset' if close_status == 'returned' else 'Kết thúc mượn asset'
        event_type = 'returned' if close_status == 'returned' else 'borrow_returned'
        log_asset_event(db, asset.id, event_type, title, f'Thu hồi từ {previous_user} ({source})', actor)
    asset.current_assignment_id = None
    asset.assigned_user = None
    asset.unassigned_at = now_str
    return previous_user


def create_assignment(db: Session, asset: Asset, new_user: str, actor: str | None, source: str, assignment_status: str = 'assigned') -> AssetAssignment:
    now_dt = datetime.utcnow()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M')
    assignment = AssetAssignment(
        asset_id=asset.id,
        employee_id=resolve_employee_id(db, new_user),
        assigned_user=new_user,
        assigned_by=actor,
        assigned_at=now_dt,
        note=source,
        status=assignment_status,
    )
    db.add(assignment)
    db.flush()
    asset.current_assignment_id = assignment.id
    asset.assigned_user = new_user
    asset.assigned_at = now_str
    asset.unassigned_at = None
    title = 'Cấp phát asset' if assignment_status == 'assigned' else 'Cho mượn asset'
    event_type = 'assigned' if assignment_status == 'assigned' else 'borrowed'
    log_asset_event(db, asset.id, event_type, title, f'Gán cho {new_user} ({source})', actor)
    return assignment


def apply_assignment_change(db: Session, asset: Asset, new_user: str | None, actor: str | None, source: str) -> None:
    previous_user = asset.assigned_user
    if previous_user == new_user:
        return
    if previous_user:
        close_active_assignment(db, asset, actor, source, close_status='returned')
    if new_user:
        create_assignment(db, asset, new_user, actor, source, assignment_status='assigned')


def set_asset_status(db: Session, asset: Asset, target_status: str | None, actor: str | None, note: str | None = None) -> tuple[str, str]:
    old_status = asset.status
    old_status_id = asset.status_id
    normalized_status, status_id = resolve_status_value(db, target_status)
    assert_valid_status_transition(old_status, normalized_status)
    if normalized_status in {'retired', 'disposed', 'lost', 'in_stock'} and getattr(asset, 'assigned_user', None):
        close_status = 'returned' if normalized_status == 'in_stock' else 'retired'
        close_active_assignment(db, asset, actor, note or f'Đổi trạng thái sang {normalized_status}', close_status=close_status)
    asset.status = normalized_status
    asset.status_id = status_id
    record_status_history(db, asset, old_status, old_status_id, normalized_status, status_id, actor, note)
    return old_status, normalized_status


def commit_import_rows(rows: list[tuple[int, AssetImportDTO]], db: Session, actor: str) -> dict:
    created = 0
    updated = 0
    skipped: list[str] = []
    for row_number, dto in rows:
        if not dto.asset_code or not dto.asset_name or not dto.asset_type:
            skipped.append(f'Dòng {row_number}: thiếu Mã thiết bị / Tên thiết bị / Loại thiết bị')
            continue
        asset = db.scalar(select(Asset).where(Asset.asset_code == dto.asset_code))
        if not asset:
            now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M') if dto.assigned_user else None
            asset_type_value, category_id = resolve_asset_type_value(db, dto.asset_type)
            requested_status = 'assigned' if dto.assigned_user and normalize_asset_status(dto.status) == 'in_stock' else dto.status
            status_value, status_id = resolve_status_value(db, requested_status)
            asset_data = asdict(dto)
            asset_data['asset_type'] = asset_type_value
            asset_data['category_id'] = category_id
            asset_data['department_id'] = resolve_department_id(db, dto.department)
            asset_data['location_id'] = resolve_location_id(db, dto.location)
            asset_data['status'] = status_value
            asset_data['status_id'] = status_id
            asset_data['assigned_at'] = now_str
            asset = Asset(**asset_data)
            db.add(asset)
            db.flush()
            log_asset_event(db, asset.id, 'asset_imported', 'Import asset mới', f'Import từ Excel: {asset.asset_code}', actor)
            if dto.assigned_user:
                assignment = AssetAssignment(
                    asset_id=asset.id,
                    employee_id=resolve_employee_id(db, dto.assigned_user),
                    assigned_user=dto.assigned_user,
                    assigned_by=actor,
                    note='Import từ Excel',
                )
                db.add(assignment)
                db.flush()
                asset.current_assignment_id = assignment.id
                log_asset_event(db, asset.id, 'assigned', 'Cấp phát asset', f'Gán cho {dto.assigned_user} (import Excel)', actor)
            created += 1
            continue
        previous_user = asset.assigned_user
        asset.asset_name = dto.asset_name
        asset.asset_type, asset.category_id = resolve_asset_type_value(db, dto.asset_type)
        asset.model = dto.model
        asset.serial_number = dto.serial_number
        asset.ip_address = dto.ip_address
        asset.department = dto.department
        asset.department_id = resolve_department_id(db, dto.department)
        asset.location = dto.location
        asset.location_id = resolve_location_id(db, dto.location)
        asset.purchase_date = dto.purchase_date
        asset.warranty_expiry = dto.warranty_expiry
        requested_status = 'assigned' if dto.assigned_user and normalize_asset_status(dto.status) == 'in_stock' else dto.status
        previous_status, current_status = set_asset_status(db, asset, requested_status, actor, 'Import từ Excel')
        asset.notes = dto.notes
        apply_assignment_change(db, asset, dto.assigned_user, actor, 'Import từ Excel')
        if previous_user == dto.assigned_user:
            asset.assigned_user = dto.assigned_user
        if previous_status != current_status:
            log_asset_event(db, asset.id, 'asset_status_changed', 'Đổi trạng thái asset', f'{previous_status} -> {current_status}', actor)
        log_asset_event(db, asset.id, 'asset_imported', 'Cập nhật asset từ import', f'Cập nhật từ Excel: {asset.asset_code}', actor)
        updated += 1
    db.commit()
    return {'created': created, 'updated': updated, 'skipped': skipped, 'total_rows': len(rows)}
