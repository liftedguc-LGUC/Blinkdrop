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


def _resolve_admin_auth(backend: str) -> str:
    explicit = os.environ.get("ADMIN_AUTH", "").strip().lower()
    if explicit in {"iap", "basic", "off"}:
        return explicit
    if os.environ.get("IAP_AUDIENCE"):
        return "iap"
    if os.environ.get("ADMIN_PASSWORD"):
        return "basic"
    # No auth configured: only acceptable on a developer machine. Against a real
    # database the admin routes refuse to serve rather than defaulting open.
    return "off" if backend == "memory" else "unconfigured"


class Settings:
    def __init__(self) -> None:
        self.backend = _resolve_backend()
        self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.firestore_database = os.environ.get("FIRESTORE_DATABASE", "(default)")
        self.web_dir = Path(os.environ.get("WEB_DIR", Path(__file__).resolve().parent.parent))
        self.seed_on_startup = _bool("SEED_ON_STARTUP", self.backend == "memory")
        self.allow_dev_endpoints = _bool("ALLOW_DEV_ENDPOINTS", self.backend == "memory")
        self.timezone_offset_hours = float(os.environ.get("APP_TIMEZONE_OFFSET_HOURS", "0"))

        self.admin_auth = _resolve_admin_auth(self.backend)
        self.admin_user = os.environ.get("ADMIN_USER", "admin")
        self.admin_password = os.environ.get("ADMIN_PASSWORD", "")
        self.iap_audience = os.environ.get("IAP_AUDIENCE", "")
        self.iap_allowed_emails = {
            email.strip().lower()
            for email in os.environ.get("IAP_ALLOWED_EMAILS", "").split(",")
            if email.strip()
        }
        self.require_known_job = _bool("REQUIRE_KNOWN_JOB", True)
        self.expose_docs = _bool("EXPOSE_DOCS", self.backend == "memory")
        self.max_body_bytes = int(os.environ.get("MAX_BODY_BYTES", 64 * 1024))
        self.feedback_rate_limit = int(os.environ.get("FEEDBACK_RATE_LIMIT_PER_MINUTE", "20"))

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

# Caps that keep one request from reading or returning an unbounded result set.
MAX_QUERY_RESULTS = 2000
MAX_DRIVERS_REPORTED = 25
