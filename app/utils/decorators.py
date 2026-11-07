"""Role based access-control decorators."""
from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user, login_required

from ..constants import Roles


def role_required(*roles):
    """Require an authenticated, active user with one of the given roles."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.is_active or current_user.role not in roles:
                if "/api/" in request.path:
                    return jsonify(
                        ok=False,
                        error={
                            "code": "FORBIDDEN",
                            "message": "You do not have permission to do that.",
                        },
                    ), 403
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def patient_required(view):
    return role_required(Roles.PATIENT)(view)


def doctor_required(view):
    return role_required(Roles.DOCTOR)(view)


def admin_required(view):
    return role_required(Roles.ADMIN)(view)
