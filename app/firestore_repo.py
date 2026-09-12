"""Firestore-backed repository.

Not exercised in this repo's test suite: the sandbox it was written in has no
gcloud and therefore no Firestore emulator. The SDK import is deliberately kept
inside the constructor so nothing else in the app depends on it being installed.
"""

from datetime import datetime, timezone

from .config import MAX_QUERY_RESULTS
from .models import (
    ExceptionEvent,
    ExceptionRecord,
    ExceptionStatus,
    FeedbackRecord,
    Job,
    StatsOut,
)
from .repository import CHARGED_STATUSES, build_stats

FEEDBACK = "feedback"
EXCEPTIONS = "exceptions"
EVENTS = "exception_events"
JOBS = "jobs"


class FirestoreRepository:
    def __init__(self, project_id: str | None = None, database: str = "(default)") -> None:
        from google.cloud import firestore  # noqa: PLC0415 — optional dependency

        self._db = firestore.AsyncClient(project=project_id, database=database)

    async def add_feedback(self, fb: FeedbackRecord) -> str:
        payload = fb.model_dump(exclude={"id"})
        _, ref = await self._db.collection(FEEDBACK).add(payload)
        fb.id = ref.id
        return ref.id

    async def add_exception(self, exc: ExceptionRecord) -> str:
        payload = exc.model_dump(exclude={"id"})
        _, ref = await self._db.collection(EXCEPTIONS).add(payload)
        exc.id = ref.id
        if exc.feedback_id:
            await self._db.collection(FEEDBACK).document(exc.feedback_id).update({"exception_id": ref.id})
        return ref.id

    async def get_exception(self, exc_id: str) -> ExceptionRecord | None:
        snapshot = await self._db.collection(EXCEPTIONS).document(exc_id).get()
        return self._to_record(snapshot) if snapshot.exists else None

    async def list_exceptions(self, status: str | None, limit: int) -> list[ExceptionRecord]:
        query = self._db.collection(EXCEPTIONS)
        if status:
            query = query.where("status", "==", status)
        query = query.order_by("created_at", direction="DESCENDING").limit(limit)
        return [self._to_record(doc) async for doc in query.stream()]

    async def update_exception_status(
        self, exc_id: str, status: ExceptionStatus, actor: str
    ) -> ExceptionRecord | None:
        ref = self._db.collection(EXCEPTIONS).document(exc_id)
        snapshot = await ref.get()
        if not snapshot.exists:
            return None
        previous = snapshot.get("status")
        now = datetime.now(timezone.utc)
        patch: dict[str, object] = {"status": str(status), "updated_at": now, "updated_by": actor}
        if status in CHARGED_STATUSES and not snapshot.get("approved_at"):
            patch["approved_at"] = now
        await ref.update(patch)
        await self._db.collection(EVENTS).add(
            {
                "exception_id": exc_id,
                "from_status": str(previous),
                "to_status": str(status),
                "actor": actor,
                "at": now,
            }
        )
        return self._to_record(await ref.get())

    async def list_events(self, exc_id: str, limit: int) -> list[ExceptionEvent]:
        query = (
            self._db.collection(EVENTS)
            .where("exception_id", "==", exc_id)
            .order_by("at")
            .limit(limit)
        )
        return [ExceptionEvent(id=doc.id, **doc.to_dict()) async for doc in query.stream()]

    async def stats(self, day_start: datetime, day_end: datetime) -> StatsOut:
        # Two single-field queries, aggregated in Python. A combined range +
        # equality filter would require a composite index for no real benefit
        # at this volume.
        # Every query is capped. The open-status one in particular used to be
        # unbounded and all-time: since every exception is born pending, a flood
        # of submissions made each dashboard load read the entire collection.
        today_query = (
            self._db.collection(EXCEPTIONS)
            .where("created_at", ">=", day_start)
            .where("created_at", "<", day_end)
            .limit(MAX_QUERY_RESULTS)
        )
        records = [self._to_record(doc) async for doc in today_query.stream()]
        seen = {r.id for r in records}
        open_query = (
            self._db.collection(EXCEPTIONS)
            .where("status", "in", [str(ExceptionStatus.PENDING), str(ExceptionStatus.NEEDS_REVIEW)])
            .limit(MAX_QUERY_RESULTS)
        )
        approved_query = (
            self._db.collection(EXCEPTIONS)
            .where("approved_at", ">=", day_start)
            .where("approved_at", "<", day_end)
            .limit(MAX_QUERY_RESULTS)
        )
        for query in (open_query, approved_query):
            async for doc in query.stream():
                record = self._to_record(doc)
                if record.id not in seen:
                    seen.add(record.id)
                    records.append(record)
        return build_stats(records, day_start, day_end)

    async def get_job(self, job_ref: str) -> Job | None:
        snapshot = await self._db.collection(JOBS).document(job_ref).get()
        if not snapshot.exists:
            return None
        return Job(job_ref=job_ref, **snapshot.to_dict())

    async def count_exceptions(self) -> int:
        # Only needs to answer "is this empty", so it stops at one document
        # rather than scanning the whole collection.
        async for _ in self._db.collection(EXCEPTIONS).select([]).limit(1).stream():
            return 1
        return 0

    async def clear(self) -> None:
        raise NotImplementedError(
            "refusing to delete a Firestore collection from the application; "
            "the runtime service account is not granted datastore.entities.delete"
        )

    @staticmethod
    def _to_record(doc) -> ExceptionRecord:
        return ExceptionRecord(id=doc.id, **doc.to_dict())
