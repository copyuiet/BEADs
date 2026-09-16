"""SQLite 结构升级测试。"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.core.database import Database


class DatabaseMigrationTests(unittest.TestCase):
    def test_existing_artworks_are_marked_saved_during_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "legacy.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE users (
                        id TEXT PRIMARY KEY, username TEXT NOT NULL,
                        username_normalized TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL, created_at TEXT NOT NULL
                    );
                    CREATE TABLE uploads (
                        image_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE artworks (
                        job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                        image_id TEXT NOT NULL, title TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '', size TEXT NOT NULL,
                        palette TEXT NOT NULL, color_mode TEXT NOT NULL,
                        dithering INTEGER NOT NULL, pattern_type TEXT NOT NULL,
                        active_bead_count INTEGER NOT NULL,
                        is_public INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL, published_at TEXT,
                        download_count INTEGER NOT NULL DEFAULT 0
                    );
                    INSERT INTO users VALUES ('u1', 'legacy', 'legacy', 'hash', '2026-01-01T00:00:00Z');
                    INSERT INTO uploads VALUES ('i1', 'u1', '2026-01-01T00:00:00Z');
                    INSERT INTO artworks VALUES (
                        'j1', 'u1', 'i1', '旧作品', '', '52x52', 'mard_221',
                        'lab', 0, 'number', 2704, 0,
                        '2026-01-01T00:00:00Z', NULL, 0
                    );
                    """
                )
                connection.commit()

            database = Database(path)
            database.initialise()
            artwork = database.get_artwork("j1")

            self.assertIsNotNone(artwork)
            self.assertTrue(artwork.is_saved)


if __name__ == "__main__":
    unittest.main()
