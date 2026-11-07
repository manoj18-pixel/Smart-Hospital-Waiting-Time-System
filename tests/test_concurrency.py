"""T09 — Simultaneous booking: exactly one winner, one 409."""
from concurrent.futures import ThreadPoolExecutor
from datetime import time
from threading import Barrier

from app.constants import SlotStatus
from app.extensions import db
from app.models.appointment import Appointment
from app.models.slot import Slot

from .factories import TEST_PASSWORD, future_day, make_slot


def test_two_patients_race_for_one_slot(app, base):
    slot = make_slot(base.doctor, day=future_day(), start=time(9, 0))
    db.session.commit()
    slot_id = slot.id
    doctor_id = base.doctor.id
    emails = [base.patient.email, base.other_patient.email]
    barrier = Barrier(len(emails))

    def book(email):
        client = app.test_client()
        login = client.post(
            "/login", data={"email": email, "password": TEST_PASSWORD}
        )
        assert login.status_code == 302, login.data[:300]
        barrier.wait(timeout=10)
        return client.post(
            f"/patient/book/{doctor_id}",
            data={"slot_id": slot_id, "reason": "Concurrent race"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result() for future in [pool.submit(book, e) for e in emails]]

    codes = sorted(response.status_code for response in responses)
    assert codes == [302, 409], [r.status_code for r in responses]

    db.session.expire_all()
    assert Appointment.query.count() == 1
    assert db.session.get(Slot, slot_id).status == SlotStatus.BOOKED

    winner = Appointment.query.one()
    assert winner.status == "CONFIRMED"
