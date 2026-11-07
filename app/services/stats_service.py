"""Admin dashboard aggregates."""
from datetime import date, datetime, timedelta
from collections import Counter, OrderedDict

from sqlalchemy import func

from ..constants import AppointmentStatus, SlotStatus
from ..models.appointment import Appointment
from ..models.department import Department
from ..models.doctor import Doctor
from ..models.slot import Slot
from ..models.user import User


def kpis():
    today = date.today()
    now = datetime.now()
    total_appointments = Appointment.query.count()
    cancelled = Appointment.query.filter_by(status=AppointmentStatus.CANCELLED).count()
    return {
        "total_patients": User.query.filter_by(role="patient").count(),
        "total_doctors": Doctor.query.filter_by(is_active=True).count(),
        "total_departments": Department.query.filter_by(is_active=True).count(),
        "appointments_today": Appointment.query.filter_by(appointment_date=today).count(),
        "available_slots_today": Slot.query.filter(
            Slot.slot_date == today,
            Slot.status == SlotStatus.AVAILABLE,
            Slot.start_time > now.time(),
        ).count(),
        "booked_slots_today": Slot.query.filter_by(
            slot_date=today, status=SlotStatus.BOOKED
        ).count(),
        "total_appointments": total_appointments,
        "cancellation_rate": round((cancelled / total_appointments * 100), 1)
        if total_appointments
        else 0,
    }


def bookings_per_day(days=7):
    start = date.today() - timedelta(days=days - 1)
    rows = (
        Appointment.query.with_entities(
            Appointment.appointment_date, func.count(Appointment.id)
        )
        .filter(Appointment.appointment_date >= start)
        .group_by(Appointment.appointment_date)
        .all()
    )
    counts = {row[0]: row[1] for row in rows}
    labels, values = [], []
    for i in range(days):
        day = start + timedelta(days=i)
        labels.append(day.strftime("%d %b"))
        values.append(counts.get(day, 0))
    return {"labels": labels, "values": values}


def department_load():
    rows = (
        Appointment.query.with_entities(Department.name, func.count(Appointment.id))
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .join(Department, Doctor.department_id == Department.id)
        .group_by(Department.name)
        .order_by(func.count(Appointment.id).desc())
        .all()
    )
    return {
        "labels": [row[0] for row in rows],
        "values": [row[1] for row in rows],
    }


def peak_hours():
    rows = (
        Appointment.query.with_entities(
            Appointment.start_time, func.count(Appointment.id)
        )
        .group_by(Appointment.start_time)
        .all()
    )
    counts = Counter()
    for start_time, count in rows:
        counts[f"{start_time.hour:02d}:00"] += count
    ordered = OrderedDict(sorted(counts.items()))
    return {"labels": list(ordered.keys()), "values": list(ordered.values())}


def slot_utilization(days=7):
    start = date.today()
    end = start + timedelta(days=days - 1)
    available = Slot.query.filter(
        Slot.slot_date.between(start, end), Slot.status == SlotStatus.AVAILABLE
    ).count()
    booked = Slot.query.filter(
        Slot.slot_date.between(start, end), Slot.status == SlotStatus.BOOKED
    ).count()
    return {
        "labels": ["Booked", "Available"],
        "values": [booked, available],
        "booked": booked,
        "available": available,
    }


def dashboard_payload(days=7):
    return {
        "kpis": kpis(),
        "bookings_per_day": bookings_per_day(days),
        "department_load": department_load(),
        "peak_hours": peak_hours(),
        "slot_utilization": slot_utilization(days),
    }
