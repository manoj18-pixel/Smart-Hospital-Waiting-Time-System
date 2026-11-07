"""T20 (plan T20/T13) — Waiting-time and queue-position calculations."""
from datetime import date, datetime, time

from app.constants import AppointmentStatus, SlotStatus
from app.extensions import db
from app.services import waiting_service
from app.utils.time_utils import humanize_minutes

from .factories import future_day, make_appointment, make_slot


def _queue(doctor, day, patient, starts, status=AppointmentStatus.CONFIRMED):
    appointments = []
    for index, clock in enumerate(starts):
        slot = make_slot(doctor, day=day, start=clock, status=SlotStatus.BOOKED)
        appointments.append(
            make_appointment(patient, slot, status=status, booking_id=f"MQ-Q{index:03d}")
        )
    return appointments


def test_estimate_counts_patients_ahead_and_delay(app, base):
    day = future_day(2)
    _queue(
        base.doctor,
        day,
        base.other_patient,
        [time(9, 0), time(9, 20), time(9, 40)],
    )
    waiting_service.set_delay_minutes(base.doctor.id, 5, day)
    db.session.commit()

    estimate = waiting_service.estimate_for_new_booking(base.doctor, day, time(10, 0))
    assert estimate["patients_ahead"] == 3
    assert estimate["queue_position"] == 4
    assert estimate["estimated_wait_minutes"] == 3 * 15 + 5
    assert estimate["delay_minutes"] == 5
    assert estimate["avg_consult_minutes"] == 15


def test_empty_queue_reports_no_wait(app, base):
    day = future_day(3)
    estimate = waiting_service.estimate_for_new_booking(base.other_doctor, day, time(10, 0))
    assert estimate["patients_ahead"] == 0
    assert estimate["queue_position"] == 1
    assert estimate["estimated_wait_minutes"] == 0
    assert humanize_minutes(estimate["estimated_wait_minutes"]) == "No wait"


def test_cancelled_and_completed_appointments_do_not_count(app, base):
    day = future_day(2)
    cancelled_slot = make_slot(base.doctor, day=day, start=time(9, 0), status=SlotStatus.BOOKED)
    make_appointment(
        base.other_patient, cancelled_slot, status=AppointmentStatus.CANCELLED
    )
    completed_slot = make_slot(base.doctor, day=day, start=time(9, 20), status=SlotStatus.BOOKED)
    make_appointment(
        base.other_patient, completed_slot, status=AppointmentStatus.COMPLETED
    )
    checked_slot = make_slot(base.doctor, day=day, start=time(9, 40), status=SlotStatus.BOOKED)
    make_appointment(
        base.other_patient, checked_slot, status=AppointmentStatus.CHECKED_IN
    )
    db.session.commit()

    assert waiting_service.patients_ahead(base.doctor.id, day, time(10, 0)) == 1


def test_delay_is_per_doctor_and_per_day(app, base):
    day = future_day(2)
    assert waiting_service.delay_minutes(base.doctor.id, day) == 0
    waiting_service.set_delay_minutes(base.doctor.id, 12, day)
    db.session.commit()

    assert waiting_service.delay_minutes(base.doctor.id, day) == 12
    assert waiting_service.delay_minutes(base.doctor.id, future_day(3)) == 0
    assert waiting_service.delay_minutes(base.other_doctor.id, day) == 0


def test_live_wait_counts_checked_in_patients(app, base):
    today = date.today()
    checked_slot = make_slot(base.doctor, day=today, start=time(9, 0), status=SlotStatus.BOOKED)
    make_appointment(
        base.other_patient, checked_slot, status=AppointmentStatus.CHECKED_IN
    )
    current_slot = make_slot(base.doctor, day=today, start=time(11, 0), status=SlotStatus.BOOKED)
    current = make_appointment(base.patient, current_slot, status=AppointmentStatus.CONFIRMED)
    waiting_service.set_delay_minutes(base.doctor.id, 5, today)
    db.session.commit()

    estimate = waiting_service.live_wait(current)
    assert estimate["patients_ahead"] == 1
    assert estimate["queue_position"] == 2
    assert estimate["estimated_wait_minutes"] == 15 + 5


def test_live_wait_uses_scheduled_order_not_wall_clock(app, base, monkeypatch):
    """The first patient of the day must not inherit the whole queue.

    A late-evening clinic used to count every earlier confirmed appointment as
    "ahead" for every patient, so the first patient saw position 4. Queue order
    comes from the schedule, not from the current clock time.
    """

    class LateEvening(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.combine(date.today(), time(23, 59))

    monkeypatch.setattr(waiting_service, "datetime", LateEvening)

    today = date.today()
    first_slot = make_slot(base.doctor, day=today, start=time(9, 0), status=SlotStatus.BOOKED)
    first = make_appointment(
        base.patient, first_slot, status=AppointmentStatus.CHECKED_IN
    )
    for index, clock in enumerate((time(9, 20), time(9, 40))):
        slot = make_slot(base.doctor, day=today, start=clock, status=SlotStatus.BOOKED)
        make_appointment(
            base.other_patient,
            slot,
            status=AppointmentStatus.CONFIRMED,
            booking_id=f"MQ-LATE{index}",
        )
    db.session.commit()

    estimate = waiting_service.live_wait(first)
    assert estimate["patients_ahead"] == 0
    assert estimate["queue_position"] == 1
    assert estimate["estimated_wait_minutes"] == 0


def test_humanize_minutes_formats_readably():
    assert humanize_minutes(0) == "No wait"
    assert humanize_minutes(-5) == "No wait"
    assert humanize_minutes(45) == "~45 min"
    assert humanize_minutes(60) == "~1 hr"
    assert humanize_minutes(65) == "~1 hr 5 min"
    assert humanize_minutes(120) == "~2 hr"


def test_doctor_queue_is_ordered_by_time(app, base):
    day = future_day(2)
    late = make_slot(base.doctor, day=day, start=time(11, 0), status=SlotStatus.BOOKED)
    early = make_slot(base.doctor, day=day, start=time(9, 0), status=SlotStatus.BOOKED)
    make_appointment(base.patient, late)
    make_appointment(base.other_patient, early)
    db.session.commit()

    queue = waiting_service.doctor_queue(base.doctor.id, day)
    assert [item.start_time for item in queue] == [time(9, 0), time(11, 0)]
