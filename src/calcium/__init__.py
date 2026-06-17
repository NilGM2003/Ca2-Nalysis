"""Calcium-imaging LIFUS dose-response analysis toolkit.

Generic, session-agnostic pipeline. Dataset-specific details (acquisition
protocol, per-file truncation, dose-response exclusions) live in session
config objects under ``sessions/`` and are passed to :func:`run_session`.
"""
from .config import SessionConfig
from .pipeline import run_session

__all__ = ["SessionConfig", "run_session"]
