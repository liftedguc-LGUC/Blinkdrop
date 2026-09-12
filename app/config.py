import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_backend() -> str:
    explicit = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    if explicit in {"memory", "firestore"}:
        return explicit
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        return "firestore"
    if os.environ.get("K_SERVICE") or os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return "firestore"
    return "memory"


class Settings:
    def __init__(self) -> None:
        self.backend = _resolve_backend()
        self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.firestore_database = os.environ.get("FIRESTORE_DATABASE", "(default)")
        self.web_dir = Path(os.environ.get("WEB_DIR", Path(__file__).resolve().parent.parent))
        self.seed_on_startup = _bool("SEED_ON_STARTUP", self.backend == "memory")
        self.allow_dev_endpoints = _bool("ALLOW_DEV_ENDPOINTS", self.backend == "memory")
        self.timezone_offset_hours = float(os.environ.get("APP_TIMEZONE_OFFSET_HOURS", "0"))

    @property
    def tz(self) -> timezone:
        return timezone(timedelta(hours=self.timezone_offset_hours))

    def day_bounds(self, now: datetime | None = None) -> tuple[datetime, datetime]:
        now = (now or datetime.now(timezone.utc)).astimezone(self.tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Business rules the wireframe never specified. Everything invented lives here
# and in mapping.py so it is cheap to change.
LATE_CHARGE_CENTS = 500
DAMAGED_CHARGE_CENTS = 1200
POOR_RATING_MAX = 2
