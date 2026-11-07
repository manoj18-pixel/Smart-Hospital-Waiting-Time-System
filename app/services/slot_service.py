"""Slot reading and atomic status transitions."""
from datetime import datetime

from sqlalchemy import update

from ..constants import SlotStatus
from ..extensions import db
from ..models.slot import Slot
from ..utils.time_utils import format_time


def slots_for_date(doctor_id, day):
    return (
        Slot.query.filter_by(doctor_id=doctor_id, slot_date=day)
        .order_by(Slot.start_time)
        .all()
    )


def display_status(slot, now=None):
    now = now or datetime.now()
    if slot.status == SlotStatus.AVAILABLE and slot.starts_at <= now:
        return SlotStatus.CLOSED
    return slot.status


def serialize_slots(doctor_id, day):
    now = datetime.now()
    slots = slots_for_date(doctor_id, day)
    rows = []
    for slot in slots:
        status = display_status(slot, now)
        rows.append(
            {
                "id": slot.id,
                "start": slot.start_time.strftime("%H:%M"),
                "end": slot.end_time.strftime("%H:%M"),
                "label": format_time(slot.start_time),
                "end_label": format_time(slot.end_time),
                "status": status,
                "available": status == SlotStatus.AVAILABLE,
            }
        )
    available = sum(1 for row in rows if row["available"])
    return {
        "doctor_id": doctor_id,
        "date": day.isoformat(),
        "slots": rows,
        "summary": {
            "total": len(rows),
            "available": available,
            "booked": sum(1 for row in rows if row["status"] == SlotStatus.BOOKED),
            "blocked": sum(1 for row in rows if row["status"] == SlotStatus.BLOCKED),
        },
        "server_time": now.isoformat(timespec="seconds"),
    }


def claim_slot(slot_id):
    """Atomically move AVAILABLE -> BOOKED. Returns True only for the winner.

    This single conditional UPDATE is the race-condition guard. SQLite serialises
    writers; InnoDB locks the matched row. The loser waits, re-evaluates the
    WHERE clause and gets rowcount 0.
    """
    result = db.session.execute(
        update(Slot)
        .where(Slot.id == slot_id, Slot.status == SlotStatus.AVAILABLE)
        .values(status=SlotStatus.BOOKED)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def release_slot(slot_id):
    """Reopen a future booked slot. Past slots are never reopened."""
    slot = db.session.get(Slot, slot_id)
    if slot is None:
        return False
    if slot.starts_at <= datetime.now():
        return False
    result = db.session.execute(
        update(Slot)
        .where(Slot.id == slot_id, Slot.status == SlotStatus.BOOKED)
        .values(status=SlotStatus.AVAILABLE)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


def block_slot(slot_id):
    result = db.session.execute(
        update(Slot)
        .where(Slot.id == slot_id, Slot.status == SlotStatus.AVAILABLE)
        .values(status=SlotStatus.BLOCKED)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1
