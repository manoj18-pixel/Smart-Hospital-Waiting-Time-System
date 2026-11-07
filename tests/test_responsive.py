"""T21 — Responsive layout, mobile navigation and print styles."""
from pathlib import Path

from .factories import TEST_PASSWORD

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def _login(client, email):
    client.post("/login", data={"email": email, "password": TEST_PASSWORD})


def test_public_pages_declare_viewport_and_frontend_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.data
    assert b'name="viewport"' in body
    assert b"width=device-width" in body
    assert b"vendor/bootstrap/css/bootstrap.min.css" in body
    assert b"vendor/fontawesome/css/all.min.css" in body
    assert b"vendor/fonts/fonts.css" in body
    assert b"theme.css" in body
    assert b"responsive.css" in body
    # Assets must be self-hosted so the UI also works on restricted networks.
    assert b"https://cdn." not in body
    assert b"fonts.googleapis.com" not in body
    assert b"fonts.gstatic.com" not in body


def test_responsive_stylesheet_defines_all_breakpoints():
    css = (STATIC / "css" / "responsive.css").read_text(encoding="utf-8")
    for width in ("1199.98px", "991.98px", "767.98px", "575.98px"):
        assert f"max-width: {width}" in css
    assert "transform: translateX(-104%)" in css
    assert ".sidebar.open" in css


def test_theme_uses_blue_white_and_light_green_palette():
    css = (STATIC / "css" / "theme.css").read_text(encoding="utf-8")
    assert "--blue-600: #0d6efd" in css
    assert "--blue-50: #f3f8ff" in css
    assert "--surface: #ffffff" in css
    assert "--green-500: #22c55e" in css
    assert "--green-100: #e6f9ee" in css
    assert "--bg: #f5f9ff" in css


def test_dashboard_has_offcanvas_sidebar_controls(client, app, base):
    _login(client, base.patient.email)
    response = client.get("/patient/dashboard")
    assert response.status_code == 200
    body = response.data
    assert b'id="sidebar"' in body
    assert b'id="menuToggle"' in body
    assert b'id="sidebarBackdrop"' in body
    assert b'aria-controls="sidebar"' in body
    assert b'aria-expanded="false"' in body


def test_mobile_sidebar_script_is_wired_up():
    script = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    assert 'getElementById("sidebar")' in script
    assert 'getElementById("menuToggle")' in script
    assert 'classList.toggle("open"' in script
    assert "sidebarBackdrop" in script


def test_admin_tables_use_scroll_containers(client, app, base):
    _login(client, base.admin.email)
    response = client.get("/admin/patients")
    assert response.status_code == 200
    assert b"table-responsive" in response.data
    assert b"table-modern" in response.data


def test_booking_page_uses_responsive_booking_grid(client, app, base):
    _login(client, base.patient.email)
    response = client.get(f"/patient/book/{base.doctor.id}")
    assert response.status_code == 200
    assert b"booking-grid" in response.data
    assert b"slot-grid" in response.data
    assert b"booking-summary" in response.data


def test_print_styles_hide_navigation_and_actions():
    css = (STATIC / "css" / "responsive.css").read_text(encoding="utf-8")
    print_block = css.split("@media print", 1)[1]
    assert ".site-nav" in print_block
    assert ".sidebar" in print_block
    assert ".no-print" in print_block
    assert "display: none !important" in print_block


def test_static_assets_are_served(client):
    for path in (
        "/static/css/theme.css",
        "/static/css/responsive.css",
        "/static/js/app.js",
        "/static/img/logo.svg",
        "/static/vendor/bootstrap/css/bootstrap.min.css",
        "/static/vendor/bootstrap/js/bootstrap.bundle.min.js",
        "/static/vendor/fontawesome/css/all.min.css",
        "/static/vendor/fontawesome/webfonts/fa-solid-900.woff2",
        "/static/vendor/fonts/fonts.css",
        "/static/vendor/fonts/inter-400.woff2",
        "/static/vendor/chartjs/chart.umd.min.js",
        "/static/img/photos/hero-corridor.jpg",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
