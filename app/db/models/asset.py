from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Asset(Base):
    __tablename__ = 'assets'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    asset_name: Mapped[str] = mapped_column(String(200))
    asset_type: Mapped[str] = mapped_column(String(50), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey('asset_categories.id'), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey('departments.id'), nullable=True, index=True)
    assigned_user: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_at: Mapped[str | None] = mapped_column(String(25), nullable=True)
    unassigned_at: Mapped[str | None] = mapped_column(String(25), nullable=True)
    current_assignment_id: Mapped[int | None] = mapped_column(ForeignKey('asset_assignments.id'), nullable=True, index=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey('locations.id'), nullable=True, index=True)
    purchase_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    warranty_expiry: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='active')
    status_id: Mapped[int | None] = mapped_column(ForeignKey('asset_statuses.id'), nullable=True, index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey('vendors.id'), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    maintenances = relationship('Maintenance', back_populates='asset', cascade='all, delete-orphan')
    incidents = relationship('Incident', back_populates='asset', cascade='all, delete-orphan')
    assignments = relationship('AssetAssignment', back_populates='asset', cascade='all, delete-orphan', order_by='desc(AssetAssignment.assigned_at)', foreign_keys='AssetAssignment.asset_id')
    events = relationship('AssetEvent', back_populates='asset', cascade='all, delete-orphan', order_by='desc(AssetEvent.created_at)')
    status_history = relationship('AssetStatusHistory', back_populates='asset', cascade='all, delete-orphan', order_by='desc(AssetStatusHistory.changed_at)')
