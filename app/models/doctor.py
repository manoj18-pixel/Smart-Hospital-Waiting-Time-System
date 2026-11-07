"""Doctor, weekly schedule and leave models."""
from datetime import datetime

from ..extensions import db


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    specialization = db.Column(db.String(120), nullable=False)
    qualification = db.Column(db.String(150))
    experience_years = db.Column(db.Integer, nullable=False, default=0)
    consultation_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    room_no = db.Column(db.String(20))
    bio = db.Column(db.Text)
    photo_url = db.Column(db.String(400))
    avg_consult_minutes = db.Column(db.Integer, nullable=False, default=15)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="doctor")
    department = db.relationship("Department", back_populates="doctors")
    schedules = db.relationship(
        "DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan"
    )
    exceptions = db.relationship(
        "ScheduleException", back_populates="doctor", cascade="all, delete-orphan"
    )
    slots = db.relationship(
        "Slot", back_populates="doctor", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def name(self):
        return self.user.full_name if self.user else "Doctor"

    @property
    def email(self):
        return self.user.email if self.user else ""

    @property
    def initials(self):
        return self.user.initials if self.user else "DR"

    def __repr__(self):
        return f"<Doctor {self.name}>"


class DoctorSchedule(db.Model):
    __tablename__ = "doctor_schedules"
    __table_args__ = (
        db.UniqueConstraint(
            "doctor_id", "weekday", "start_time", name="uq_doctor_weekday_start"
        ),
        db.CheckConstraint("end_time > start_time", name="ck_schedule_window"),
    )

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday = db.Column(db.SmallInteger, nullable=False)  # 0 = Monday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_duration_minutes = db.Column(db.SmallInteger, nullable=False, default=20)
    max_patients = db.Column(db.SmallInteger)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    doctor = db.relationship("Doctor", back_populates="schedules")

    @property
    def weekday_name(self):
        return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
            self.weekday
        ]


class ScheduleException(db.Model):
    __tablename__ = "schedule_exceptions"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exception_date = db.Column(db.Date, nullable=False, index=True)
    is_closed = db.Column(db.Boolean, nullable=False, default=True)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    reason = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    doctor = db.relationship("Doctor", back_populates="exceptions")

    def covers(self, start_time, end_time):
        if self.is_closed and self.start_time is None:
            return True
        if self.start_time and self.end_time:
            return start_time < self.end_time and end_time > self.start_time
        return False
