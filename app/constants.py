"""Domain constants shared by models, services and templates."""


class Roles:
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"
    ALL = (PATIENT, DOCTOR, ADMIN)


class SlotStatus:
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"
    ALL = (AVAILABLE, BOOKED, BLOCKED, CLOSED)


class AppointmentStatus:
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    IN_CONSULTATION = "IN_CONSULTATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
    ALL = (CONFIRMED, CHECKED_IN, IN_CONSULTATION, COMPLETED, CANCELLED, NO_SHOW)


ACTIVE_APPOINTMENT_STATUSES = (
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_CONSULTATION,
)
QUEUE_STATUSES = (
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_CONSULTATION,
)
FINISHED_APPOINTMENT_STATUSES = (
    AppointmentStatus.COMPLETED,
    AppointmentStatus.CANCELLED,
    AppointmentStatus.NO_SHOW,
)

BOOKING_ID_PREFIX = "MQ"
DEFAULT_SETTINGS = {
    "hospital_name": "MediQueue General Hospital",
    "cancellation_cutoff_hours": "2",
    "max_cancellations_per_30_days": "3",
    "booking_open_days": "30",
    "reminder_hours_before": "24",
    "support_email": "support@mediqueue.local",
}
