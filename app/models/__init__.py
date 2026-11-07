"""Import all models so Flask-Migrate and db.create_all() see them."""
from .appointment import Appointment
from .audit_log import AuditLog
from .department import Department
from .doctor import Doctor, DoctorSchedule, ScheduleException
from .notification import Notification
from .setting import Setting
from .slot import Slot
from .user import PatientProfile, User

__all__ = [
    "User",
    "PatientProfile",
    "Department",
    "Doctor",
    "DoctorSchedule",
    "ScheduleException",
    "Slot",
    "Appointment",
    "Notification",
    "AuditLog",
    "Setting",
]
