"""Dated appointment slot model - the heart of the booking system."""
from datetime import datetime

from ..constants import SlotStatus
from ..extensions import db


class Slot(db.Model):
    __tablename__ = "slots"
    __table_args__ = (
        db.UniqueConstraint(
            "doctor_id", "slot_date", "start_time", name="uq_doctor_slot"
        ),
        db.CheckConstraint("end_time > start_time", name="ck_slot_window"),
        db.Index("idx_slots_day", "slot_date", "status"),
        db.Index("idx_slots_doctor", "doctor_id", "slot_date", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.String(12), nullable=False, default=SlotStatus.AVAILABLE, index=True
    )
    fee = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    doctor = db.relationship("Doctor", back_populates="slots")
    appointment = db.relationship("Appointment", back_populates="slot", uselist=False)

    @property
    def starts_at(self):
        return datetime.combine(self.slot_date, self.start_time)

    @property
    def is_available(self):
        return self.status == SlotStatus.AVAILABLE and self.starts_at > datetime.now()

    @property
    def is_past(self):
        return self.starts_at <= datetime.now()

    def __repr__(self):
        return f"<Slot {self.slot_date} {self.start_time} doctor={self.doctor_id} {self.status}>"
