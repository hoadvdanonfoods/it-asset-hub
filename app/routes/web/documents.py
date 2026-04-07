import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_module_access, require_permission
from app.config import DATA_DIR
from app.db.models import Document
from app.db.session import get_db

router = APIRouter(prefix='/documents', tags=['documents'])
templates = Jinja2Templates(directory='app/templates')
DOCUMENTS_DIR = DATA_DIR / 'uploads' / 'documents'
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx'}


def _render_form(request: Request, current_user, *, item=None, error: str | None = None):
    return templates.TemplateResponse('documents/form.html', {'request': request, 'current_user': current_user, 'item': item, 'error': error})


@router.get('/', response_class=HTMLResponse)
@require_module_access('documents')
def document_list(request: Request, q: str | None = Query(default=None), category: str | None = Query(default=None), db: Session = Depends(get_db), current_user=None):
    stmt = select(Document).where(Document.is_active == True)  # noqa: E712
    if q:
        like = f'%{q.strip()}%'
        stmt = stmt.where(Document.title.ilike(like))
    if category:
        stmt = stmt.where(Document.category == category)
    items = db.scalars(stmt.order_by(Document.created_at.desc(), Document.title.asc())).all()
    categories = db.scalars(select(Document.category).where(Document.category.is_not(None)).distinct().order_by(Document.category.asc())).all()
    return templates.TemplateResponse('documents/list.html', {'request': request, 'current_user': current_user, 'items': items, 'q': q or '', 'category': category or '', 'categories': categories})


@router.get('/new', response_class=HTMLResponse)
@require_permission('can_manage_documents')
def document_new(request: Request, current_user=None):
    return _render_form(request, current_user)


@router.post('/new')
@require_permission('can_manage_documents')
def document_create(request: Request, title: str = Form(...), category: str = Form(default='Biểu mẫu'), description: str = Form(default=''), file: UploadFile = File(...), db: Session = Depends(get_db), current_user=None):
    ext = Path(file.filename or '').suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return _render_form(request, current_user, error='Chỉ hỗ trợ PDF, Word hoặc Excel.')
    content = file.file.read()
    if not content:
        return _render_form(request, current_user, error='File upload đang rỗng.')
    stored_filename = f'{uuid.uuid4().hex}{ext}'
    stored_path = DOCUMENTS_DIR / stored_filename
    stored_path.write_bytes(content)
    mime_type = file.content_type or mimetypes.guess_type(file.filename or '')[0] or 'application/octet-stream'
    item = Document(
        title=title.strip(),
        category=category.strip() or 'Biểu mẫu',
        description=description.strip() or None,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        stored_path=str(stored_path),
        mime_type=mime_type,
        file_size=len(content),
        uploaded_by=(current_user.full_name or current_user.username) if current_user else None,
        is_active=True,
    )
    db.add(item)
    db.commit()
    return RedirectResponse('/documents/', status_code=303)


@router.get('/{document_id}/download')
@require_module_access('documents')
def document_download(document_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Document, document_id)
    if not item or not item.is_active:
        return RedirectResponse('/documents/', status_code=303)
    return FileResponse(path=item.stored_path, filename=item.original_filename, media_type=item.mime_type or 'application/octet-stream')


@router.get('/{document_id}/edit', response_class=HTMLResponse)
@require_permission('can_manage_documents')
def document_edit(document_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Document, document_id)
    return _render_form(request, current_user, item=item)


@router.post('/{document_id}/edit')
@require_permission('can_manage_documents')
def document_update(document_id: int, request: Request, title: str = Form(...), category: str = Form(default='Biểu mẫu'), description: str = Form(default=''), replace_file: UploadFile | None = File(default=None), db: Session = Depends(get_db), current_user=None):
    item = db.get(Document, document_id)
    item.title = title.strip()
    item.category = category.strip() or 'Biểu mẫu'
    item.description = description.strip() or None
    if replace_file and (replace_file.filename or '').strip():
        ext = Path(replace_file.filename or '').suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return _render_form(request, current_user, item=item, error='Chỉ hỗ trợ PDF, Word hoặc Excel.')
        content = replace_file.file.read()
        if content:
            old_path = Path(item.stored_path)
            if old_path.exists():
                old_path.unlink()
            stored_filename = f'{uuid.uuid4().hex}{ext}'
            stored_path = DOCUMENTS_DIR / stored_filename
            stored_path.write_bytes(content)
            item.stored_filename = stored_filename
            item.stored_path = str(stored_path)
            item.original_filename = replace_file.filename or stored_filename
            item.mime_type = replace_file.content_type or mimetypes.guess_type(replace_file.filename or '')[0] or 'application/octet-stream'
            item.file_size = len(content)
    db.commit()
    return RedirectResponse('/documents/', status_code=303)


@router.post('/{document_id}/archive')
@require_permission('can_manage_documents')
def document_archive(document_id: int, request: Request, db: Session = Depends(get_db), current_user=None):
    item = db.get(Document, document_id)
    if item:
        item.is_active = False
        db.commit()
    return RedirectResponse('/documents/', status_code=303)
