"""Audit trail for sensitive actions."""
from datetime import datetime

from ..extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (db.Index("idx_audit_actor", "actor_user_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL")
    )
    action = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(30))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    actor = db.relationship("User", foreign_keys=[actor_user_id])

    def __repr__(self):
        return f"<AuditLog {self.action}>"
