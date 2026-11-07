"""Public pages: landing, about and health check."""
from datetime import date

from flask import Blueprint, jsonify, render_template

from ..models.appointment import Appointment
from ..models.department import Department
from ..models.doctor import Doctor
from ..models.user import User
from ..services import schedule_service

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    departments = (
        Department.query.filter_by(is_active=True).order_by(Department.name).limit(8).all()
    )
    doctors = (
        Doctor.query.filter_by(is_active=True).order_by(Doctor.experience_years.desc()).limit(4).all()
    )
    stats = {
        "doctors": Doctor.query.filter_by(is_active=True).count(),
        "departments": Department.query.filter_by(is_active=True).count(),
        "patients": User.query.filter_by(role="patient").count(),
        "appointments": Appointment.query.count(),
    }
    return render_template(
        "main/index.html", departments=departments, doctors=doctors, stats=stats
    )


@bp.get("/about")
def about():
    return render_template("main/about.html")


@bp.get("/contact")
def contact():
    return render_template("main/contact.html")


@bp.get("/health")
def health():
    return jsonify(status="ok", service="mediqueue", date=date.today().isoformat())
