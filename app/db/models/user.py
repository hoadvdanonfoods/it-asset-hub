from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default='user')
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_dashboard: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_assets: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_maintenance: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_incidents: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_resources: Mapped[bool] = mapped_column(Boolean, default=False)
    can_create_assets: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit_assets: Mapped[bool] = mapped_column(Boolean, default=False)
    can_import_assets: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export_assets: Mapped[bool] = mapped_column(Boolean, default=False)
    can_create_maintenance: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit_maintenance: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export_maintenance: Mapped[bool] = mapped_column(Boolean, default=False)
    can_create_incidents: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_incidents: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export_incidents: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_users: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_system: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_resources: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    session_version: Mapped[int] = mapped_column(default=1)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
