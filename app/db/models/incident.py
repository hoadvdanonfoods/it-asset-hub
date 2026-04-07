from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Incident(Base):
    __tablename__ = 'incidents'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), index=True)
    reported_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requester_department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    issue_description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default='medium')
    status: Mapped[str] = mapped_column(String(20), default='open')
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    asset = relationship('Asset', back_populates='incidents')
    events = relationship('IncidentEvent', back_populates='incident', cascade='all, delete-orphan', order_by='desc(IncidentEvent.created_at)')
