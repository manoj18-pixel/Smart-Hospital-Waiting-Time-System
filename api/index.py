"""Vercel serverless entry point for MediQueue.

Vercel's Python runtime looks for a WSGI callable named ``app`` in files under
``api/``. The whole Flask application lives one directory up, so add the project
root to ``sys.path`` before importing it.

If the application cannot start (for example a missing environment variable or
an unreachable database), the module still exports a small WSGI app that
explains the problem instead of failing with an opaque
``FUNCTION_INVOCATION_FAILED`` page. Append ``?debug=<SECRET_KEY>`` to the URL
to see the exact exception message.
"""
import html
import os
import re
import sys
import traceback
from urllib.parse import parse_qs

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _scrub(message):
    """Hide database passwords before showing an error to a human."""
    message = re.sub(r"(://[^:/@\s]+:)[^@\s]+@", r"\1***@", str(message))
    return html.escape(message[:2000])


def _boot_error_app(exc):
    detail = f"{type(exc).__name__}: {exc}"
    # Also write it to the Vercel runtime logs.
    print("MediQueue failed to start:\n" + traceback.format_exc(), file=sys.stderr)
    secret = os.environ.get("SECRET_KEY", "")

    def app(environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""))
        debug = (query.get("debug") or [""])[0]
        if secret and debug == secret:
            body = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>MediQueue boot error</title>"
                "<h1>MediQueue could not start</h1>"
                f"<pre style='white-space:pre-wrap'>{_scrub(detail)}</pre>"
            )
        else:
            body = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>MediQueue is not configured</title>"
                "<h1>MediQueue is not configured yet</h1>"
                "<p>Set <code>SECRET_KEY</code> and <code>DATABASE_URL</code> in "
                "Vercel &rarr; Project &rarr; Settings &rarr; Environment Variables, "
                "then redeploy.</p>"
            )
        start_response(
            "500 Internal Server Error",
            [("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")],
        )
        return [body.encode("utf-8")]

    return app


try:
    from app import create_app

    app = create_app("production")
except Exception as exc:  # pragma: no cover - only used during deployment
    app = _boot_error_app(exc)
