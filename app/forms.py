"""WTForms used across the application."""
from email_validator import EmailNotValidError, validate_email
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from .constants import Roles
from .extensions import db
from .models.user import User
from .utils.security import password_problem


class HospitalEmail(Email):
    """Email validator that also accepts internal and test domains.

    ``email_validator`` rejects the reserved ``.local`` and ``.test`` domains.
    MediQueue uses ``.local`` for its intranet/demo accounts and ``.test`` in
    automated tests, so those are checked against the syntax rules of a normal
    public domain before being accepted.
    """

    def __init__(self, message=None, **kwargs):
        kwargs.setdefault("test_environment", True)
        super().__init__(message=message, **kwargs)

    def __call__(self, form, field):
        value = (field.data or "").strip()
        local_part, _, domain = value.rpartition("@")
        if local_part and domain and domain.lower().endswith(".local"):
            try:
                validate_email(f"{local_part}@example.com", check_deliverability=False)
            except EmailNotValidError as exc:
                raise ValidationError("Invalid email address.") from exc
            return
        super().__call__(form, field)


class RegisterForm(FlaskForm):
    full_name = StringField(
        "Full name", validators=[DataRequired(), Length(min=3, max=120)]
    )
    email = StringField("Email address", validators=[DataRequired(), HospitalEmail(), Length(max=255)])
    phone = StringField("Phone number", validators=[Optional(), Length(max=20)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    accept_terms = BooleanField("I agree to the hospital privacy policy", validators=[DataRequired()])

    def validate_email(self, field):
        email = (field.data or "").strip().lower()
        if User.query.filter_by(email=email).first():
            raise ValidationError("An account with this email already exists.")

    def validate_password(self, field):
        problem = password_problem(field.data)
        if problem:
            raise ValidationError(problem)


class LoginForm(FlaskForm):
    email = StringField("Email address", validators=[DataRequired(), HospitalEmail()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")


class BookingForm(FlaskForm):
    slot_id = IntegerField("Slot", validators=[DataRequired()])
    reason = TextAreaField("Reason for visit", validators=[Optional(), Length(max=300)])


class CancelForm(FlaskForm):
    reason = StringField(
        "Cancellation reason", validators=[DataRequired(), Length(min=3, max=300)]
    )


class DepartmentForm(FlaskForm):
    name = StringField("Department name", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    icon = StringField("Font Awesome icon", validators=[Optional(), Length(max=60)], default="fa-hospital")
    image_url = StringField("Image URL", validators=[Optional(), Length(max=400)])
    floor = StringField("Floor", validators=[Optional(), Length(max=30)])
    phone_ext = StringField("Phone extension", validators=[Optional(), Length(max=10)])
    is_active = BooleanField("Active", default=True)


class DoctorForm(FlaskForm):
    full_name = StringField("Doctor name", validators=[DataRequired(), Length(min=3, max=120)])
    email = StringField("Login email", validators=[DataRequired(), HospitalEmail(), Length(max=255)])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    password = PasswordField("Password (leave blank to keep current)", validators=[Optional(), Length(max=128)])
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    specialization = StringField("Specialization", validators=[DataRequired(), Length(max=120)])
    qualification = StringField("Qualification", validators=[Optional(), Length(max=150)])
    experience_years = IntegerField("Experience (years)", validators=[DataRequired(), NumberRange(min=0, max=60)])
    consultation_fee = DecimalField("Consultation fee", validators=[DataRequired(), NumberRange(min=0)], places=2)
    room_no = StringField("Room number", validators=[Optional(), Length(max=20)])
    bio = TextAreaField("Profile bio", validators=[Optional(), Length(max=2000)])
    photo_url = StringField("Photo URL", validators=[Optional(), Length(max=400)])
    avg_consult_minutes = IntegerField(
        "Average consultation (minutes)", validators=[DataRequired(), NumberRange(min=5, max=120)], default=15
    )
    is_active = BooleanField("Active", default=True)

    def __init__(self, *args, editing_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing_user = editing_user

    def validate_email(self, field):
        email = (field.data or "").strip().lower()
        existing = User.query.filter_by(email=email).first()
        if existing and (self.editing_user is None or existing.id != self.editing_user.id):
            raise ValidationError("Another account already uses this email.")

    def validate_password(self, field):
        if field.data:
            problem = password_problem(field.data)
            if problem:
                raise ValidationError(problem)
        elif self.editing_user is None:
            raise ValidationError("A password is required for a new doctor account.")


class ScheduleForm(FlaskForm):
    weekday = SelectField(
        "Weekday",
        coerce=int,
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ],
        validators=[DataRequired()],
    )
    start_time = TimeField("Start time", validators=[DataRequired()])
    end_time = TimeField("End time", validators=[DataRequired()])
    slot_duration_minutes = IntegerField(
        "Slot duration (minutes)", validators=[DataRequired(), NumberRange(min=5, max=120)], default=20
    )
    max_patients = IntegerField("Max patients (optional)", validators=[Optional(), NumberRange(min=1, max=200)])
    is_active = BooleanField("Active", default=True)

    def validate_end_time(self, field):
        if self.start_time.data and field.data and field.data <= self.start_time.data:
            raise ValidationError("End time must be after the start time.")


class LeaveForm(FlaskForm):
    exception_date = DateField("Date", validators=[DataRequired()])
    is_closed = BooleanField("Full day leave", default=True)
    start_time = TimeField("From (optional)", validators=[Optional()])
    end_time = TimeField("To (optional)", validators=[Optional()])
    reason = StringField("Reason", validators=[Optional(), Length(max=200)])


class DoctorProfileForm(FlaskForm):
    bio = TextAreaField("Profile bio", validators=[Optional(), Length(max=2000)])
    consultation_fee = DecimalField("Consultation fee", validators=[DataRequired(), NumberRange(min=0)], places=2)
    avg_consult_minutes = IntegerField(
        "Average consultation (minutes)", validators=[DataRequired(), NumberRange(min=5, max=120)]
    )
    room_no = StringField("Room number", validators=[Optional(), Length(max=20)])


class DelayForm(FlaskForm):
    delay_minutes = IntegerField("Running late by (minutes)", validators=[DataRequired(), NumberRange(min=0, max=180)])
