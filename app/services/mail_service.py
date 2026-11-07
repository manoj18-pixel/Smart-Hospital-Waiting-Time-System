"""Email notifications. Failed delivery never rolls back a booking."""
from datetime import datetime

from flask import current_app, render_template
from flask_mail import Message

from ..extensions import db, mail
from ..models.notification import Notification
from ..utils.time_utils import format_date, format_time, humanize_minutes


def _send(appointment, kind, subject, template, extra=None):
    patient = appointment.patient
    recipient = patient.email if patient else None
    if not recipient:
        return None
    context = {
        "appointment": appointment,
        "doctor": appointment.doctor,
        "patient": patient,
        "date_label": format_date(appointment.appointment_date),
        "time_label": format_time(appointment.start_time),
        "humanize_minutes": humanize_minutes,
        "extra": extra or {},
        "hospital_name": current_app.config.get("HOSPITAL_NAME", "MediQueue"),
    }
    try:
        html = render_template(template, **context)
        text = render_template("email/plain.txt", **context)
    except Exception:
        html, text = None, None

    notification = Notification(
        user_id=patient.id,
        appointment_id=appointment.id,
        channel="email",
        type=kind,
        recipient_email=recipient,
        subject=subject,
        body=html,
        status="pending",
    )
    db.session.add(notification)
    db.session.commit()

    try:
        message = Message(subject=subject, recipients=[recipient], html=html, body=text)
        mail.send(message)
        notification.status = "sent"
        notification.sent_at = datetime.utcnow()
    except Exception as exc:  # pragma: no cover - depends on external SMTP
        notification.status = "failed"
        notification.error_message = str(exc)[:500]
    db.session.commit()
    return notification


def send_booking_confirmation(appointment):
    subject = f"Appointment confirmed - {appointment.booking_id}"
    return _send(
        appointment, "booking_confirmation", subject, "email/booking_confirmation.html"
    )


def send_cancellation(appointment, cancelled_by="patient"):
    subject = f"Appointment cancelled - {appointment.booking_id}"
    return _send(
        appointment,
        "cancellation",
        subject,
        "email/cancellation.html",
        extra={"cancelled_by": cancelled_by},
    )
