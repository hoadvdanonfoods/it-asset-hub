from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssetAssignment(Base):
    __tablename__ = 'asset_assignments'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), index=True)
    assigned_user: Mapped[str] = mapped_column(String(120))
    assigned_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    returned_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='assigned', index=True)

    asset = relationship('Asset', back_populates='assignments')
