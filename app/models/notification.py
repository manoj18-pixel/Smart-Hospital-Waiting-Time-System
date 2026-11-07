"""Outbound notification log."""
from datetime import datetime

from ..extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    appointment_id = db.Column(
        db.Integer, db.ForeignKey("appointments.id", ondelete="SET NULL")
    )
    channel = db.Column(db.String(10), nullable=False, default="email")
    type = db.Column(db.String(30), nullable=False)
    recipient_email = db.Column(db.String(255))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    status = db.Column(db.String(10), nullable=False, default="pending")
    error_message = db.Column(db.String(500))
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
    appointment = db.relationship("Appointment", foreign_keys=[appointment_id])

    def __repr__(self):
        return f"<Notification {self.type} {self.status}>"
