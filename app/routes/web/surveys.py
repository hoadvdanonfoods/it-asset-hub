from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login, require_permission
from app.db.models.survey import Survey, SurveyResponse
from app.db.session import get_db
from app.services.survey_service import CRITERIA, avg_score, validate_response

router = APIRouter(prefix='/surveys', tags=['surveys'])
templates = Jinja2Templates(directory='app/templates')


# ── Admin: list surveys ──────────────────────────────────────────────────────

@router.get('/', response_class=HTMLResponse)
@require_permission('can_manage_system')
def survey_list(request: Request, current_user=None, db: Session = Depends(get_db)):
    surveys = db.scalars(select(Survey).order_by(Survey.year.desc(), Survey.quarter.desc())).all()
    counts = {
        r[0]: r[1]
        for r in db.execute(
            select(SurveyResponse.survey_id, func.count(SurveyResponse.id))
            .group_by(SurveyResponse.survey_id)
        ).all()
    }
    return templates.TemplateResponse('surveys/list.html', {
        'request': request, 'current_user': current_user,
        'surveys': surveys, 'response_counts': counts,
    })


# ── Admin: create survey ─────────────────────────────────────────────────────

@router.get('/new', response_class=HTMLResponse)
@require_permission('can_manage_system')
def survey_new(request: Request, current_user=None):
    return templates.TemplateResponse('surveys/form.html', {
        'request': request, 'current_user': current_user, 'error': None,
    })


@router.post('/new')
@require_permission('can_manage_system')
def survey_create(
    request: Request,
    title: str = Form(...),
    quarter: str = Form(...),
    year: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    current_user=None,
    db: Session = Depends(get_db),
):
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        return templates.TemplateResponse('surveys/form.html', {
            'request': request, 'current_user': current_user,
            'error': 'Ngày không hợp lệ.',
        })
    if end <= start:
        return templates.TemplateResponse('surveys/form.html', {
            'request': request, 'current_user': current_user,
            'error': 'Ngày kết thúc phải sau ngày bắt đầu.',
        })
    db.add(Survey(
        title=title.strip(),
        quarter=quarter,
        year=year,
        start_date=start,
        end_date=end,
        status='draft',
        created_at=datetime.utcnow(),
        created_by=current_user.username if current_user else None,
    ))
    db.commit()
    return RedirectResponse('/surveys/', status_code=303)


# ── Admin: activate / close ──────────────────────────────────────────────────

@router.post('/{survey_id}/activate')
@require_permission('can_manage_system')
def survey_activate(request: Request, survey_id: int, current_user=None, db: Session = Depends(get_db)):
    # Only one survey active at a time
    for s in db.scalars(select(Survey).where(Survey.status == 'active')).all():
        s.status = 'closed'
    survey = db.get(Survey, survey_id)
    if survey:
        survey.status = 'active'
    db.commit()
    return RedirectResponse('/surveys/', status_code=303)


@router.post('/{survey_id}/close')
@require_permission('can_manage_system')
def survey_close(request: Request, survey_id: int, current_user=None, db: Session = Depends(get_db)):
    survey = db.get(Survey, survey_id)
    if survey:
        survey.status = 'closed'
    db.commit()
    return RedirectResponse('/surveys/', status_code=303)


# ── Admin: dashboard ─────────────────────────────────────────────────────────

@router.get('/{survey_id}/dashboard', response_class=HTMLResponse)
@require_permission('can_manage_system')
def survey_dashboard(request: Request, survey_id: int, current_user=None, db: Session = Depends(get_db)):
    survey = db.get(Survey, survey_id)
    if not survey:
        return RedirectResponse('/surveys/', status_code=303)
    responses = db.scalars(
        select(SurveyResponse).where(SurveyResponse.survey_id == survey_id)
        .order_by(SurveyResponse.submitted_at.desc())
    ).all()
    total = len(responses)
    if total:
        avgs = {
            'response_time': round(sum(r.response_time for r in responses) / total, 2),
            'quality':       round(sum(r.quality       for r in responses) / total, 2),
            'attitude':      round(sum(r.attitude      for r in responses) / total, 2),
            'knowledge':     round(sum(r.knowledge     for r in responses) / total, 2),
        }
        avgs['overall'] = round(sum(avgs.values()) / 4, 2)
        dist = {i: sum(1 for r in responses if round((r.response_time + r.quality + r.attitude + r.knowledge) / 4) == i) for i in range(1, 6)}
        low_pct = round(sum(1 for r in responses if any(s <= 3 for s in [r.response_time, r.quality, r.attitude, r.knowledge])) / total * 100)
    else:
        avgs = {'response_time': 0, 'quality': 0, 'attitude': 0, 'knowledge': 0, 'overall': 0}
        dist = {i: 0 for i in range(1, 6)}
        low_pct = 0

    return templates.TemplateResponse('surveys/dashboard.html', {
        'request': request, 'current_user': current_user,
        'survey': survey, 'responses': responses,
        'total': total, 'avgs': avgs, 'dist': dist,
        'low_pct': low_pct, 'criteria': CRITERIA,
    })


# ── User: respond ────────────────────────────────────────────────────────────

@router.get('/{survey_id}/respond', response_class=HTMLResponse)
@require_login
def survey_respond_page(request: Request, survey_id: int, current_user=None, db: Session = Depends(get_db)):
    survey = db.get(Survey, survey_id)
    if not survey or survey.status != 'active':
        return RedirectResponse('/', status_code=303)
    now = datetime.utcnow()
    if now < survey.start_date or now > survey.end_date:
        return RedirectResponse('/', status_code=303)
    existing = db.scalar(
        select(SurveyResponse).where(
            SurveyResponse.survey_id == survey_id,
            SurveyResponse.user_id == current_user.id,
        )
    )
    if existing:
        return RedirectResponse(f'/surveys/{survey_id}/my-response', status_code=303)
    return templates.TemplateResponse('surveys/respond.html', {
        'request': request, 'current_user': current_user,
        'survey': survey, 'criteria': CRITERIA, 'error': None,
    })


@router.post('/{survey_id}/respond')
@require_login
def survey_respond_submit(
    request: Request,
    survey_id: int,
    response_time: int = Form(...),
    quality: int = Form(...),
    attitude: int = Form(...),
    knowledge: int = Form(...),
    reason_text: str = Form(default=''),
    current_user=None,
    db: Session = Depends(get_db),
):
    survey = db.get(Survey, survey_id)
    if not survey or survey.status != 'active':
        return RedirectResponse('/', status_code=303)
    now = datetime.utcnow()
    if now < survey.start_date or now > survey.end_date:
        return RedirectResponse('/', status_code=303)

    # Double-submit guard
    existing = db.scalar(
        select(SurveyResponse).where(
            SurveyResponse.survey_id == survey_id,
            SurveyResponse.user_id == current_user.id,
        )
    )
    if existing:
        return RedirectResponse(f'/surveys/{survey_id}/my-response', status_code=303)

    error = validate_response(response_time, quality, attitude, knowledge, reason_text)
    if error:
        return templates.TemplateResponse('surveys/respond.html', {
            'request': request, 'current_user': current_user,
            'survey': survey, 'criteria': CRITERIA, 'error': error,
            'prev': {'response_time': response_time, 'quality': quality,
                     'attitude': attitude, 'knowledge': knowledge,
                     'reason_text': reason_text},
        })

    db.add(SurveyResponse(
        survey_id=survey_id,
        user_id=current_user.id,
        submitted_at=now,
        response_time=response_time,
        quality=quality,
        attitude=attitude,
        knowledge=knowledge,
        reason_text=reason_text.strip() or None,
        respondent_name=current_user.full_name or current_user.username,
    ))
    db.commit()
    return RedirectResponse(f'/surveys/{survey_id}/my-response', status_code=303)


# ── User: view own response ──────────────────────────────────────────────────

@router.get('/{survey_id}/my-response', response_class=HTMLResponse)
@require_login
def survey_my_response(request: Request, survey_id: int, current_user=None, db: Session = Depends(get_db)):
    survey = db.get(Survey, survey_id)
    response = db.scalar(
        select(SurveyResponse).where(
            SurveyResponse.survey_id == survey_id,
            SurveyResponse.user_id == current_user.id,
        )
    )
    if not response:
        return RedirectResponse(f'/surveys/{survey_id}/respond', status_code=303)
    overall = avg_score(response.response_time, response.quality, response.attitude, response.knowledge)
    return templates.TemplateResponse('surveys/my_response.html', {
        'request': request, 'current_user': current_user,
        'survey': survey, 'response': response,
        'overall': overall, 'criteria': CRITERIA,
    })
