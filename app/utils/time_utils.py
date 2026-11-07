"""Date and time helpers. The whole app uses naive hospital-local datetimes."""
from datetime import date, datetime, time, timedelta

from ..constants import Roles


def now():
    return datetime.now()


def today():
    return date.today()


def combine(day, clock):
    return datetime.combine(day, clock)


def to_minutes(clock):
    return clock.hour * 60 + clock.minute


def humanize_minutes(minutes):
    minutes = max(0, int(minutes or 0))
    if minutes == 0:
        return "No wait"
    if minutes < 60:
        return f"~{minutes} min"
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"~{hours} hr"
    return f"~{hours} hr {rest} min"


def format_time(clock):
    if clock is None:
        return ""
    return clock.strftime("%I:%M %p").lstrip("0")


def format_date(day):
    if day is None:
        return ""
    return day.strftime("%a, %d %b %Y")


def dashboard_for(user):
    if user.role == Roles.ADMIN:
        return "admin.dashboard"
    if user.role == Roles.DOCTOR:
        return "doctor.dashboard"
    return "patient.dashboard"


def days_until(day):
    return (day - date.today()).days


def upcoming_window(days):
    start = date.today()
    return [start + timedelta(days=i) for i in range(days)]
