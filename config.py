"""Compatibility shim.

Canonical configuration lives in :mod:`app.config` so the application package
is importable from any working directory. Keep this module for tooling and
documentation that expects ``config.py`` at the project root.
"""
from app.config import (  # noqa: F401
    BASE_DIR,
    INSTANCE_DIR,
    BaseConfig,
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    config_by_name,
)

__all__ = [
    "BASE_DIR",
    "INSTANCE_DIR",
    "BaseConfig",
    "DevelopmentConfig",
    "TestingConfig",
    "ProductionConfig",
    "config_by_name",
]
