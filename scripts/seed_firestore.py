"""Seed a real Firestore database, run locally with your own credentials.

This replaces the seeding endpoint's destructive force=true path. It is additive
and refuses to run against a non-empty database unless you pass --allow-existing.
It never deletes anything.

    gcloud auth application-default login
    GOOGLE_CLOUD_PROJECT=<project> python scripts/seed_firestore.py
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.firestore_repo import JOBS as JOBS_COLLECTION  # noqa: E402
from app.firestore_repo import FirestoreRepository  # noqa: E402
from app.seed import JOBS, seed_records  # noqa: E402


async def main(allow_existing: bool) -> int:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("GOOGLE_CLOUD_PROJECT is not set", file=sys.stderr)
        return 2

    repo = FirestoreRepository(project, os.environ.get("FIRESTORE_DATABASE", "(default)"))

    if await repo.count_exceptions() > 0 and not allow_existing:
        print("database already holds exceptions; pass --allow-existing to add anyway")
        return 1

    for job in JOBS:
        await repo._db.collection(JOBS_COLLECTION).document(job.job_ref).set(
            {"driver": job.driver, "customer": job.customer}
        )
    created = await seed_records(repo)
    print(f"seeded {len(JOBS)} jobs and {created} exceptions into {project}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-existing", action="store_true")
    raise SystemExit(asyncio.run(main(parser.parse_args().allow_existing)))
