"""Hospital department model."""
from datetime import datetime

from ..extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(60), default="fa-hospital")
    image_url = db.Column(db.String(400))
    floor = db.Column(db.String(30))
    phone_ext = db.Column(db.String(10))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    doctors = db.relationship("Doctor", back_populates="department", lazy="dynamic")

    @property
    def doctor_count(self):
        return self.doctors.filter_by(is_active=True).count()

    @property
    def active_doctors(self):
        return self.doctors.filter_by(is_active=True).order_by("id").all()

    def __repr__(self):
        return f"<Department {self.name}>"
