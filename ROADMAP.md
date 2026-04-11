# IT Asset Hub Roadmap V2.1

## 🎯 Vision

Build an internal IT operations platform that goes beyond basic asset tracking:

- Centralized IT asset management (CMDB-lite)
- Predictable asset lifecycle and assignment tracking
- Incident and maintenance workflow management
- Operational checklist and compliance visibility
- Reporting, auditability, and admin traceability

---

## 📌 Product Principles

- Avoid breaking the existing system, prefer backward-compatible changes
- Prefer incremental migration over big refactor
- Standardize data before adding complex features
- Keep UI simple and consistent, prioritize usability for IT admin
- Every feature must solve a real operational problem
- Refactor only where it improves reliability, maintainability, or reuse

---

## 🚦 Priority Model

### MUST
Critical for correctness, security, maintainability, or future scalability.  
These should not be skipped.

### SHOULD
Important and valuable, should be done early if timeline allows.

### NICE TO HAVE
Useful improvements, but can wait until core flow is stable.

---

# Phase 0 — Stabilization & Safety Baseline (MUST)

## Goals
- Make the codebase safe to extend
- Remove insecure defaults
- Reduce regression risk before adding major features

## Refactor Constraints
**MUST**
During Phase 0:

- Do NOT change API response format
- Do NOT change route paths
- Do NOT change route signatures
- Do NOT change template structure unless necessary
- Keep backward compatibility for all existing flows
- Do NOT attempt full rewrite of existing modules
- Refactor only high-risk or high-logic parts incrementally

## Tasks

### 1. Repo & Project Structure
**MUST**
- Standardize project layout
- Remove dead/temporary files
- Group web routes, services, templates, migrations clearly
- Define folder conventions for:
  - `routes`
  - `services`
  - `db/models`
  - `templates`
  - `static`
  - `docs`

### 2. Config & Environment
**MUST**
- Standardize `.env` and config loading
- Require `SECRET_KEY` from env in non-dev mode
- Document required env vars
- Separate dev/test/prod config behavior

### 3. Security Baseline
**MUST**
- Remove insecure default admin behavior
- Disable unsafe default credentials in production
- Add session timeout
- Review auth/session cookie settings
- Ensure permission checks are consistently applied

### 4. Route/Service Refactor Boundary
**MUST**
Start refactor from:
- `app/routes/web/assets.py`
- then `incidents.py`
- then `maintenance.py`

Move only high-logic parts to services:
- asset lifecycle transitions
- assignment logic
- import/export logic
- dashboard aggregations
- audit write hooks

Avoid full rewrite of all routes at once.

### 5. UI Consistency Baseline
**SHOULD**
- Normalize layout and component patterns across:
  - list pages
  - forms
  - action buttons
  - modal/dialog behavior
  - sidebar / mobile nav
- Eliminate one-off template drift

### 6. Developer Setup
**MUST**
- Add/update:
  - internal README
  - developer setup guide
  - run instructions
  - migration instructions
  - seed instructions
  - backup/restore notes

### 7. Smoke Testing Baseline
**MUST**
Add minimum smoke test coverage for:
- login/auth flow
- key route rendering
- permission-protected routes
- import/export entry points
- template rendering for main modules

### 8. Observability Baseline
**SHOULD**
- Add structured logging baseline
- Add startup health logging
- Add basic error logging standard
- Add slow query detection (basic)
- Add simple metrics/health tracking where feasible

---

# Phase 1 — Data Foundation & Master Data (MUST)

## Goals
- Standardize the data model
- Prepare for scalable features without breaking legacy data
- Reduce hardcoded business values

## Migration Safety Rules
**MUST**
- All migrations must be idempotent
- Always backup database before running migration
- Backfill must log unmatched values
- Provide rollback or manual fix strategy for mapping errors

## Tasks

### 1. Master Data Tables
**MUST**
Create and standardize:
- asset_category
- asset_status
- department
- location
- vendor
- incident_category
- priority
- maintenance_type

### 2. Foreign Key Introduction
**MUST**
Add FK fields without deleting current string fields.

#### assets
- category_id
- status_id
- department_id
- location_id
- vendor_id

#### incidents
- category_id
- priority_id
- department_id
- source

#### maintenance
- maintenance_type_id
- vendor_id

### 3. Migration Strategy
**MUST**
- Keep old string fields temporarily
- Add new FK fields
- Backfill from legacy values
- Add fallback read logic
- Make migration idempotent where possible
- Log unmatched legacy values for cleanup
- Backup database before migration

### 4. Seed Data
**MUST**
Seed at least:
- statuses: `IN_STOCK`, `ASSIGNED`, `BORROWED`, `REPAIRING`, `RETIRED`, `DISPOSED`, `LOST`
- categories: `LAPTOP`, `DESKTOP`, `PRINTER`, `CAMERA`, `NETWORK`, etc.
- priorities: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- maintenance types: `PREVENTIVE`, `CORRECTIVE`
- incident sources:
  - `USER_REPORT`
  - `MONITORING`
  - `CHECKLIST`
  - `SYSTEM_GENERATED`

### 5. UI Transition
**SHOULD**
- Gradually replace text fields with dropdowns
- Continue displaying legacy values during migration period
- Avoid breaking forms while backfill is incomplete

### 6. Data Quality Checks
**SHOULD**
- Flag unmapped department/category/status values
- Add admin visibility into incomplete mapping
- Provide manual cleanup path

---

# Phase 2 — Asset Lifecycle & Assignment (MUST)

## Goals
- Make asset state predictable
- Track ownership and operational responsibility
- Build reliable history

## Domain Decisions
**MUST**
Adopt these rules unless revised explicitly:

- Assignment primary relation = **asset -> employee**
- Department is **derived or snapshotted**, not the primary ownership relation
- `borrowed` is a subtype/state of assignment, not a separate system
- Assignment history stores **snapshot data** at time of change:
  - employee name
  - department
  - asset code/name
  - changed_by
  - changed_at

## Single Source of Truth
**MUST**
- `Asset.current_assignment_id` is the single source of truth
- `Asset.assigned_user` (legacy) is deprecated and used only for backward compatibility
- Assignment table is the historical source of truth
- Avoid maintaining conflicting ownership state in multiple places

## Tasks

### 1. Asset Lifecycle Model
**MUST**
Define valid asset states:
- `IN_STOCK`
- `ASSIGNED`
- `BORROWED`
- `REPAIRING`
- `RETIRED`
- `DISPOSED`
- `LOST`

### 2. Status Transition Rules
**MUST**
Define allowed transitions explicitly, for example:
- `IN_STOCK -> ASSIGNED`
- `IN_STOCK -> BORROWED`
- `ASSIGNED -> REPAIRING`
- `REPAIRING -> IN_STOCK`
- `ASSIGNED -> RETIRED`
- `ASSIGNED -> LOST`

Add server-side validation so invalid transitions are blocked.

### 3. Asset Status History
**MUST**
Create:
- `asset_status_history`
  - asset_id
  - old_status_id
  - new_status_id
  - changed_by
  - changed_at
  - note

### 4. Assignment Module
**MUST**
Support:
- assign
- return
- transfer
- borrow / return borrowed item

Rules:
- one active assignment per asset
- assignment tied to employee
- capture snapshot of assignee metadata
- preserve full history

### 5. UI
**SHOULD**
Asset detail page should show:
- current owner
- current status
- assignment history
- status history

Actions:
- Assign
- Return
- Transfer
- Move to repair / restore

---

# Phase 3 — Incident & Maintenance (MUST)

## Goals
- Track support issues and repair workflow
- Improve IT operational response

## Tasks

### 1. Incident System
**MUST**
Add:
- category FK
- priority FK
- asset link
- requester link
- assignee link
- source

Recommended source values:
- `USER_REPORT`
- `MONITORING`
- `CHECKLIST`
- `SYSTEM_GENERATED`

Define status flow:
- `open -> in_progress -> resolved -> closed`

### 2. Maintenance System
**MUST**
Add:
- maintenance_type (`PREVENTIVE`, `CORRECTIVE`)
- vendor link
- cost
- downtime
- result
- related asset
- optional related incident

### 3. SLA (Basic)
**SHOULD**
- Define expected resolution time by priority
- Flag overdue incidents
- Show overdue state in dashboard/list

### 4. Vendor Usage
**SHOULD**
Link vendor to:
- maintenance
- asset (optional)
- incident escalation (optional later)

### 5. Warranty & Repair Tracking
**SHOULD**
- warranty expiry visibility
- repair cost accumulation
- repair history by asset

---

# Phase 4 — Operational Features & Notifications (SHOULD)

## Goals
- Support real daily IT operations
- Surface actionable alerts

## Tasks

### 1. Checklist Module
**SHOULD**
Support:
- daily
- weekly
- monthly checklist

Track:
- performed_by
- result (`pass/fail/warning`)
- note
- performed_at

### 2. Compliance Checks
**SHOULD**
Detect:
- assets without owner
- assets without serial
- expired warranty
- overdue maintenance
- inconsistent status/assignment

### 3. Event-Driven Notification Model
**SHOULD**
Define domain events first.

Recommended event types:
- `ASSET_STATUS_CHANGED`
- `ASSET_ASSIGNED`
- `ASSET_RETURNED`
- `INCIDENT_CREATED`
- `INCIDENT_OVERDUE`
- `WARRANTY_EXPIRING`
- `MAINTENANCE_OVERDUE`
- `CHECKLIST_FAILED`

### 4. Notification Delivery
**SHOULD**
Support:
- Zalo
- Email

### 5. Notification Rules
**MUST**
Add explicit throttling and dedup rules:
- max X notifications / hour / event type
- deduplicate by `(event_type, asset_id)` or `(event_type, incident_id)`
- retry with limit
- log delivery result
- cooldown for repeated alerts where needed

---

# Phase 5 — Dashboard, Reports & Visibility (SHOULD)

## Goals
- Provide operational visibility
- Support decision-making and monthly review

## Tasks

### 1. Dashboard
**SHOULD**
Show:
- assets by status
- assets by department
- incidents by category/priority/source
- maintenance overdue
- compliance warnings

### 2. Reports
**SHOULD**
Add:
- monthly incident summary
- repair cost report
- asset inventory by department
- overdue maintenance report
- warranty expiry report

### 3. Export
**SHOULD**
- Excel export with filters
- report by month / department / status
- preserve legacy compatibility where needed

---

# Phase 6 — Security, Audit & Reliability (MUST)

## Goals
- Improve traceability
- Harden the platform for real internal usage

## Tasks

### 1. Roles & Permissions
**MUST**
Standardize:
- Admin
- Technician
- Viewer

Ensure permission matrix is documented and enforced consistently.

### 2. Audit Log
**MUST**
Track at minimum:
- asset changes
- assignment changes
- status changes
- incident updates
- maintenance updates
- permission-sensitive admin actions
- import/export actions

### 3. Security Hardening
**MUST**
- ensure default admin insecure path is gone
- require secure secret/session config
- apply session timeout
- add basic rate limit where needed
- review unsafe internal actions

### 4. Error & Reliability Visibility
**SHOULD**
Add:
- error tracking
- exception logging
- failed notification logs
- migration/backfill logs
- suspicious auth behavior logging

### 5. Observability
**SHOULD**
Add:
- basic metrics
- slow query detection
- route latency visibility
- operational health checks

---

# Phase 7 — Optimization & Scale (NICE TO HAVE)

## Goals
- Improve performance and scalability only after workflows are stable

## Start Phase 7 Only When
**MUST**
Start only if one or more conditions are true:
- asset volume > 500
- incidents > 50 / week
- dashboard query latency exceeds target threshold
- real user complaints indicate performance bottleneck
- reporting/export becomes operationally slow

## Tasks

### 1. Database & Query Optimization
**NICE TO HAVE**
- move to PostgreSQL if needed
- add indexes for search/filter fields
- optimize heavy list/dashboard queries

### 2. Performance Observability
**NICE TO HAVE**
- slow query reporting
- route latency tracking
- basic usage metrics

### 3. Caching
**NICE TO HAVE**
- introduce caching only if justified by real bottlenecks

---

# 📅 Suggested 6-Week Timeline

## Week 1
**MUST**
- Phase 0 stabilization
- security baseline
- config/env cleanup
- smoke test baseline

## Week 2
**MUST**
- Phase 1 data foundation
- migrations
- master data
- FK + backfill
- seed data

## Week 3
**MUST**
- Phase 2 asset lifecycle
- status history
- assignment model
- assignment UI basics

## Week 4
**MUST / SHOULD**
- Phase 3 incident + maintenance
- SLA basics
- warranty and vendor linkage

## Week 5
**SHOULD**
- Phase 4 operational features
- event-driven notifications
- checklist + compliance checks

## Week 6
**MUST / SHOULD**
- Phase 5 dashboard/reporting
- Phase 6 audit/security completion
- stabilization and regression pass

---

# ⚠️ Anti-Patterns to Avoid

- ❌ Big refactor all at once
- ❌ Delete old fields immediately
- ❌ Hardcode values like status/department/category
- ❌ Mix heavy business logic inside routes
- ❌ Skip migration/backfill logging
- ❌ Add notifications before defining domain events
- ❌ Build reports on dirty/unmapped data without warnings
- ❌ Maintain multiple conflicting ownership truths for assets

---

# ✅ Definition of Done (per feature)

Every feature should include:

## MUST
- data model updated
- migration handled
- fallback compatibility considered
- UI updated
- permission impact reviewed
- audit impact reviewed
- manual test checklist completed

## SHOULD
- smoke test updated
- logs added where relevant
- edge cases documented

---

# 📌 Next Immediate Steps

1. Audit current schema and legacy string fields
2. Define FK mapping strategy for assets, incidents, maintenance
3. Backup database before migration work
4. Create master data tables
5. Add FK fields without deleting legacy fields
6. Seed core master data
7. Backfill legacy values and log unmatched mappings
8. Update asset form/list with dropdown + fallback logic
9. Add smoke test for migrated flow
