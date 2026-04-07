from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IncidentEvent(Base):
    __tablename__ = 'incident_events'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey('incidents.id'), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    incident = relationship('Incident', back_populates='events')
