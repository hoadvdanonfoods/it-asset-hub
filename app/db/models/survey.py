from datetime import datetime

from sqlalchemy import Integer, String, Text, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Survey(Base):
    __tablename__ = 'surveys'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    quarter: Mapped[str] = mapped_column(String(2))   # Q1 Q2 Q3 Q4
    year: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), default='draft')  # draft active closed
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)


class SurveyResponse(Base):
    __tablename__ = 'survey_responses'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    survey_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)
    response_time: Mapped[int] = mapped_column(Integer)   # Tốc độ phản hồi 1-5
    quality: Mapped[int] = mapped_column(Integer)         # Chất lượng xử lý 1-5
    attitude: Mapped[int] = mapped_column(Integer)        # Thái độ phục vụ 1-5
    knowledge: Mapped[int] = mapped_column(Integer)       # Kiến thức chuyên môn 1-5
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    respondent_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    __table_args__ = (UniqueConstraint('survey_id', 'user_id', name='uq_survey_response'),)
