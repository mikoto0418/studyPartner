"""
Backfill legacy StudentMemory rows into Memory Wiki.

Run from project root:
    python scripts/backfill_memory_wiki.py [--user USERNAME]
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.user import User
from app.services.memory_wiki_service import MemoryWikiService


async def main(username: str | None = None) -> None:
    async with SessionLocal() as db:
        user_id = None
        if username:
            res = await db.execute(select(User).where(User.username == username))
            user = res.scalars().first()
            if not user:
                print(f"[ERROR] User '{username}' not found")
                sys.exit(1)
            user_id = user.id
            print(f"[INFO] Backfilling memory wiki for user: {username} ({user.id})")
        else:
            print("[INFO] Backfilling memory wiki for all users")

        created, skipped = await MemoryWikiService.backfill_from_legacy_memories(db, user_id=user_id)
        print(f"[OK] Created {created} memory pages, skipped {skipped} already-migrated rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill legacy student memories into Memory Wiki")
    parser.add_argument("--user", type=str, default=None, help="Only backfill this username")
    args = parser.parse_args()
    asyncio.run(main(args.user))