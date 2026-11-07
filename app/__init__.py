"""MediQueue application factory."""
import mimetypes
import os
import sqlite3
from datetime import date

import click
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import config_by_name
from .constants import AppointmentStatus, SlotStatus
from .extensions import csrf, db, limiter, login_manager, mail, migrate
from .utils.time_utils import format_date, format_time, humanize_minutes

# Some Windows installations map .js to text/plain in the registry. Browsers
# refuse to execute that when X-Content-Type-Options: nosniff is set, so pin
# the frontend asset types explicitly.
for _extension, _mimetype in (
    (".js", "application/javascript"),
    (".mjs", "application/javascript"),
    (".css", "text/css"),
    (".svg", "image/svg+xml"),
    (".json", "application/json"),
    (".webmanifest", "application/manifest+json"),
    (".woff", "font/woff"),
    (".woff2", "font/woff2"),
):
    mimetypes.add_type(_mimetype, _extension)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record):
    """WAL + busy timeout make the SQLite dev database concurrency-safe."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
        cursor.close()


def _env_flag(name, default=False):
    """Read a boolean environment flag (1/true/yes/on)."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap_database(app):
    """Create the schema (and demo data) on a fresh serverless database.

    Vercel starts with an empty managed database; without this the first
    request would fail with ``relation "departments" does not exist``.
    """
    from .constants import DEFAULT_SETTINGS
    from .models.setting import Setting
    from .models.user import User

    with app.app_context():
        db.create_all()
        for key, value in DEFAULT_SETTINGS.items():
            if Setting.get(key) is None:
                Setting.set(key, value)
        db.session.commit()

        # Demo data is only inserted when the admin account is missing, so this
        # is a one-time cost. Set AUTO_SEED_DEMO=false for a clean database.
        if _env_flag("AUTO_SEED_DEMO", default=True):
            if User.query.filter_by(email="admin@mediqueue.local").first() is None:
                from seed import seed_database

                seed_database(app)


def create_app(config_name=None, overrides=None):
    config_name = config_name or os.getenv("FLASK_CONFIG", "development")

    # Serverless platforms (Vercel, Lambda, ...) have a read-only filesystem and
    # no persistent disk, so SQLite cannot be used there. Fail loudly at boot
    # instead of returning confusing 500s on the first request.
    if config_name == "production":
        missing = [
            name
            for name in ("SECRET_KEY", "DATABASE_URL")
            if not (os.getenv(name) or "").strip()
        ]
        if missing:
            raise RuntimeError(
                "Missing required production environment variable(s): "
                + ", ".join(missing)
                + ". Set them in the Vercel dashboard (Project > Settings > "
                "Environment Variables)."
            )

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))
    if overrides:
        app.config.update(overrides)

    # Vercel (and every other reverse proxy) terminates TLS before the request
    # reaches Flask, so trust exactly one hop of X-Forwarded-* headers. Without
    # this, secure cookies and generated URLs would look like plain HTTP.
    if config_name == "production":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        # Read-only filesystem on serverless hosts. Only the default SQLite
        # database needs this directory, and production requires DATABASE_URL.
        pass
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
        engine_options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
        connect_args = dict(engine_options.get("connect_args") or {})
        connect_args.setdefault("timeout", 15)
        engine_options["connect_args"] = connect_args
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options
    else:
        # Managed databases (Neon, Aiven, ...) close idle serverless
        # connections. Check before use and keep a tiny per-instance pool.
        engine_options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {})
        engine_options.setdefault("pool_pre_ping", True)
        engine_options.setdefault("pool_recycle", 280)
        if os.getenv("VERCEL"):
            engine_options.setdefault("pool_size", 1)
            engine_options.setdefault("max_overflow", 0)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401  (register models with SQLAlchemy)
    from .blueprints import admin, api, auth, doctor, errors, main, patient

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(patient.bp)
    app.register_blueprint(doctor.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(errors.bp)

    @login_manager.unauthorized_handler
    def unauthorized():
        if "/api/" in request.path:
            return (
                jsonify(
                    ok=False,
                    error={"code": "AUTH_REQUIRED", "message": "Please sign in to continue."},
                ),
                401,
            )
        flash("Please sign in to continue.", "warning")
        target = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=target))

    @app.context_processor
    def inject_globals():
        return {
            "app_name": "MediQueue",
            "hospital_name": app.config.get("HOSPITAL_NAME", "MediQueue General Hospital"),
            "current_year": date.today().year,
            "today_date": date.today(),
            "SlotStatus": SlotStatus,
            "AppointmentStatus": AppointmentStatus,
            "format_time": format_time,
            "format_date": format_date,
            "humanize_minutes": humanize_minutes,
        }

    app.jinja_env.filters["time12"] = format_time
    app.jinja_env.filters["date_label"] = format_date
    app.jinja_env.filters["wait_label"] = humanize_minutes

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
        return response

    @app.cli.command("init-db")
    def init_db_command():
        """Create all tables and default settings."""
        from .models.setting import Setting
        from .constants import DEFAULT_SETTINGS

        db.create_all()
        for key, value in DEFAULT_SETTINGS.items():
            if Setting.get(key) is None:
                Setting.set(key, value)
        db.session.commit()
        click.echo("Database created.")

    @app.cli.command("generate-slots")
    @click.option("--days", default=30, show_default=True)
    def generate_slots_command(days):
        """Generate future slots for every active doctor."""
        from .services import schedule_service

        total = schedule_service.generate_all_slots(days=days)
        click.echo(f"{total} slot(s) generated.")

    @app.cli.command("seed")
    def seed_command():
        """Load demo departments, doctors, schedules and patients."""
        from seed import seed_database

        seed_database(app)
        click.echo("Demo data loaded.")

    @app.shell_context_processor
    def shell_context():
        return {"db": db}

    if config_name == "production" and _env_flag(
        "AUTO_INIT_DB", default=bool(os.getenv("VERCEL"))
    ):
        _bootstrap_database(app)

    return app
