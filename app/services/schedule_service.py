"""Turn weekly schedule templates into dated slots."""
from datetime import date, datetime, time, timedelta

from ..constants import SlotStatus
from ..extensions import db
from ..models.doctor import Doctor, ScheduleException
from ..models.setting import Setting
from ..models.slot import Slot


def _window(doctor, day):
    return [s for s in doctor.schedules if s.is_active and s.weekday == day.weekday()]


def _exceptions(doctor, day):
    return [e for e in doctor.exceptions if e.exception_date == day]


def generate_slots(doctor, start_date=None, days=None):
    """Idempotently create missing slots for a doctor. Returns count created."""
    start = start_date or date.today()
    days = days or Setting.get_int("booking_open_days", 30)
    end = start + timedelta(days=days - 1)
    existing = {
        (slot.slot_date, slot.start_time)
        for slot in doctor.slots.filter(Slot.slot_date.between(start, end)).all()
    }
    now = datetime.now()
    created = 0

    for offset in range(days):
        day = start + timedelta(days=offset)
        if day < date.today():
            continue
        exceptions = _exceptions(doctor, day)
        for template in _window(doctor, day):
            duration = timedelta(minutes=int(template.slot_duration_minutes or 20))
            cursor = datetime.combine(day, template.start_time)
            window_end = datetime.combine(day, template.end_time)
            count = 0
            while cursor + duration <= window_end:
                slot_end = cursor + duration
                if template.max_patients and count >= template.max_patients:
                    break
                if cursor > now and not any(
                    exc.covers(cursor.time(), slot_end.time()) for exc in exceptions
                ):
                    key = (day, cursor.time())
                    if key not in existing:
                        db.session.add(
                            Slot(
                                doctor_id=doctor.id,
                                slot_date=day,
                                start_time=cursor.time(),
                                end_time=slot_end.time(),
                                status=SlotStatus.AVAILABLE,
                                fee=doctor.consultation_fee,
                            )
                        )
                        existing.add(key)
                        created += 1
                cursor = slot_end
                count += 1

    if created:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            created = 0
    return created


def generate_all_slots(days=None):
    total = 0
    for doctor in Doctor.query.filter_by(is_active=True).all():
        total += generate_slots(doctor, days=days)
    return total


def available_dates(doctor, days=14, generate=True):
    if generate:
        generate_slots(doctor, days=max(days, 30))
    today = date.today()
    last = today + timedelta(days=days - 1)
    rows = (
        Slot.query.with_entities(Slot.slot_date)
        .filter(
            Slot.doctor_id == doctor.id,
            Slot.slot_date.between(today, last),
            Slot.status == SlotStatus.AVAILABLE,
        )
        .distinct()
        .order_by(Slot.slot_date)
        .all()
    )
    # Filter same-day slots that have already started in Python for portability.
    now = datetime.now()
    result = []
    for (day,) in rows:
        slots = [
            slot
            for slot in Slot.query.filter_by(
                doctor_id=doctor.id, slot_date=day, status=SlotStatus.AVAILABLE
            ).all()
            if slot.starts_at > now
        ]
        if slots:
            result.append({"date": day, "available": len(slots)})
    return result


def next_available(doctor, from_date=None):
    from_date = from_date or date.today()
    slots = (
        Slot.query.filter(
            Slot.doctor_id == doctor.id,
            Slot.slot_date >= from_date,
            Slot.status == SlotStatus.AVAILABLE,
        )
        .order_by(Slot.slot_date, Slot.start_time)
        .all()
    )
    # Only same-day slots can already have started; compare full datetimes in
    # Python so future dates are not filtered by today's clock time.
    now = datetime.now()
    for slot in slots:
        if slot.starts_at > now:
            return slot
    return None


def block_date(doctor, day, reason=None, created_by=None, start=None, end=None):
    exception = ScheduleException(
        doctor_id=doctor.id,
        exception_date=day,
        is_closed=start is None and end is None,
        start_time=start,
        end_time=end,
        reason=reason,
        created_by=created_by,
    )
    db.session.add(exception)

    query = Slot.query.filter(
        Slot.doctor_id == doctor.id,
        Slot.slot_date == day,
        Slot.status == SlotStatus.AVAILABLE,
    )
    blocked = 0
    for slot in query.all():
        if start and end and not (slot.start_time < end and slot.end_time > start):
            continue
        slot.status = SlotStatus.BLOCKED
        blocked += 1
    db.session.commit()
    return blocked
