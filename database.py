"""Async SQLite database for license management."""

import aiosqlite
from datetime import datetime, timezone
from typing import Optional, List
import os


class Database:
    def __init__(self, path: str):
        self.path = path
        db_dir = os.path.dirname(os.path.abspath(path))
        os.makedirs(db_dir, exist_ok=True)

    async def init(self):
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    device_id       TEXT PRIMARY KEY,
                    telegram_id     INTEGER NOT NULL,
                    telegram_username TEXT,
                    license_code    TEXT,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    created_at      TEXT NOT NULL,
                    approved_at     TEXT
                )
            """)
            await db.commit()

    async def upsert_request(
        self,
        device_id: str,
        telegram_id: int,
        telegram_username: Optional[str],
    ) -> bool:
        """Add or update a license request. Returns True if newly created."""
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT status FROM licenses WHERE device_id = ?", (device_id,)
            )
            row = await cur.fetchone()
            if row:
                # Already exists — update telegram info but keep status
                await db.execute(
                    """UPDATE licenses
                       SET telegram_id=?, telegram_username=?
                       WHERE device_id=?""",
                    (telegram_id, telegram_username, device_id),
                )
                await db.commit()
                return False
            else:
                await db.execute(
                    """INSERT INTO licenses
                       (device_id, telegram_id, telegram_username, status, created_at)
                       VALUES (?, ?, ?, 'pending', ?)""",
                    (device_id, telegram_id, telegram_username, now),
                )
                await db.commit()
                return True

    async def approve(self, device_id: str, license_code: str) -> Optional[dict]:
        """Approve a license request. Returns the updated record or None."""
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """UPDATE licenses
                   SET status='approved', license_code=?, approved_at=?
                   WHERE device_id=?""",
                (license_code, now, device_id),
            )
            await db.commit()
            return await self.get(device_id)

    async def revoke(self, device_id: str) -> bool:
        """Revoke a license. Returns True if found."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "UPDATE licenses SET status='revoked' WHERE device_id=?",
                (device_id,),
            )
            await db.commit()
            return cur.rowcount > 0

    async def get(self, device_id: str) -> Optional[dict]:
        """Get a single license record."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM licenses WHERE device_id=?", (device_id,)
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_all(self) -> List[dict]:
        """List all licenses."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM licenses ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Find the most recent request from a Telegram user."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT * FROM licenses
                   WHERE telegram_id=?
                   ORDER BY created_at DESC LIMIT 1""",
                (telegram_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None
