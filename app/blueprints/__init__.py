"""Blueprint package."""
from . import admin, api, auth, doctor, errors, main, patient

__all__ = ["auth", "main", "patient", "doctor", "admin", "api", "errors"]
