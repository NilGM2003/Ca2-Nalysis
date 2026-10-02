"""Registry of analysable imaging sessions.

Each session module exposes a ``CONFIG`` SessionConfig. Add new sessions here.
"""
from .s20260609 import CONFIG as s20260609
from .s20260612 import CONFIG as s20260612
from .s20260623 import CONFIG as s20260623
from .s20261001 import CONFIG as s20261001

SESSIONS = {
    "20260609": s20260609,
    "20260612": s20260612,
    "20260623": s20260623,
    "20261001": s20261001,
}