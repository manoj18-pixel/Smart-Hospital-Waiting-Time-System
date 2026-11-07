"""Admin dashboard and management screens."""
import re
import unicodedata
from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from ..constants import AppointmentStatus, Roles
from ..extensions import db
from ..forms import (
    CancelForm,
    DepartmentForm,
    DoctorForm,
    LeaveForm,
    ScheduleForm,
)
from ..models.appointment import Appointment
from ..models.department import Department
from ..models.doctor import Doctor, DoctorSchedule
from ..models.user import PatientProfile, User
from ..services import (
    audit_service,
    booking_service,
    schedule_service,
    stats_service,
)
from ..utils.decorators import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _department_or_404(department_id):
    item = db.session.get(Department, department_id)
    if item is None:
        abort(404)
    return item


def _doctor_or_404(doctor_id):
    item = db.session.get(Doctor, doctor_id)
    if item is None:
        abort(404)
    return item


def _slugify(value):
    """Dependency-free slug helper (Werkzeug 3 removed ``slugify``)."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def _unique_slug(name, exclude_id=None):
    base = _slugify(name) or "department"
    candidate = base
    counter = 2
    while True:
        query = Department.query.filter_by(slug=candidate)
        if exclude_id:
            query = query.filter(Department.id != exclude_id)
        if query.first() is None:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


def _apply_department_choices(form):
    form.department_id.choices = [
        (item.id, item.name)
        for item in Department.query.order_by(Department.name).all()
    ]


@bp.get("/dashboard")
@admin_required
def dashboard():
    payload = stats_service.dashboard_payload(days=7)
    today_appointments = (
        Appointment.query.filter_by(appointment_date=date.today())
        .order_by(Appointment.start_time)
        .limit(8)
        .all()
    )
    return render_template(
        "admin/dashboard.html", payload=payload, today_appointments=today_appointments
    )


@bp.get("/api/stats")
@admin_required
def stats_api():
    return jsonify(stats_service.dashboard_payload(days=7))


# --------------------------------------------------------------------------- #
# Departments
# --------------------------------------------------------------------------- #
@bp.get("/departments")
@admin_required
def departments():
    items = Department.query.order_by(Department.name).all()
    return render_template("admin/departments.html", departments=items)


@bp.route("/departments/new", methods=["GET", "POST"])
@admin_required
def department_new():
    form = DepartmentForm()
    if form.validate_on_submit():
        item = Department(
            name=form.name.data.strip(),
            slug=_unique_slug(form.name.data),
            description=(form.description.data or "").strip() or None,
            icon=(form.icon.data or "fa-hospital").strip(),
            image_url=(form.image_url.data or "").strip() or None,
            floor=(form.floor.data or "").strip() or None,
            phone_ext=(form.phone_ext.data or "").strip() or None,
            is_active=form.is_active.data,
        )
        db.session.add(item)
        db.session.commit()
        audit_service.log("department_created", "department", item.id)
        flash(f"Department '{item.name}' created.", "success")
        return redirect(url_for("admin.departments"))
    return render_template(
        "admin/department_form.html", form=form, department=None
    )


@bp.route("/departments/<int:department_id>/edit", methods=["GET", "POST"])
@admin_required
def department_edit(department_id):
    item = _department_or_404(department_id)
    form = DepartmentForm(obj=item)
    if form.validate_on_submit():
        item.name = form.name.data.strip()
        item.slug = _unique_slug(item.name, exclude_id=item.id)
        item.description = (form.description.data or "").strip() or None
        item.icon = (form.icon.data or "fa-hospital").strip()
        item.image_url = (form.image_url.data or "").strip() or None
        item.floor = (form.floor.data or "").strip() or None
        item.phone_ext = (form.phone_ext.data or "").strip() or None
        item.is_active = form.is_active.data
        db.session.commit()
        audit_service.log("department_updated", "department", item.id)
        flash("Department updated.", "success")
        return redirect(url_for("admin.departments"))
    return render_template(
        "admin/department_form.html", form=form, department=item
    )


@bp.post("/departments/<int:department_id>/toggle")
@admin_required
def department_toggle(department_id):
    item = _department_or_404(department_id)
    item.is_active = not item.is_active
    db.session.commit()
    audit_service.log(
        "department_toggled", "department", item.id, {"is_active": item.is_active}
    )
    flash(
        f"Department '{item.name}' is now {'active' if item.is_active else 'inactive'}.",
        "info",
    )
    return redirect(url_for("admin.departments"))


# --------------------------------------------------------------------------- #
# Doctors
# --------------------------------------------------------------------------- #
@bp.get("/doctors")
@admin_required
def doctors():
    items = (
        Doctor.query.join(User)
        .order_by(Doctor.is_active.desc(), User.full_name)
        .all()
    )
    return render_template("admin/doctors.html", doctors=items)


@bp.route("/doctors/new", methods=["GET", "POST"])
@admin_required
def doctor_new():
    form = DoctorForm()
    _apply_department_choices(form)
    if form.validate_on_submit():
        user = User(
            role=Roles.DOCTOR,
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=(form.phone.data or "").strip() or None,
        )
        user.set_password(form.password.data)
        doctor = Doctor(
            user=user,
            department_id=form.department_id.data,
            specialization=form.specialization.data.strip(),
            qualification=(form.qualification.data or "").strip() or None,
            experience_years=form.experience_years.data,
            consultation_fee=form.consultation_fee.data,
            room_no=(form.room_no.data or "").strip() or None,
            bio=(form.bio.data or "").strip() or None,
            photo_url=(form.photo_url.data or "").strip() or None,
            avg_consult_minutes=form.avg_consult_minutes.data,
            is_active=form.is_active.data,
        )
        db.session.add(user)
        db.session.add(doctor)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Could not create the doctor account. Email may already be in use.", "danger")
            return render_template("admin/doctor_form.html", form=form, doctor=None)
        audit_service.log("doctor_created", "doctor", doctor.id)
        flash(f"Doctor {doctor.name} created. Add a weekly schedule to open slots.", "success")
        return redirect(url_for("admin.schedules", doctor_id=doctor.id))
    return render_template("admin/doctor_form.html", form=form, doctor=None)


@bp.route("/doctors/<int:doctor_id>/edit", methods=["GET", "POST"])
@admin_required
def doctor_edit(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    form = DoctorForm(editing_user=doctor.user)
    _apply_department_choices(form)
    if request.method == "GET":
        form.full_name.data = doctor.name
        form.email.data = doctor.email
        form.phone.data = doctor.user.phone
        form.department_id.data = doctor.department_id
        form.specialization.data = doctor.specialization
        form.qualification.data = doctor.qualification
        form.experience_years.data = doctor.experience_years
        form.consultation_fee.data = doctor.consultation_fee
        form.room_no.data = doctor.room_no
        form.bio.data = doctor.bio
        form.photo_url.data = doctor.photo_url
        form.avg_consult_minutes.data = doctor.avg_consult_minutes
        form.is_active.data = doctor.is_active
    if form.validate_on_submit():
        doctor.user.full_name = form.full_name.data.strip()
        doctor.user.email = form.email.data.strip().lower()
        doctor.user.phone = (form.phone.data or "").strip() or None
        if form.password.data:
            doctor.user.set_password(form.password.data)
        doctor.department_id = form.department_id.data
        doctor.specialization = form.specialization.data.strip()
        doctor.qualification = (form.qualification.data or "").strip() or None
        doctor.experience_years = form.experience_years.data
        doctor.consultation_fee = form.consultation_fee.data
        doctor.room_no = (form.room_no.data or "").strip() or None
        doctor.bio = (form.bio.data or "").strip() or None
        doctor.photo_url = (form.photo_url.data or "").strip() or None
        doctor.avg_consult_minutes = form.avg_consult_minutes.data
        doctor.is_active = form.is_active.data
        doctor.user.is_active = form.is_active.data
        db.session.commit()
        audit_service.log("doctor_updated", "doctor", doctor.id)
        flash("Doctor updated.", "success")
        return redirect(url_for("admin.doctors"))
    return render_template("admin/doctor_form.html", form=form, doctor=doctor)


@bp.post("/doctors/<int:doctor_id>/toggle")
@admin_required
def doctor_toggle(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    doctor.is_active = not doctor.is_active
    doctor.user.is_active = doctor.is_active
    db.session.commit()
    audit_service.log(
        "doctor_toggled", "doctor", doctor.id, {"is_active": doctor.is_active}
    )
    flash(
        f"Dr. {doctor.name} is now {'active' if doctor.is_active else 'inactive'}.",
        "info",
    )
    return redirect(url_for("admin.doctors"))


# --------------------------------------------------------------------------- #
# Schedules and leave
# --------------------------------------------------------------------------- #
@bp.get("/doctors/<int:doctor_id>/schedules")
@admin_required
def schedules(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    schedule_form = ScheduleForm()
    leave_form = LeaveForm()
    return render_template(
        "admin/schedules.html",
        doctor=doctor,
        schedules=sorted(
            doctor.schedules, key=lambda s: (s.weekday, s.start_time)
        ),
        schedule_form=schedule_form,
        leave_form=leave_form,
    )


@bp.post("/doctors/<int:doctor_id>/schedules")
@admin_required
def schedule_add(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    form = ScheduleForm()
    if form.validate_on_submit():
        item = DoctorSchedule(
            doctor_id=doctor.id,
            weekday=form.weekday.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            slot_duration_minutes=form.slot_duration_minutes.data,
            max_patients=form.max_patients.data,
            is_active=form.is_active.data,
        )
        db.session.add(item)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A schedule starting at that time already exists for this weekday.", "danger")
        else:
            created = schedule_service.generate_slots(doctor)
            audit_service.log("schedule_created", "doctor", doctor.id)
            flash(f"Schedule added. {created} new slots generated.", "success")
    else:
        flash("Please correct the schedule details.", "danger")
    return redirect(url_for("admin.schedules", doctor_id=doctor.id))


@bp.post("/schedules/<int:schedule_id>/delete")
@admin_required
def schedule_delete(schedule_id):
    item = db.session.get(DoctorSchedule, schedule_id)
    if item is None:
        abort(404)
    doctor_id = item.doctor_id
    db.session.delete(item)
    db.session.commit()
    audit_service.log("schedule_deleted", "doctor", doctor_id)
    flash("Schedule template removed. Existing slots are unchanged.", "info")
    return redirect(url_for("admin.schedules", doctor_id=doctor_id))


@bp.post("/doctors/<int:doctor_id>/leave")
@admin_required
def add_leave(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    form = LeaveForm()
    if form.validate_on_submit():
        partial = not form.is_closed.data
        if partial and (not form.start_time.data or not form.end_time.data):
            flash("Provide both times for a partial-day block.", "danger")
        elif partial and form.end_time.data <= form.start_time.data:
            flash("End time must be after start time.", "danger")
        else:
            blocked = schedule_service.block_date(
                doctor,
                form.exception_date.data,
                reason=form.reason.data,
                created_by=current_user.id,
                start=form.start_time.data if partial else None,
                end=form.end_time.data if partial else None,
            )
            audit_service.log("leave_blocked", "doctor", doctor.id, {"date": str(form.exception_date.data)})
            flash(f"Leave saved. {blocked} available slot(s) blocked.", "success")
    else:
        flash("Please provide a valid leave date.", "danger")
    return redirect(url_for("admin.schedules", doctor_id=doctor.id))


@bp.post("/doctors/<int:doctor_id>/generate-slots")
@admin_required
def generate_slots(doctor_id):
    doctor = _doctor_or_404(doctor_id)
    created = schedule_service.generate_slots(doctor)
    flash(f"{created} slot(s) generated for the next 30 days.", "success")
    return redirect(url_for("admin.schedules", doctor_id=doctor.id))


# --------------------------------------------------------------------------- #
# Patients
# --------------------------------------------------------------------------- #
@bp.get("/patients")
@admin_required
def patients():
    query = User.query.filter_by(role=Roles.PATIENT)
    search = (request.args.get("q") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(User.full_name.ilike(like), User.email.ilike(like))
        )
    items = query.order_by(User.created_at.desc()).limit(200).all()
    return render_template("admin/patients.html", patients=items, search=search)


@bp.post("/patients/<int:user_id>/toggle")
@admin_required
def patient_toggle(user_id):
    user = db.session.get(User, user_id)
    if user is None or user.role != Roles.PATIENT:
        abort(404)
    user.is_active = not user.is_active
    db.session.commit()
    audit_service.log("patient_toggled", "user", user.id, {"is_active": user.is_active})
    flash(
        f"{user.full_name} is now {'active' if user.is_active else 'disabled'}.",
        "info",
    )
    return redirect(url_for("admin.patients"))


# --------------------------------------------------------------------------- #
# Appointments
# --------------------------------------------------------------------------- #
@bp.get("/appointments")
@admin_required
def appointments():
    query = Appointment.query
    date_value = (request.args.get("date") or "").strip()
    status_value = (request.args.get("status") or "").strip()
    doctor_value = (request.args.get("doctor_id") or "").strip()
    search = (request.args.get("q") or "").strip()

    if date_value:
        try:
            query = query.filter_by(
                appointment_date=datetime.strptime(date_value, "%Y-%m-%d").date()
            )
        except ValueError:
            pass
    if status_value in AppointmentStatus.ALL:
        query = query.filter_by(status=status_value)
    if doctor_value.isdigit():
        query = query.filter_by(doctor_id=int(doctor_value))
    if search:
        query = query.filter(Appointment.booking_id.ilike(f"%{search}%"))

    items = query.order_by(
        Appointment.appointment_date.desc(), Appointment.start_time.desc()
    ).limit(200).all()
    doctors = Doctor.query.join(User).order_by(User.full_name).all()
    return render_template(
        "admin/appointments.html",
        appointments=items,
        doctors=doctors,
        cancel_form=CancelForm(),
        filters={
            "date": date_value,
            "status": status_value,
            "doctor_id": doctor_value,
            "q": search,
        },
    )


@bp.post("/appointments/<int:appointment_id>/cancel")
@admin_required
def cancel_appointment(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None:
        abort(404)
    form = CancelForm()
    if not form.validate_on_submit():
        flash("A cancellation reason is required.", "danger")
        return redirect(url_for("admin.appointments"))
    try:
        booking_service.cancel_booking(
            appointment, current_user, form.reason.data, is_admin=True
        )
        audit_service.log("admin_booking_cancelled", "appointment", appointment.id)
        flash(
            f"Appointment {appointment.booking_id} cancelled and slot released.",
            "success",
        )
    except booking_service.BookingError as exc:
        flash(exc.message, "danger")
    return redirect(url_for("admin.appointments"))
