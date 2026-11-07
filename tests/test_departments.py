"""T03 — Department selection and visibility."""
from app.extensions import db

from .factories import TEST_PASSWORD, make_department


def _login(client, email):
    client.post("/login", data={"email": email, "password": TEST_PASSWORD})


def test_public_landing_lists_active_departments(client, app, base):
    make_department("Dermatology")
    make_department("Archived Unit", is_active=False)
    db.session.commit()

    response = client.get("/")
    assert response.status_code == 200
    assert b"Cardiology" in response.data
    assert b"Dermatology" in response.data
    assert b"Archived Unit" not in response.data


def test_patient_department_page_hides_inactive(client, app, base):
    make_department("Dermatology")
    make_department("Archived Unit", is_active=False)
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get("/patient/departments")
    assert response.status_code == 200
    assert b"Cardiology" in response.data
    assert b"Dermatology" in response.data
    assert b"Archived Unit" not in response.data


def test_inactive_department_doctor_list_is_404(client, app, base):
    inactive = make_department("Archived Unit", is_active=False)
    db.session.commit()

    _login(client, base.patient.email)
    response = client.get(f"/patient/departments/{inactive.id}/doctors")
    assert response.status_code == 404


def test_department_card_links_to_doctor_list(client, app, base):
    _login(client, base.patient.email)
    response = client.get("/patient/departments")
    assert response.status_code == 200
    expected = f"/patient/departments/{base.department.id}/doctors".encode()
    assert expected in response.data
