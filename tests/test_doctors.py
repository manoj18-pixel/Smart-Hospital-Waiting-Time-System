"""T04 — Doctor selection and profiles."""
from app.extensions import db

from .factories import TEST_PASSWORD, make_doctor, make_schedule


def _login(client, email):
    client.post("/login", data={"email": email, "password": TEST_PASSWORD})


def test_doctors_are_filtered_by_department(client, app, base):
    hidden = make_doctor(
        base.department, full_name="Hidden Doctor", email="hidden@test.local"
    )
    hidden.is_active = False
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get(f"/patient/departments/{base.department.id}/doctors")
    assert response.status_code == 200
    assert b"Arjun Mehta" in response.data
    assert b"Kavya Rao" not in response.data
    assert b"Hidden Doctor" not in response.data


def test_doctor_profile_shows_specialisation_and_hours(client, app, base):
    make_schedule(base.doctor)
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get(f"/patient/doctors/{base.doctor.id}")
    assert response.status_code == 200
    assert b"Interventional Cardiologist" in response.data
    assert base.doctor.department.name.encode() in response.data


def test_doctor_profile_links_to_booking(client, app, base):
    _login(client, base.patient.email)
    response = client.get(f"/patient/doctors/{base.doctor.id}")
    assert response.status_code == 200
    assert f"/patient/book/{base.doctor.id}".encode() in response.data


def test_inactive_doctor_profile_is_404(client, app, base):
    base.other_doctor.is_active = False
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get(f"/patient/doctors/{base.other_doctor.id}")
    assert response.status_code == 404


def test_doctor_list_requires_patient_login(client, app, base):
    response = client.get(f"/patient/departments/{base.department.id}/doctors")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
