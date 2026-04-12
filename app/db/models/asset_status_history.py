from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssetStatusHistory(Base):
    __tablename__ = 'asset_status_history'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), index=True)
    old_status_id: Mapped[int | None] = mapped_column(ForeignKey('asset_statuses.id'), nullable=True, index=True)
    new_status_id: Mapped[int | None] = mapped_column(ForeignKey('asset_statuses.id'), nullable=True, index=True)
    old_status_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status_code: Mapped[str] = mapped_column(String(50), index=True)
    changed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset = relationship('Asset', back_populates='status_history')
