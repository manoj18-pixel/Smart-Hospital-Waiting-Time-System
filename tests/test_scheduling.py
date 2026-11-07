"""T17 — Weekly schedule generation and leave blocking."""
from datetime import date, time, timedelta

from app.constants import SlotStatus
from app.extensions import db
from app.models.doctor import ScheduleException
from app.models.slot import Slot
from app.services import schedule_service

from .factories import (
    TEST_PASSWORD,
    future_day,
    make_doctor,
    make_schedule,
    make_slot,
)


def test_generate_slots_from_weekly_window(app, base):
    day = future_day(1)
    make_schedule(base.doctor, weekday=day.weekday(), start=time(9, 0), end=time(10, 0), duration=20)
    db.session.commit()

    created = schedule_service.generate_slots(base.doctor, days=2)
    assert created == 3
    generated = Slot.query.filter_by(doctor_id=base.doctor.id, slot_date=day).order_by(Slot.start_time).all()
    assert [slot.start_time for slot in generated] == [time(9, 0), time(9, 20), time(9, 40)]
    assert all(slot.status == SlotStatus.AVAILABLE for slot in generated)


def test_generation_is_idempotent(app, base):
    day = future_day(1)
    make_schedule(base.doctor, weekday=day.weekday(), start=time(9, 0), end=time(10, 0), duration=20)
    db.session.commit()

    assert schedule_service.generate_slots(base.doctor, days=2) == 3
    assert schedule_service.generate_slots(base.doctor, days=2) == 0
    assert Slot.query.filter_by(doctor_id=base.doctor.id, slot_date=day).count() == 3


def test_doctor_without_schedule_generates_nothing(app, base):
    assert schedule_service.generate_slots(base.other_doctor, days=5) == 0
    assert Slot.query.filter_by(doctor_id=base.other_doctor.id).count() == 0


def test_max_patients_caps_generated_slots(app, base):
    day = future_day(1)
    make_schedule(
        base.doctor,
        weekday=day.weekday(),
        start=time(9, 0),
        end=time(12, 0),
        duration=20,
        max_patients=2,
    )
    db.session.commit()

    assert schedule_service.generate_slots(base.doctor, days=2) == 2


def test_inactive_schedule_is_ignored(app, base):
    day = future_day(1)
    make_schedule(
        base.doctor,
        weekday=day.weekday(),
        start=time(9, 0),
        end=time(10, 0),
        duration=20,
        is_active=False,
    )
    db.session.commit()

    assert schedule_service.generate_slots(base.doctor, days=2) == 0


def test_full_day_leave_blocks_available_slots_only(app, base):
    day = future_day(1)
    make_slot(base.doctor, day=day, start=time(9, 0))
    make_slot(base.doctor, day=day, start=time(9, 20))
    booked = make_slot(base.doctor, day=day, start=time(9, 40), status=SlotStatus.BOOKED)
    db.session.commit()

    blocked = schedule_service.block_date(base.doctor, day, reason="Conference")
    assert blocked == 2
    assert ScheduleException.query.filter_by(doctor_id=base.doctor.id, exception_date=day).count() == 1

    db.session.expire_all()
    statuses = {
        slot.start_time: slot.status
        for slot in Slot.query.filter_by(doctor_id=base.doctor.id, slot_date=day).all()
    }
    assert statuses[time(9, 0)] == SlotStatus.BLOCKED
    assert statuses[time(9, 20)] == SlotStatus.BLOCKED
    assert statuses[time(9, 40)] == SlotStatus.BOOKED
    assert db.session.get(Slot, booked.id).status == SlotStatus.BOOKED


def test_partial_leave_blocks_overlapping_slots(app, base):
    day = future_day(1)
    for clock in (time(9, 0), time(9, 20), time(9, 40)):
        make_slot(base.doctor, day=day, start=clock)
    db.session.commit()

    blocked = schedule_service.block_date(
        base.doctor, day, reason="Surgery", start=time(9, 20), end=time(9, 50)
    )
    assert blocked == 2

    db.session.expire_all()
    statuses = {
        slot.start_time: slot.status
        for slot in Slot.query.filter_by(doctor_id=base.doctor.id, slot_date=day).all()
    }
    assert statuses[time(9, 0)] == SlotStatus.AVAILABLE
    assert statuses[time(9, 20)] == SlotStatus.BLOCKED
    assert statuses[time(9, 40)] == SlotStatus.BLOCKED


def test_available_dates_and_next_available(app, base):
    day = future_day(2)
    make_slot(base.doctor, day=day, start=time(10, 0))
    db.session.commit()

    availability = schedule_service.available_dates(base.doctor, days=14, generate=False)
    assert any(item["date"] == day and item["available"] == 1 for item in availability)

    slot = schedule_service.next_available(base.doctor, from_date=day)
    assert slot is not None
    assert slot.slot_date == day


def test_admin_generate_slots_route(app, base):
    day = future_day(1)
    make_schedule(base.doctor, weekday=day.weekday(), start=time(9, 0), end=time(10, 0), duration=20)
    db.session.commit()

    client = app.test_client()
    client.post("/login", data={"email": base.admin.email, "password": TEST_PASSWORD})
    response = client.post(f"/admin/doctors/{base.doctor.id}/generate-slots")
    assert response.status_code == 302

    # The route fills the whole booking window (30 days by default), so the
    # same weekday is generated several times. Each generated day must contain
    # exactly the three 20-minute slots described by the schedule.
    generated = Slot.query.filter_by(doctor_id=base.doctor.id).all()
    assert generated
    assert {slot.slot_date.weekday() for slot in generated} == {day.weekday()}
    assert Slot.query.filter_by(doctor_id=base.doctor.id, slot_date=day).count() == 3
    assert len(generated) % 3 == 0
