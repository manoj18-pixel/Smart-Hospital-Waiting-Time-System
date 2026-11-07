"""Audit logging helper."""
import json

from flask import has_request_context, request
from flask_login import current_user

from ..extensions import db
from ..models.audit_log import AuditLog


def log(action, entity_type=None, entity_id=None, details=None, actor=None, commit=True):
    if actor is None:
        actor = current_user if getattr(current_user, "is_authenticated", False) else None
    actor_id = getattr(actor, "id", None)
    if details is not None and not isinstance(details, str):
        details = json.dumps(details, default=str)
    entry = AuditLog(
        actor_user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=request.remote_addr if has_request_context() else None,
    )
    db.session.add(entry)
    if commit:
        db.session.commit()
    return entry
