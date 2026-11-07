"""HTTP error handlers and JSON-aware responses."""
from flask import Blueprint, jsonify, render_template, request
from flask_wtf.csrf import CSRFError

bp = Blueprint("errors", __name__)


def wants_json():
    """True when the caller expects a JSON error envelope.

    Checks for an ``/api/`` segment anywhere in the path so nested endpoints
    such as ``/admin/api/stats`` are treated as API calls too.
    """
    return "/api/" in request.path or request.accept_mimetypes.best == "application/json"


def json_error(status, code, message):
    return jsonify(ok=False, error={"code": code, "message": message}), status


@bp.app_errorhandler(400)
def bad_request(error):
    if wants_json():
        return json_error(400, "BAD_REQUEST", "The request could not be understood.")
    return render_template("errors/400.html"), 400


@bp.app_errorhandler(CSRFError)
def csrf_error(error):
    if wants_json():
        return json_error(400, "CSRF_ERROR", "Your session expired. Please refresh and try again.")
    return render_template("errors/400.html", message="Your session expired. Please refresh and try again."), 400


@bp.app_errorhandler(403)
def forbidden(error):
    if wants_json():
        return json_error(403, "FORBIDDEN", "You do not have permission to do that.")
    return render_template("errors/403.html"), 403


@bp.app_errorhandler(404)
def not_found(error):
    if wants_json():
        return json_error(404, "NOT_FOUND", "The requested resource was not found.")
    return render_template("errors/404.html"), 404


@bp.app_errorhandler(409)
def conflict(error):
    if wants_json():
        return json_error(409, "CONFLICT", getattr(error, "description", "Request conflict."))
    return render_template("errors/409.html"), 409


@bp.app_errorhandler(429)
def rate_limited(error):
    if wants_json():
        return json_error(429, "RATE_LIMITED", "Too many requests. Please slow down.")
    return render_template("errors/429.html"), 429


@bp.app_errorhandler(500)
def server_error(error):
    if wants_json():
        return json_error(500, "SERVER_ERROR", "Something went wrong on our side.")
    return render_template("errors/500.html"), 500
