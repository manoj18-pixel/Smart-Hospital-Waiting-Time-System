"""User and patient profile models."""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..constants import Roles
from ..extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10), nullable=False, default=Roles.PATIENT, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patient_profile = db.relationship(
        "PatientProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    doctor = db.relationship(
        "Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    appointments = db.relationship(
        "Appointment",
        back_populates="patient",
        foreign_keys="Appointment.patient_id",
        lazy="dynamic",
    )

    @property
    def is_authenticated(self):
        """A loaded session user is authenticated even if later deactivated.

        Flask-Login's default ``UserMixin.is_authenticated`` returns
        ``is_active``, which silently turns a deactivated account into an
        anonymous user mid-session. Keeping the session authenticated lets
        :func:`role_required` reject it with an explicit 403 instead of a
        redirect that hides what happened. ``login_user`` still refuses to
        create a session for an inactive account.
        """
        return True

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def first_name(self):
        return (self.full_name or "").split(" ")[0]

    @property
    def initials(self):
        parts = [p for p in (self.full_name or "").split(" ") if p]
        return "".join(p[0] for p in parts[:2]).upper() or "U"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class PatientProfile(db.Model):
    __tablename__ = "patient_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(15))
    blood_group = db.Column(db.String(5))
    address = db.Column(db.String(255))
    emergency_contact = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="patient_profile")

    def __repr__(self):
        return f"<PatientProfile user={self.user_id}>"
