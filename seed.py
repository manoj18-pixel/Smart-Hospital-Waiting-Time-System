"""Seed MediQueue with a realistic demo hospital.

Usage (from ``smart-hospital/``)::

    ..\\.venv\\Scripts\\python.exe -m flask --app run.py seed

The seeder is idempotent: if the admin account already exists it does nothing
apart from topping up future slots.
"""
from datetime import date, datetime, time, timedelta

from app.constants import (
    DEFAULT_SETTINGS,
    AppointmentStatus,
    Roles,
    SlotStatus,
)
from app.extensions import db
from app.models.appointment import Appointment
from app.models.department import Department
from app.models.doctor import Doctor, DoctorSchedule
from app.models.setting import Setting
from app.models.slot import Slot
from app.models.user import PatientProfile, User
from app.services import booking_service, schedule_service

ADMIN_EMAIL = "admin@mediqueue.local"
ADMIN_PASSWORD = "Admin@123"
DOCTOR_PASSWORD = "Doctor@123"
PATIENT_PASSWORD = "Patient@123"

DEPARTMENTS = [
    {
        "name": "Cardiology",
        "icon": "fa-heart-pulse",
        "floor": "3rd floor",
        "phone_ext": "301",
        "description": "Heart health, ECG, echocardiography and interventional cardiac care.",
    },
    {
        "name": "Neurology",
        "icon": "fa-brain",
        "floor": "4th floor",
        "phone_ext": "401",
        "description": "Brain, spine and nervous-system care from experienced neurologists.",
    },
    {
        "name": "Orthopaedics",
        "icon": "fa-bone",
        "floor": "2nd floor",
        "phone_ext": "201",
        "description": "Bone, joint and sports-injury care, including physiotherapy support.",
    },
    {
        "name": "Paediatrics",
        "icon": "fa-baby",
        "floor": "1st floor",
        "phone_ext": "101",
        "description": "Child-friendly outpatient care, vaccinations and growth monitoring.",
    },
    {
        "name": "Dermatology",
        "icon": "fa-allergies",
        "floor": "2nd floor",
        "phone_ext": "205",
        "description": "Skin, hair and nail conditions with evidence-based treatment.",
    },
    {
        "name": "General Medicine",
        "icon": "fa-stethoscope",
        "floor": "Ground floor",
        "phone_ext": "005",
        "description": "Everyday health concerns, fever, infections and preventive check-ups.",
    },
    {
        "name": "ENT",
        "icon": "fa-ear-listen",
        "floor": "1st floor",
        "phone_ext": "110",
        "description": "Ear, nose and throat care for children and adults.",
    },
    {
        "name": "Gynaecology",
        "icon": "fa-person-dress",
        "floor": "3rd floor",
        "phone_ext": "310",
        "description": "Women's health, antenatal care and reproductive medicine.",
    },
]

DOCTORS = [
    {
        "name": "Arjun Mehta",
        "email": "dr.arjun@mediqueue.local",
        "department": "Cardiology",
        "specialization": "Interventional Cardiologist",
        "qualification": "MBBS, MD, DM (Cardiology)",
        "experience": 14,
        "fee": 900,
        "room": "C-204",
        "avg": 18,
        "phone": "+91 98450 11001",
        "bio": "Dr. Arjun Mehta specialises in angioplasty, preventive cardiology and the management of complex hypertension. He believes every patient should leave a consultation understanding their own heart health.",
        "windows": [((0, 1, 2, 3, 4, 5), time(9, 0), time(13, 0), 20)],
    },
    {
        "name": "Kavya Rao",
        "email": "dr.kavya@mediqueue.local",
        "department": "Neurology",
        "specialization": "Neurologist & Epileptologist",
        "qualification": "MBBS, MD, DM (Neurology)",
        "experience": 11,
        "fee": 800,
        "room": "N-402",
        "avg": 22,
        "phone": "+91 98450 11002",
        "bio": "Dr. Kavya Rao treats migraine, epilepsy and movement disorders, with a focus on long-term quality of life.",
        "windows": [((0, 2, 4), time(10, 0), time(14, 0), 20)],
    },
    {
        "name": "Rahul Deshmukh",
        "email": "dr.rahul@mediqueue.local",
        "department": "Orthopaedics",
        "specialization": "Joint Replacement Surgeon",
        "qualification": "MBBS, MS (Orthopaedics)",
        "experience": 16,
        "fee": 750,
        "room": "O-201",
        "avg": 15,
        "phone": "+91 98450 11003",
        "bio": "Dr. Rahul Deshmukh performs knee and hip replacements and manages sports injuries with a rehabilitation-first approach.",
        "windows": [((1, 3, 5), time(9, 30), time(13, 30), 20), ((0, 2), time(15, 0), time(18, 0), 30)],
    },
    {
        "name": "Sana Qureshi",
        "email": "dr.sana@mediqueue.local",
        "department": "Paediatrics",
        "specialization": "Paediatrician & Neonatologist",
        "qualification": "MBBS, MD (Paediatrics)",
        "experience": 9,
        "fee": 600,
        "room": "P-108",
        "avg": 12,
        "phone": "+91 98450 11004",
        "bio": "Dr. Sana Qureshi looks after newborns, children and adolescents, and is known for a calm, reassuring manner with anxious parents.",
        "windows": [((0, 1, 2, 3, 4, 5), time(10, 0), time(13, 0), 15), ((0, 2, 4), time(16, 0), time(19, 0), 15)],
    },
    {
        "name": "Meera Krishnan",
        "email": "dr.meera@mediqueue.local",
        "department": "Dermatology",
        "specialization": "Dermatologist & Trichologist",
        "qualification": "MBBS, MD (Dermatology)",
        "experience": 8,
        "fee": 650,
        "room": "D-205",
        "avg": 14,
        "phone": "+91 98450 11005",
        "bio": "Dr. Meera Krishnan treats acne, eczema, pigmentation and hair loss with tailored, evidence-based regimens.",
        "windows": [((1, 3, 5), time(11, 0), time(15, 0), 20)],
    },
    {
        "name": "Vikram Singh",
        "email": "dr.vikram@mediqueue.local",
        "department": "General Medicine",
        "specialization": "Internal Medicine Consultant",
        "qualification": "MBBS, MD (Internal Medicine)",
        "experience": 12,
        "fee": 500,
        "room": "G-006",
        "avg": 10,
        "phone": "+91 98450 11006",
        "bio": "Dr. Vikram Singh handles fever, diabetes, thyroid disorders and preventive health checks for the whole family.",
        "windows": [((0, 1, 2, 3, 4, 5), time(8, 30), time(12, 30), 15), ((0, 1, 2, 3, 4, 5), time(17, 0), time(20, 0), 15)],
    },
    {
        "name": "Ananya Bose",
        "email": "dr.ananya@mediqueue.local",
        "department": "ENT",
        "specialization": "ENT Surgeon",
        "qualification": "MBBS, MS (ENT)",
        "experience": 10,
        "fee": 700,
        "room": "E-112",
        "avg": 16,
        "phone": "+91 98450 11007",
        "bio": "Dr. Ananya Bose manages sinus disease, hearing loss and paediatric ENT problems, including minimally invasive surgery.",
        "windows": [((0, 2, 4, 6), time(9, 0), time(12, 0), 20)],
    },
    {
        "name": "Farah Khan",
        "email": "dr.farah@mediqueue.local",
        "department": "Gynaecology",
        "specialization": "Obstetrician & Gynaecologist",
        "qualification": "MBBS, MS (OBG)",
        "experience": 13,
        "fee": 850,
        "room": "Y-310",
        "avg": 20,
        "phone": "+91 98450 11008",
        "bio": "Dr. Farah Khan provides antenatal care, fertility counselling and minimally invasive gynaecological surgery.",
        "windows": [((0, 1, 3, 5), time(10, 0), time(14, 0), 20)],
    },
]

PATIENTS = [
    ("Asha Verma", "asha@example.com", "+91 99887 22001", "Female", "O+", "1994-04-18"),
    ("Ravi Kumar", "ravi@example.com", "+91 99887 22002", "Male", "B+", "1988-09-02"),
    ("Meera Iyer", "meera@example.com", "+91 99887 22003", "Female", "A+", "1999-12-11"),
    ("Priya Nair", "priya@example.com", "+91 99887 22004", "Female", "AB+", "1991-06-27"),
    ("Aarav Sharma", "aarav@example.com", "+91 99887 22005", "Male", "O-", "1985-01-09"),
    ("Neha Gupta", "neha@example.com", "+91 99887 22006", "Female", "B-", "1997-08-30"),
]


def _get_or_create_user(full_name, email, password, role, phone=None):
    user = User.query.filter_by(email=email).first()
    if user:
        return user, False
    user = User(role=role, full_name=full_name, email=email, phone=phone)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user, True


def _ensure_settings():
    for key, value in DEFAULT_SETTINGS.items():
        if db.session.get(Setting, key) is None:
            Setting.set(key, value)


def _ensure_departments():
    mapping = {}
    for index, data in enumerate(DEPARTMENTS):
        department = Department.query.filter_by(name=data["name"]).first()
        if department is None:
            department = Department(
                name=data["name"],
                slug=data["name"].lower().replace(" ", "-"),
                description=data["description"],
                icon=data["icon"],
                floor=data["floor"],
                phone_ext=data["phone_ext"],
                is_active=True,
            )
            db.session.add(department)
            db.session.flush()
        mapping[data["name"]] = department
    return mapping


def _ensure_doctors(departments):
    doctors = []
    for data in DOCTORS:
        user, created = _get_or_create_user(
            data["name"], data["email"], DOCTOR_PASSWORD, Roles.DOCTOR, data["phone"]
        )
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if doctor is None:
            doctor = Doctor(
                user_id=user.id,
                department_id=departments[data["department"]].id,
                specialization=data["specialization"],
                qualification=data["qualification"],
                experience_years=data["experience"],
                consultation_fee=data["fee"],
                room_no=data["room"],
                bio=data["bio"],
                avg_consult_minutes=data["avg"],
                is_active=True,
            )
            db.session.add(doctor)
            db.session.flush()
        doctors.append((doctor, data))
    return doctors


def _ensure_schedules(doctors):
    created = 0
    for doctor, data in doctors:
        existing = {(s.weekday, s.start_time) for s in doctor.schedules}
        for weekdays, start, end, duration in data["windows"]:
            for weekday in weekdays:
                key = (weekday, start)
                if key in existing:
                    continue
                db.session.add(
                    DoctorSchedule(
                        doctor_id=doctor.id,
                        weekday=weekday,
                        start_time=start,
                        end_time=end,
                        slot_duration_minutes=duration,
                        is_active=True,
                    )
                )
                existing.add(key)
                created += 1
    return created


def _ensure_patients():
    patients = []
    for name, email, phone, gender, blood, dob in PATIENTS:
        user, created = _get_or_create_user(name, email, PATIENT_PASSWORD, Roles.PATIENT, phone)
        if created and user.patient_profile is None:
            user.patient_profile = PatientProfile(
                gender=gender,
                blood_group=blood,
                date_of_birth=date.fromisoformat(dob),
                address="12 Wellness Avenue, Medical District",
                emergency_contact="+91 99887 22999",
            )
        patients.append(user)
    return patients


def _find_slot(doctor, start_day, exact_day=False):
    """Return the next genuinely bookable slot for a doctor.

    ``start_day`` is a lower bound; if the doctor does not work that weekday
    the search rolls forward to their next OPD day. ``exact_day`` restricts the
    search to a single date (used for today's live demo queue).
    """
    query = Slot.query.filter(
        Slot.doctor_id == doctor.id,
        Slot.status == SlotStatus.AVAILABLE,
    )
    if exact_day:
        query = query.filter(Slot.slot_date == start_day)
    else:
        query = query.filter(Slot.slot_date >= start_day)
    for slot in query.order_by(Slot.slot_date, Slot.start_time).all():
        if slot.starts_at > datetime.now():
            return slot
    return None


def _book(patient, doctor, start_day, reason, exact_day=False, quiet=False):
    slot = _find_slot(doctor, start_day, exact_day=exact_day)
    if slot is None:
        if not quiet:
            print(
                f"  ! no available slot for {patient.full_name} with Dr. {doctor.name}"
                f" from {start_day.isoformat()}"
            )
        return None
    try:
        return booking_service.create_booking(patient, slot.id, reason)
    except booking_service.BookingError as exc:
        if not quiet:
            print(
                f"  ! could not book {patient.full_name} with Dr. {doctor.name}:"
                f" {exc.message}"
            )
        return None


def _force_book(patient, doctor, day, reason, position):
    """Book a same-day demo slot even if its clock time has already passed.

    Real bookings are refused once a slot starts. The seeder uses this only for
    today's queue so the doctor dashboard and live waiting-time screens have
    data no matter what time of day the project is demonstrated.
    """
    slot = (
        Slot.query.filter_by(
            doctor_id=doctor.id, slot_date=day, status=SlotStatus.AVAILABLE
        )
        .order_by(Slot.start_time)
        .first()
    )
    if slot is None:
        # Slot generation only creates future times, so an afternoon demo has
        # no rows for today. Create a synthetic slot at a free time for the
        # same-day demo queue.
        used = {
            row.start_time
            for row in Slot.query.filter_by(doctor_id=doctor.id, slot_date=day).all()
        }
        cursor = datetime.combine(day, time(8, 0))
        while cursor.time() in used:
            cursor += timedelta(minutes=20)
        slot = Slot(
            doctor_id=doctor.id,
            slot_date=day,
            start_time=cursor.time(),
            end_time=(cursor + timedelta(minutes=20)).time(),
            status=SlotStatus.BOOKED,
            fee=doctor.consultation_fee,
        )
        db.session.add(slot)
        db.session.flush()
    else:
        slot.status = SlotStatus.BOOKED
    same_day = Appointment.query.filter(Appointment.appointment_date == day).count()
    appointment = Appointment(
        booking_id=f"MQ-{day:%Y%m%d}-{same_day + 1:04d}",
        patient_id=patient.id,
        doctor_id=doctor.id,
        slot_id=slot.id,
        appointment_date=day,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=AppointmentStatus.CONFIRMED,
        reason_for_visit=reason,
        fee=slot.fee if slot.fee is not None else doctor.consultation_fee,
        queue_position=position,
        estimated_wait_minutes=max(
            0, (position - 1) * int(doctor.avg_consult_minutes or 15)
        ),
    )
    db.session.add(appointment)
    db.session.commit()
    return appointment


def _seed_appointments(patients, doctors_by_email, admin):
    today = date.today()
    created = 0

    arjun = doctors_by_email["dr.arjun@mediqueue.local"]
    # A small live queue for today. If the OPD window has already ended, seed
    # the queue directly so the demo still has live data in the afternoon.
    today_appointments = []
    for patient, reason in zip(patients[:4], [
        "Chest discomfort while climbing stairs",
        "Routine blood-pressure review",
        "Palpitations at night",
        "Follow-up after ECG",
    ]):
        appointment = _book(patient, arjun, today, reason, exact_day=True, quiet=True)
        if appointment is None:
            appointment = _force_book(
                patient, arjun, today, reason, len(today_appointments) + 1
            )
        if appointment:
            today_appointments.append(appointment)
            created += 1
    if today_appointments:
        booking_service.check_in(today_appointments[0])

    # Future appointments across departments.
    future_plan = [
        (patients[1], "dr.kavya@mediqueue.local", 1, "Recurring migraine"),
        (patients[2], "dr.sana@mediqueue.local", 1, "Child vaccination review"),
        (patients[3], "dr.vikram@mediqueue.local", 2, "Fever and fatigue"),
        (patients[4], "dr.meera@mediqueue.local", 2, "Persistent skin rash"),
        (patients[0], "dr.farah@mediqueue.local", 3, "Antenatal check-up"),
        (patients[5], "dr.ananya@mediqueue.local", 3, "Blocked ear and hearing loss"),
    ]
    for patient, email, offset, reason in future_plan:
        doctor = doctors_by_email.get(email)
        if doctor is None:
            continue
        appointment = _book(patient, doctor, today + timedelta(days=offset), reason)
        if appointment:
            created += 1

    # One completed visit and one cancelled visit for history screens.
    completed = _book(
        patients[5],
        doctors_by_email["dr.vikram@mediqueue.local"],
        today + timedelta(days=1),
        "Annual health check",
    )
    if completed:
        completed.status = AppointmentStatus.COMPLETED
        completed.completed_at = datetime.utcnow()
        db.session.commit()
        created += 1

    cancelled = _book(
        patients[2],
        doctors_by_email["dr.rahul@mediqueue.local"],
        today + timedelta(days=4),
        "Knee pain review",
    )
    if cancelled:
        try:
            booking_service.cancel_booking(
                cancelled, cancelled.patient, "Travel plans changed", is_admin=True
            )
        except booking_service.BookingError:
            pass
        created += 1

    return created


def seed_database(app):
    """Create demo data inside the application context."""
    with app.app_context():
        db.create_all()
        _ensure_settings()

        admin, admin_created = _get_or_create_user(
            "Hospital Administrator", ADMIN_EMAIL, ADMIN_PASSWORD, Roles.ADMIN, "+91 80 4567 8900"
        )
        if not admin_created and Department.query.count() > 0:
            # Already seeded: just make sure future slots keep flowing.
            total = schedule_service.generate_all_slots(days=30)
            db.session.commit()
            print("Demo data already present; generated", total, "new slot(s).")
            return

        departments = _ensure_departments()
        doctors = _ensure_doctors(departments)
        schedules_created = _ensure_schedules(doctors)
        patients = _ensure_patients()
        db.session.commit()

        print(f"Created {len(departments)} departments, {len(doctors)} doctors, {schedules_created} schedule windows, {len(patients)} patients.")

        total_slots = 0
        for doctor, _data in doctors:
            total_slots += schedule_service.generate_slots(doctor, days=30)
        print(f"Generated {total_slots} bookable slots for the next 30 days.")

        created = _seed_appointments(patients, {d.user.email: d for d, _ in doctors}, admin)
        print(f"Created {created} demo appointments.")

        print("\nDemo credentials")
        print("  Admin   :", ADMIN_EMAIL, "/", ADMIN_PASSWORD)
        print("  Doctor  :", DOCTORS[0]["email"], "/", DOCTOR_PASSWORD)
        print("  Patient :", PATIENTS[0][1], "/", PATIENT_PASSWORD)
