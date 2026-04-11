# Session Checkpoint

Updated: 2026-04-11 18:45 GMT+7

## Current runtime status
- App is running successfully on `http://127.0.0.1:8002`
- Login works again with:
  - username: `admin`
  - password: `admin123`
- Forced password change flow works and redirects correctly
- Core smoke test passed for main pages after password change

## What was completed in this session

### 1. Auth and entry flow fixes
- Fixed startup/login access issues so the app can be entered again
- Reset admin password hash so `admin/admin123` works again
- Verified login returns proper `303` redirect with session cookie
- Verified forced password change flow redirects to `/users/change-password?force=1`
- Verified changing password then entering dashboard works

### 2. Auth-focused UI layout
- Added new auth-only layout:
  - `app/templates/auth/auth_focus.html`
- Migrated login page to auth-focused layout
- Migrated forced password change page to auth-focused layout
- Kept normal in-app change password on standard `base.html`

### 3. Phase 1 backend foundation started
Added new master reference models:
- `AssetCategory`
- `AssetStatus`
- `Vendor`
- `IncidentCategory`
- `Priority`
- `MaintenanceType`

Extended existing models with new FK-ready fields:
- `Asset`
  - `category_id`
  - `status_id`
  - `department_id`
  - `location_id`
  - `vendor_id`
  - `current_assignment_id`
- `AssetAssignment`
  - `employee_id`
- `Incident`
  - `category_id`
  - `priority_id`
  - `department_id`
  - `source`
- `Maintenance`
  - `maintenance_type_id`
  - `vendor_id`

### 4. Safe migration scaffold added
`app/db/migrations.py` now includes:
- `ensure_master_tables()`
- `ensure_fk_columns()`
- `seed_master_data()`
- `backfill_master_data()`

Seeded defaults:
- `asset_statuses`: `IN_STOCK`, `ASSIGNED`, `BORROWED`, `REPAIRING`, `RETIRED`, `DISPOSED`, `LOST`
- `priorities`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- `maintenance_types`: `PREVENTIVE`, `CORRECTIVE`

### 5. ORM relationship fixes
- Fixed SQLAlchemy ambiguous FK issue between:
  - `Asset.assignments`
  - `AssetAssignment.asset`

### 6. Template/base fixes
- Fixed broken `has_permission` template dependency path that caused dashboard 500
- Reworked `base.html` nav permission checks to use direct user fields safely

## Smoke test results
Passed after changing password from default:
- `/`
- `/assets/`
- `/maintenance/`
- `/incidents/`
- `/resources/`
- `/documents/`
- `/users/`
- `/master-data/departments`

## Known open issues

### 1. Legacy assignment backfill is incomplete
Startup logs still show many unmatched legacy values for:
- `asset_assignments.assigned_user -> employees`

Examples include generic/group/non-normalized values such as:
- `QC`
- `HR`
- `All user`
- `Driver`
- `Tổ trưởng`
- various inconsistent personal names

This is expected legacy data quality debt, not a startup crash.

### 2. Phase 1 normalization is only partially done
Still pending:
- read fallback logic across routes/templates/helpers
- create/edit write compatibility for FK + legacy string fields
- full unmatched audit report
- better assignment normalization rules
- safe UI dropdown rollout for master data where appropriate

### 3. Temporary credential state
- `admin/admin123` is active only to regain access
- the system forces a password change
- after next login cycle, password may be changed by user, so do not assume `admin123` remains valid

## Recommended next step
Do this next:
1. complete maintenance compatibility layer
2. audit unmatched legacy values into a report
3. then continue assignment normalization cleanup and minimal safe UI rollout

## Progress update after checkpoint creation

### Assets normalization progress
Completed after this checkpoint was first written:
- added fallback display layer for asset type / department / location / status
- asset create/edit/import/bulk update now sets FK fields when mapping succeeds
- preserved all legacy string fields and form payload names
- assignment creation now also attempts `employee_id` mapping and updates `current_assignment_id`
- asset detail page now renders resolved fallback values safely

Smoke-tested after change:
- `/assets/`
- `/assets/new`
- `/assets/1`

### Incidents normalization progress
Completed after this checkpoint was first written:
- added fallback display layer for incident priority and requester department
- incident create/edit now sets `priority_id` and `department_id` when mapping succeeds
- incident form now loads department master-data suggestions
- incident list now renders priority through fallback-aware display values

Smoke-tested after change:
- `/incidents/`
- `/incidents/new`

### Maintenance normalization progress
Completed after this checkpoint was first written:
- added fallback display layer for maintenance type
- maintenance create/edit now sets `maintenance_type_id` when mapping succeeds
- maintenance form now loads maintenance type options from master data
- kept legacy behavior and route signatures intact

Smoke-tested after change:
- `/maintenance/`
- `/maintenance/new`

### Unmatched audit report
Generated report file:
- `docs_phase1_unmatched_report.json`

Current unmatched counts captured:
- asset types: 3
- asset departments: 92
- asset locations: 6
- asset statuses: 1
- incident departments: 1
- incident priorities: 0
- assignment users: 141

### Master data UI expansion
Expanded `master_data` web route config to expose Phase 1 master tables:
- `asset_categories`
- `asset_statuses`
- `vendors`
- `incident_categories`
- `priorities`
- `maintenance_types`

Smoke-tested after change:
- `/master-data/asset_categories`
- `/master-data/asset_statuses`
- `/master-data/priorities`
- `/master-data/maintenance_types`

## Files changed in this session
- `app/db/migrations.py`
- `app/db/models/__init__.py`
- `app/db/models/asset.py`
- `app/db/models/asset_assignment.py`
- `app/db/models/incident.py`
- `app/db/models/maintenance.py`
- `app/db/models/master_reference.py`
- `app/main.py`
- `app/templates/auth/auth_focus.html`
- `app/templates/auth/login.html`
- `app/templates/base.html`
- `app/templates/users/change_password.html`

Also modified earlier in repo and left present:
- `app/routes/web/master_data.py`
- `app/templates/master_data/list.html`

## Notes
- `verify_final.py` is untracked and should be reviewed before commit or removed if temporary.
- Before continuing, use this file plus `git diff` as the source of truth, not chat memory.
