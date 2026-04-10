import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def log_audit(
    db: Session,
    *,
    actor: str | None,
    module: str,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    result: str = 'success',
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    safe_metadata = None
    if metadata:
        redacted = {}
        for k, v in metadata.items():
            key = str(k).lower()
            if any(token in key for token in ['password', 'token', 'secret']):
                redacted[k] = '[redacted]'
            else:
                redacted[k] = v
        safe_metadata = json.dumps(redacted, ensure_ascii=False, default=str)

    db.add(
        AuditLog(
            actor=actor,
            module=module,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            result=result,
            reason=reason,
            metadata_json=safe_metadata,
        )
    )
