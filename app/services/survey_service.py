from datetime import datetime

from sqlalchemy import select

from app.db.session import SessionLocal


CRITERIA = [
    ('response_time', 'Tốc độ phản hồi'),
    ('quality',       'Chất lượng xử lý'),
    ('attitude',      'Thái độ phục vụ'),
    ('knowledge',     'Kiến thức chuyên môn'),
]


def validate_response(response_time: int, quality: int, attitude: int, knowledge: int, reason_text: str | None) -> str | None:
    scores = [response_time, quality, attitude, knowledge]
    for s in scores:
        if s not in (1, 2, 3, 4, 5):
            return 'Vui lòng đánh giá đầy đủ tất cả 4 tiêu chí (1–5 sao).'
    if any(s <= 3 for s in scores):
        text = (reason_text or '').strip()
        if not text:
            return 'Vui lòng nhập lý do khi có tiêu chí đánh giá ≤ 3 sao.'
        if len(text) < 30:
            return 'Lý do phải có ít nhất 30 ký tự.'
        words = [w for w in text.split() if w]
        if len(words) < 5:
            return 'Lý do phải có ít nhất 5 từ.'
    return None


def avg_score(response_time: int, quality: int, attitude: int, knowledge: int) -> float:
    return round((response_time + quality + attitude + knowledge) / 4, 2)


def get_pending_survey_for_user(current_user):
    """Jinja2 global: returns active Survey if user hasn't responded yet, else None."""
    if not current_user:
        return None
    from app.db.models.survey import Survey, SurveyResponse
    db = SessionLocal()
    try:
        survey = db.scalar(select(Survey).where(Survey.status == 'active'))
        if not survey:
            return None
        now = datetime.utcnow()
        if now < survey.start_date or now > survey.end_date:
            return None
        already = db.scalar(
            select(SurveyResponse).where(
                SurveyResponse.survey_id == survey.id,
                SurveyResponse.user_id == current_user.id,
            )
        )
        return None if already else survey
    finally:
        db.close()
