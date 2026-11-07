"""Appointment model and status helpers."""
from datetime import datetime, timedelta

from ..constants import ACTIVE_APPOINTMENT_STATUSES, AppointmentStatus
from ..extensions import db


class Appointment(db.Model):
    __tablename__ = "appointments"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('CONFIRMED','CHECKED_IN','IN_CONSULTATION','COMPLETED','CANCELLED','NO_SHOW')",
            name="ck_appointment_status",
        ),
        db.Index("idx_appt_patient", "patient_id", "status"),
        db.Index("idx_appt_doctor", "doctor_id", "appointment_date", "start_time"),
        db.Index("idx_appt_day", "appointment_date", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.String(24), nullable=False, unique=True, index=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    doctor_id = db.Column(
        db.Integer, db.ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False
    )
    slot_id = db.Column(
        db.Integer,
        db.ForeignKey("slots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    appointment_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.String(15), nullable=False, default=AppointmentStatus.CONFIRMED, index=True
    )
    reason_for_visit = db.Column(db.String(300))
    fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    queue_position = db.Column(db.SmallInteger)
    estimated_wait_minutes = db.Column(db.SmallInteger)
    checked_in_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    cancelled_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    cancel_reason = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patient = db.relationship(
        "User", back_populates="appointments", foreign_keys=[patient_id]
    )
    doctor = db.relationship("Doctor")
    slot = db.relationship("Slot", back_populates="appointment")
    canceller = db.relationship("User", foreign_keys=[cancelled_by])

    @property
    def starts_at(self):
        return datetime.combine(self.appointment_date, self.start_time)

    @property
    def ends_at(self):
        return datetime.combine(self.appointment_date, self.end_time)

    @property
    def is_active(self):
        return self.status in ACTIVE_APPOINTMENT_STATUSES

    @property
    def is_upcoming(self):
        return self.is_active and self.starts_at > datetime.now()

    @property
    def is_today(self):
        return self.appointment_date == datetime.now().date()

    def cancellable(self, cutoff_hours=2):
        return self.is_active and self.starts_at - datetime.now() >= timedelta(
            hours=cutoff_hours
        )

    def __repr__(self):
        return f"<Appointment {self.booking_id} {self.status}>"
