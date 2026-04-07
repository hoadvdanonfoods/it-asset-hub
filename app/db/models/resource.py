from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Resource(Base):
    __tablename__ = 'resources'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    username_hint: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
