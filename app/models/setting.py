"""Key/value hospital settings stored in the database."""
from datetime import datetime

from ..constants import DEFAULT_SETTINGS
from ..extensions import db


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(300), nullable=False)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @classmethod
    def get(cls, key, default=None):
        row = db.session.get(cls, key)
        if row is None:
            return DEFAULT_SETTINGS.get(key, default)
        return row.value

    @classmethod
    def get_int(cls, key, default=0):
        try:
            return int(cls.get(key, default))
        except (TypeError, ValueError):
            return default

    @classmethod
    def set(cls, key, value):
        row = db.session.get(cls, key)
        if row is None:
            row = cls(key=key, value=str(value))
            db.session.add(row)
        else:
            row.value = str(value)
        return row
