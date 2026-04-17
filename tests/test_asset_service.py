"""
Unit and integration tests for app/services/asset_service.py.

Unit tests (no DB) use MagicMock for Asset objects.
Integration tests use the `db` fixture from conftest.py (in-memory SQLite).
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from app.services.asset_service import (
    ASSET_STATUSES,
    AssetImportDTO,
    assert_valid_status_transition,
    days_to_warranty,
    normalize_asset_status,
    normalize_text,
    parse_date,
    preview_token_from_rows,
    rows_from_preview_token,
)
from app.db.models import Asset, AssetAssignment, AssetEvent


# ---------------------------------------------------------------------------
# normalize_asset_status
# ---------------------------------------------------------------------------

class TestNormalizeAssetStatus:
    def test_valid_statuses_pass_through(self):
        for status in ASSET_STATUSES:
            assert normalize_asset_status(status) == status

    def test_none_returns_in_stock(self):
        assert normalize_asset_status(None) == 'in_stock'

    def test_empty_string_returns_in_stock(self):
        assert normalize_asset_status('') == 'in_stock'

    def test_unknown_value_returns_in_stock(self):
        assert normalize_asset_status('xyz_unknown_status') == 'in_stock'

    def test_alias_active_to_assigned(self):
        assert normalize_asset_status('active') == 'assigned'

    def test_alias_broken_to_repairing(self):
        assert normalize_asset_status('broken') == 'repairing'

    def test_alias_archive_variants_to_retired(self):
        assert normalize_asset_status('archive') == 'retired'
        assert normalize_asset_status('archived') == 'retired'

    def test_alias_repair_variants(self):
        assert normalize_asset_status('in_repair') == 'repairing'
        assert normalize_asset_status('repair') == 'repairing'
        assert normalize_asset_status('in-repair') == 'repairing'
        assert normalize_asset_status('in repair') == 'repairing'

    def test_alias_instock_variants(self):
        assert normalize_asset_status('instock') == 'in_stock'
        assert normalize_asset_status('in stock') == 'in_stock'
        assert normalize_asset_status('inactive') == 'in_stock'

    def test_case_insensitive(self):
        assert normalize_asset_status('ASSIGNED') == 'assigned'
        assert normalize_asset_status('Active') == 'assigned'
        assert normalize_asset_status('BROKEN') == 'repairing'


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_valid_iso_date(self):
        result = parse_date('2024-12-31')
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31

    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_empty_string_returns_none(self):
        assert parse_date('') is None

    def test_whitespace_only_returns_none(self):
        assert parse_date('   ') is None

    def test_wrong_format_returns_none(self):
        assert parse_date('31/12/2024') is None
        assert parse_date('2024/12/31') is None
        assert parse_date('not-a-date') is None

    def test_invalid_month_returns_none(self):
        assert parse_date('2024-13-01') is None


# ---------------------------------------------------------------------------
# days_to_warranty
# ---------------------------------------------------------------------------

class TestDaysToWarranty:
    def test_future_expiry(self):
        asset = MagicMock()
        asset.warranty_expiry = (datetime.utcnow().date() + timedelta(days=30)).isoformat()
        assert days_to_warranty(asset) == 30

    def test_past_expiry_is_negative(self):
        asset = MagicMock()
        asset.warranty_expiry = (datetime.utcnow().date() - timedelta(days=5)).isoformat()
        assert days_to_warranty(asset) == -5

    def test_no_expiry_returns_none(self):
        asset = MagicMock()
        asset.warranty_expiry = None
        assert days_to_warranty(asset) is None

    def test_invalid_date_returns_none(self):
        asset = MagicMock()
        asset.warranty_expiry = 'not-a-date'
        assert days_to_warranty(asset) is None

    def test_empty_expiry_returns_none(self):
        asset = MagicMock()
        asset.warranty_expiry = ''
        assert days_to_warranty(asset) is None


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_none_returns_empty_string(self):
        assert normalize_text(None) == ''

    def test_strips_whitespace(self):
        assert normalize_text('  hello  ') == 'hello'

    def test_datetime_formats_as_date(self):
        dt = datetime(2024, 3, 15)
        assert normalize_text(dt) == '2024-03-15'

    def test_integer_converts_to_string(self):
        assert normalize_text(42) == '42'

    def test_empty_string_stays_empty(self):
        assert normalize_text('') == ''


# ---------------------------------------------------------------------------
# assert_valid_status_transition
# ---------------------------------------------------------------------------

class TestAssertValidStatusTransition:
    def test_in_stock_to_assigned_is_valid(self):
        assert_valid_status_transition('in_stock', 'assigned')

    def test_assigned_to_in_stock_is_valid(self):
        assert_valid_status_transition('assigned', 'in_stock')

    def test_in_stock_to_repairing_is_valid(self):
        assert_valid_status_transition('in_stock', 'repairing')

    def test_retired_to_in_stock_is_valid(self):
        assert_valid_status_transition('retired', 'in_stock')

    def test_same_status_is_valid(self):
        assert_valid_status_transition('in_stock', 'in_stock')
        assert_valid_status_transition('assigned', 'assigned')

    def test_retired_to_assigned_raises(self):
        with pytest.raises(ValueError, match='Không cho phép'):
            assert_valid_status_transition('retired', 'assigned')

    def test_disposed_to_assigned_raises(self):
        with pytest.raises(ValueError):
            assert_valid_status_transition('disposed', 'assigned')

    def test_none_old_status_treated_as_in_stock(self):
        # None → in_stock → assigned is valid
        assert_valid_status_transition(None, 'assigned')

    def test_alias_in_old_status(self):
        # 'active' aliases to 'assigned'; assigned → in_stock is valid
        assert_valid_status_transition('active', 'in_stock')


# ---------------------------------------------------------------------------
# preview_token roundtrip
# ---------------------------------------------------------------------------

class TestPreviewTokenRoundtrip:
    def test_single_row_roundtrip(self):
        dto = AssetImportDTO(asset_code='TS-001', asset_name='Test Laptop', asset_type='Laptop')
        token = preview_token_from_rows([(2, dto)], 'test.xlsx')
        decoded_rows, filename = rows_from_preview_token(token)
        assert filename == 'test.xlsx'
        assert len(decoded_rows) == 1
        idx, decoded = decoded_rows[0]
        assert idx == 2
        assert decoded.asset_code == 'TS-001'
        assert decoded.asset_name == 'Test Laptop'
        assert decoded.asset_type == 'Laptop'

    def test_multiple_rows_preserve_order(self):
        rows = [
            (2, AssetImportDTO(asset_code='A-001', asset_name='Asset A', asset_type='Laptop')),
            (3, AssetImportDTO(asset_code='B-002', asset_name='Asset B', asset_type='Monitor')),
            (4, AssetImportDTO(asset_code='C-003', asset_name='Asset C', asset_type='Printer')),
        ]
        token = preview_token_from_rows(rows, 'bulk.xlsx')
        decoded_rows, filename = rows_from_preview_token(token)
        assert filename == 'bulk.xlsx'
        assert len(decoded_rows) == 3
        assert decoded_rows[0][1].asset_code == 'A-001'
        assert decoded_rows[2][1].asset_code == 'C-003'

    def test_optional_fields_preserved(self):
        dto = AssetImportDTO(
            asset_code='X-001',
            asset_name='Server',
            asset_type='Server',
            serial_number='SN999',
            department='IT',
            notes='Rack unit 3',
        )
        token = preview_token_from_rows([(5, dto)], 'servers.xlsx')
        decoded_rows, _ = rows_from_preview_token(token)
        decoded = decoded_rows[0][1]
        assert decoded.serial_number == 'SN999'
        assert decoded.department == 'IT'
        assert decoded.notes == 'Rack unit 3'


# ---------------------------------------------------------------------------
# DB integration tests (require `db` fixture from conftest.py)
# ---------------------------------------------------------------------------

class TestLogAssetEvent:
    def test_creates_event_in_db(self, db, test_asset):
        from app.services.asset_service import log_asset_event
        log_asset_event(db, test_asset.id, 'test_event', 'Test Title', 'Some description', 'admin')
        db.flush()
        event = db.query(AssetEvent).filter_by(asset_id=test_asset.id, event_type='test_event').first()
        assert event is not None
        assert event.title == 'Test Title'
        assert event.description == 'Some description'
        assert event.actor == 'admin'

    def test_event_without_description(self, db, test_asset):
        from app.services.asset_service import log_asset_event
        log_asset_event(db, test_asset.id, 'minimal_event', 'No description')
        db.flush()
        event = db.query(AssetEvent).filter_by(asset_id=test_asset.id, event_type='minimal_event').first()
        assert event is not None
        assert event.description is None


class TestSetAssetStatus:
    def test_valid_transition_updates_status(self, db, test_asset):
        from app.services.asset_service import set_asset_status
        old, new = set_asset_status(db, test_asset, 'repairing', 'admin', 'Testing')
        assert old == 'in_stock'
        assert new == 'repairing'
        assert test_asset.status == 'repairing'

    def test_returns_old_and_new_status(self, db, test_asset):
        from app.services.asset_service import set_asset_status
        old, new = set_asset_status(db, test_asset, 'retired', 'admin', 'End of life')
        assert old == 'in_stock'
        assert new == 'retired'

    def test_invalid_transition_raises_value_error(self, db):
        from app.services.asset_service import set_asset_status
        retired_asset = Asset(asset_code='RET-001', asset_name='Retired', asset_type='Laptop', status='retired')
        db.add(retired_asset)
        db.flush()
        with pytest.raises(ValueError, match='Không cho phép'):
            set_asset_status(db, retired_asset, 'assigned', 'admin', 'Should fail')

    def test_same_status_is_idempotent(self, db, test_asset):
        from app.services.asset_service import set_asset_status
        old, new = set_asset_status(db, test_asset, 'in_stock', 'admin', 'No-op')
        assert old == new == 'in_stock'


class TestCreateAssignment:
    def test_creates_assignment_record(self, db, test_asset):
        from app.services.asset_service import create_assignment
        assignment = create_assignment(db, test_asset, 'Nguyen Van A', 'admin', 'Test assign')
        db.flush()
        assert assignment.assigned_user == 'Nguyen Van A'
        assert assignment.status == 'assigned'
        assert test_asset.assigned_user == 'Nguyen Van A'
        assert test_asset.current_assignment_id == assignment.id

    def test_borrow_assignment_has_correct_status(self, db, test_asset):
        from app.services.asset_service import create_assignment
        assignment = create_assignment(db, test_asset, 'Tran Thi B', 'admin', 'Borrow', assignment_status='borrowed')
        db.flush()
        assert assignment.status == 'borrowed'

    def test_logs_assigned_event(self, db, test_asset):
        from app.services.asset_service import create_assignment
        create_assignment(db, test_asset, 'Le Van C', 'admin', 'Assign event test')
        db.flush()
        event = db.query(AssetEvent).filter_by(asset_id=test_asset.id, event_type='assigned').first()
        assert event is not None


class TestCloseActiveAssignment:
    def test_closes_assignment_and_clears_asset(self, db):
        from app.services.asset_service import close_active_assignment
        asset = Asset(asset_code='CLO-001', asset_name='Asset to close', asset_type='Laptop', status='assigned', assigned_user='User X')
        db.add(asset)
        db.flush()
        assignment = AssetAssignment(asset_id=asset.id, assigned_user='User X', assigned_by='admin', status='assigned')
        db.add(assignment)
        db.flush()
        asset.current_assignment_id = assignment.id

        previous_user = close_active_assignment(db, asset, 'admin', 'Test close')
        db.flush()

        assert previous_user == 'User X'
        assert asset.assigned_user is None
        assert asset.current_assignment_id is None
        assert assignment.status == 'returned'

    def test_returns_previous_user(self, db):
        from app.services.asset_service import close_active_assignment
        asset = Asset(asset_code='CLO-002', asset_name='Asset', asset_type='Laptop', status='assigned', assigned_user='User Y')
        db.add(asset)
        db.flush()

        result = close_active_assignment(db, asset, 'admin', 'Close test')
        assert result == 'User Y'


class TestFilteredAssets:
    def test_excludes_cameras_by_default(self, db):
        from app.services.asset_service import filtered_assets
        laptop = Asset(asset_code='FLT-L01', asset_name='Filter Laptop', asset_type='Laptop', status='in_stock')
        camera = Asset(asset_code='FLT-C01', asset_name='Filter Camera', asset_type='Camera', status='in_stock')
        db.add_all([laptop, camera])
        db.flush()

        results = filtered_assets(db)
        codes = [a.asset_code for a in results]
        assert 'FLT-L01' in codes
        assert 'FLT-C01' not in codes

    def test_filter_by_status(self, db):
        from app.services.asset_service import filtered_assets
        a1 = Asset(asset_code='FLT-S01', asset_name='In Stock', asset_type='Laptop', status='in_stock')
        a2 = Asset(asset_code='FLT-S02', asset_name='Retired', asset_type='Laptop', status='retired')
        db.add_all([a1, a2])
        db.flush()

        results = filtered_assets(db, status='in_stock')
        codes = [a.asset_code for a in results]
        assert 'FLT-S01' in codes
        assert 'FLT-S02' not in codes

    def test_search_by_code(self, db):
        from app.services.asset_service import filtered_assets
        asset = Asset(asset_code='UNIQUE-XYZ', asset_name='Unique Asset', asset_type='Server', status='in_stock')
        db.add(asset)
        db.flush()

        results = filtered_assets(db, q='UNIQUE-XYZ')
        assert any(a.asset_code == 'UNIQUE-XYZ' for a in results)

    def test_filter_by_department(self, db):
        from app.services.asset_service import filtered_assets
        a1 = Asset(asset_code='FLT-D01', asset_name='IT Asset', asset_type='Laptop', status='in_stock', department='IT')
        a2 = Asset(asset_code='FLT-D02', asset_name='HR Asset', asset_type='Laptop', status='in_stock', department='HR')
        db.add_all([a1, a2])
        db.flush()

        results = filtered_assets(db, department='IT')
        codes = [a.asset_code for a in results]
        assert 'FLT-D01' in codes
        assert 'FLT-D02' not in codes
