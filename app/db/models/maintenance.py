from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Maintenance(Base):
    __tablename__ = 'maintenances'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), index=True)
    maintenance_type_id: Mapped[int | None] = mapped_column(ForeignKey('maintenance_types.id'), nullable=True, index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey('vendors.id'), nullable=True, index=True)
    maintenance_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    technician: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    next_maintenance_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    asset = relationship('Asset', back_populates='maintenances')
