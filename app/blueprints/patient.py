"""Patient-facing dashboard, doctor discovery and appointment management."""
from datetime import date, datetime, timedelta

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import or_

from ..constants import ACTIVE_APPOINTMENT_STATUSES, AppointmentStatus
from ..extensions import db
from ..forms import BookingForm, CancelForm
from ..models.appointment import Appointment
from ..models.department import Department
from ..models.doctor import Doctor
from ..models.setting import Setting
from ..models.slot import Slot
from ..services import booking_service, schedule_service, slot_service, waiting_service
from ..utils.decorators import patient_required
from ..utils.time_utils import dashboard_for, humanize_minutes
from ..utils.time_utils import combine

bp = Blueprint("patient", __name__, url_prefix="/patient")


def _doctor_or_404(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)
    if doctor is None or not doctor.is_active:
        abort(404)
    return doctor


def _appointment_for_patient(booking_id):
    appointment = Appointment.query.filter_by(booking_id=booking_id).first_or_404()
    if appointment.patient_id != current_user.id:
        abort(403)
    return appointment


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@bp.get("/dashboard")
@patient_required
def dashboard():
    today = date.today()
    base = Appointment.query.filter_by(patient_id=current_user.id)
    upcoming = (
        base.filter(
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.appointment_date >= today,
        )
        .order_by(Appointment.appointment_date, Appointment.start_time)
        .all()
    )
    next_appointment = upcoming[0] if upcoming else None
    stats = {
        "upcoming": len(upcoming),
        "completed": base.filter_by(status=AppointmentStatus.COMPLETED).count(),
        "cancelled": base.filter_by(status=AppointmentStatus.CANCELLED).count(),
        "total": base.count(),
    }
    wait = None
    if next_appointment and next_appointment.appointment_date == today:
        wait = waiting_service.live_wait(next_appointment)
    recent = (
        base.order_by(Appointment.created_at.desc()).limit(5).all()
    )
    return render_template(
        "patient/dashboard.html",
        upcoming=upcoming[:4],
        next_appointment=next_appointment,
        stats=stats,
        wait=wait,
        recent=recent,
    )


@bp.get("/departments")
@patient_required
def departments():
    items = (
        Department.query.filter_by(is_active=True).order_by(Department.name).all()
    )
    return render_template("patient/departments.html", departments=items)


@bp.get("/departments/<int:department_id>/doctors")
@patient_required
def doctors(department_id):
    department = db.session.get(Department, department_id)
    if department is None or not department.is_active:
        abort(404)
    items = (
        Doctor.query.filter_by(department_id=department.id, is_active=True)
        .order_by(Doctor.experience_years.desc())
        .all()
    )
    next_dates = {}
    for doctor in items:
        availability = schedule_service.available_dates(doctor, days=14, generate=False)
        next_dates[doctor.id] = availability[0]["date"] if availability else None
    return render_template(
        "patient/doctors.html",
        department=department,
        doctors=items,
        next_dates=next_dates,
    )


@bp.get("/doctors/<int:doctor_id>")
@patient_required
def doctor_profile(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    schedules = sorted(
        [s for s in doctor.schedules if s.is_active],
        key=lambda s: (s.weekday, s.start_time),
    )
    availability = schedule_service.available_dates(doctor, days=14)
    return render_template(
        "patient/doctor_profile.html",
        doctor=doctor,
        schedules=schedules,
        availability=availability,
    )


@bp.route("/book/<int:doctor_id>", methods=["GET", "POST"])
@patient_required
def book(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    form = BookingForm()
    open_days = Setting.get_int("booking_open_days", 30)

    if form.validate_on_submit():
        try:
            appointment = booking_service.create_booking(
                current_user, form.slot_id.data, form.reason.data
            )
        except booking_service.BookingError as exc:
            if exc.status == 409:
                return render_template("errors/409.html", message=exc.message), 409
            flash(exc.message, "danger")
            back_date = request.form.get("date") or ""
            return redirect(
                url_for("patient.book", doctor_id=doctor.id, date=back_date)
            )
        flash("Appointment confirmed. A confirmation email has been sent.", "success")
        return redirect(
            url_for("patient.confirmation", booking_id=appointment.booking_id)
        )

    schedule_service.generate_slots(doctor, days=open_days)
    availability = schedule_service.available_dates(doctor, days=14, generate=False)
    date_options = availability
    selected = _parse_date(request.args.get("date"))
    if selected is None and date_options:
        selected = date_options[0]["date"]
    if selected is None:
        selected = date.today()
    if selected < date.today() or selected > date.today() + timedelta(days=open_days):
        selected = date.today()

    payload = slot_service.serialize_slots(doctor.id, selected)
    selected_available = any(row["available"] for row in payload["slots"])
    if date_options and not selected_available:
        for option in date_options:
            if option["date"] >= selected:
                selected = option["date"]
                payload = slot_service.serialize_slots(doctor.id, selected)
                break

    return render_template(
        "patient/book.html",
        doctor=doctor,
        form=form,
        date_options=date_options,
        selected_date=selected,
        payload=payload,
    )


@bp.get("/confirmation/<booking_id>")
@patient_required
def confirmation(booking_id):
    appointment = _appointment_for_patient(booking_id)
    if appointment.appointment_date == date.today():
        estimate = waiting_service.live_wait(appointment)
    else:
        estimate = {
            "patients_ahead": max(0, (appointment.queue_position or 1) - 1),
            "queue_position": appointment.queue_position or 1,
            "estimated_wait_minutes": appointment.estimated_wait_minutes or 0,
            "delay_minutes": 0,
            "avg_consult_minutes": appointment.doctor.avg_consult_minutes,
        }
    return render_template(
        "patient/confirmation.html",
        appointment=appointment,
        estimate=estimate,
        wait_label=humanize_minutes(estimate["estimated_wait_minutes"]),
    )


@bp.get("/appointments")
@patient_required
def appointments():
    scope = request.args.get("scope", "upcoming")
    query = Appointment.query.filter_by(patient_id=current_user.id)
    today = date.today()
    if scope == "upcoming":
        query = query.filter(
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.appointment_date >= today,
        ).order_by(Appointment.appointment_date, Appointment.start_time)
    elif scope == "past":
        query = query.filter(
            or_(
                Appointment.status.in_(
                    (
                        AppointmentStatus.COMPLETED,
                        AppointmentStatus.NO_SHOW,
                    )
                ),
                Appointment.appointment_date < today,
            )
        ).order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc())
    elif scope == "cancelled":
        query = query.filter_by(status=AppointmentStatus.CANCELLED).order_by(
            Appointment.cancelled_at.desc()
        )
    else:
        scope = "all"
        query = query.order_by(
            Appointment.appointment_date.desc(), Appointment.start_time.desc()
        )
    items = query.all()
    cutoff = Setting.get_int("cancellation_cutoff_hours", 2)
    return render_template(
        "patient/appointments.html",
        appointments=items,
        scope=scope,
        cancel_form=CancelForm(),
        cutoff=cutoff,
    )


@bp.get("/appointments/<booking_id>")
@patient_required
def appointment_detail(booking_id):
    appointment = _appointment_for_patient(booking_id)
    cutoff = Setting.get_int("cancellation_cutoff_hours", 2)
    wait = None
    if appointment.appointment_date == date.today() and appointment.is_active:
        wait = waiting_service.live_wait(appointment)
    return render_template(
        "patient/appointment_detail.html",
        appointment=appointment,
        cancel_form=CancelForm(),
        cutoff=cutoff,
        wait=wait,
        wait_label=humanize_minutes(wait["estimated_wait_minutes"]) if wait else None,
    )


@bp.post("/appointments/<booking_id>/cancel")
@patient_required
def cancel(booking_id):
    appointment = _appointment_for_patient(booking_id)
    form = CancelForm()
    if not form.validate_on_submit():
        flash("Please provide a reason for cancellation.", "danger")
        return redirect(url_for("patient.appointment_detail", booking_id=booking_id))
    try:
        booking_service.cancel_booking(appointment, current_user, form.reason.data)
    except booking_service.BookingError as exc:
        if exc.status == 409:
            return render_template("errors/409.html", message=exc.message), 409
        flash(exc.message, "danger")
    else:
        flash(
            "Appointment cancelled. The slot has been released for other patients.",
            "success",
        )
    return redirect(url_for("patient.appointments", scope="upcoming"))
