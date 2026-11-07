"""Registration, login and logout."""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..constants import Roles
from ..extensions import db, limiter
from ..forms import LoginForm, RegisterForm
from ..models.user import PatientProfile, User
from ..services import audit_service
from ..utils.security import is_safe_redirect
from ..utils.time_utils import dashboard_for

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_for(current_user)))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            role=Roles.PATIENT,
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=(form.phone.data or "").strip() or None,
        )
        user.set_password(form.password.data)
        user.patient_profile = PatientProfile()
        db.session.add(user)
        db.session.commit()
        audit_service.log("patient_registered", "user", user.id, actor=user)
        flash("Your account is ready. Please sign in to book an appointment.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_for(current_user)))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(form.password.data):
            audit_service.log("login_failed", "user", details={"email": email}, commit=True)
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form), 200
        if not user.is_active:
            flash("This account is disabled. Please contact the hospital.", "danger")
            return render_template("auth/login.html", form=form), 200
        login_user(user, remember=form.remember.data)
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        session.permanent = True
        audit_service.log("login", "user", user.id)
        flash(f"Welcome back, {user.first_name}!", "success")
        target = request.args.get("next")
        if target and is_safe_redirect(target):
            return redirect(target)
        return redirect(url_for(dashboard_for(user)))
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    audit_service.log("logout", "user", current_user.id)
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))
