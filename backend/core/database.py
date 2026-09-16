"""用户、上传记录和拼豆作品的 SQLite 持久化。"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class DatabaseError(ValueError):
    """数据库约束或数据状态不允许当前操作。"""


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: str
    username: str
    password_hash: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ArtworkRecord:
    job_id: str
    user_id: str
    username: str
    image_id: str
    title: str
    description: str
    size: str
    palette: str
    color_mode: str
    dithering: bool
    pattern_type: str
    active_bead_count: int
    is_saved: bool
    is_public: bool
    created_at: str
    published_at: str | None
    download_count: int


@dataclass(frozen=True, slots=True)
class ChatUserRecord:
    id: str
    username: str
    last_message: str | None = None
    last_message_at: str | None = None
    unread_count: int = 0


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: int
    sender_id: str
    recipient_id: str
    body: str
    created_at: str
    read_at: str | None


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def initialise(self) -> None:
        """创建或升级数据库结构；由应用 lifespan 在开始服务前调用。"""

        self._initialise()

    def create_user(self, username: str, password_hash: str) -> UserRecord:
        user_id = str(uuid.uuid4())
        created_at = _now()
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO users (id, username, username_normalized, password_hash, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, username.casefold(), password_hash, created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise DatabaseError("该用户名已被注册") from exc
        return UserRecord(user_id, username, password_hash, created_at)

    def get_user_by_username(self, username: str) -> UserRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE username_normalized = ?",
                (username.casefold(),),
            ).fetchone()
        return _user_from_row(row)

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return _user_from_row(row)

    def register_upload(self, image_id: str, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO uploads (image_id, user_id, created_at) VALUES (?, ?, ?)",
                (image_id, user_id, _now()),
            )

    def owns_upload(self, image_id: str, user_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM uploads WHERE image_id = ? AND user_id = ?",
                (image_id, user_id),
            ).fetchone()
        return row is not None

    def create_artwork(
        self,
        *,
        job_id: str,
        user_id: str,
        image_id: str,
        title: str,
        size: str,
        palette: str,
        color_mode: str,
        dithering: bool,
        pattern_type: str,
        active_bead_count: int,
    ) -> ArtworkRecord:
        created_at = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artworks (
                    job_id, user_id, image_id, title, description, size, palette,
                    color_mode, dithering, pattern_type, active_bead_count,
                    is_saved, is_public, created_at, published_at, download_count
                ) VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, 0, 0, ?, NULL, 0)
                """,
                (
                    job_id,
                    user_id,
                    image_id,
                    title,
                    size,
                    palette,
                    color_mode,
                    int(dithering),
                    pattern_type,
                    active_bead_count,
                    created_at,
                ),
            )
        artwork = self.get_artwork(job_id)
        if artwork is None:  # pragma: no cover - 数据库写入后的防御检查
            raise DatabaseError("作品记录保存失败")
        return artwork

    def get_artwork(self, job_id: str) -> ArtworkRecord | None:
        with self._connect() as connection:
            row = connection.execute(_ARTWORK_SELECT + " WHERE a.job_id = ?", (job_id,)).fetchone()
        return _artwork_from_row(row)

    def list_user_artworks(self, user_id: str) -> list[ArtworkRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                _ARTWORK_SELECT + " WHERE a.user_id = ? AND a.is_saved = 1 ORDER BY a.created_at DESC",
                (user_id,),
            ).fetchall()
        return [_artwork_from_row(row) for row in rows if row is not None]

    def list_public_artworks(self, limit: int, offset: int) -> list[ArtworkRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                _ARTWORK_SELECT
                + " WHERE a.is_saved = 1 AND a.is_public = 1 ORDER BY a.published_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_artwork_from_row(row) for row in rows if row is not None]

    def publish_artwork(
        self,
        job_id: str,
        user_id: str,
        title: str,
        description: str,
    ) -> ArtworkRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE artworks SET title = ?, description = ?, is_public = 1, "
                "published_at = COALESCE(published_at, ?) "
                "WHERE job_id = ? AND user_id = ? AND is_saved = 1",
                (title, description, _now(), job_id, user_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseError("作品不存在或不属于当前用户")
        artwork = self.get_artwork(job_id)
        if artwork is None:  # pragma: no cover
            raise DatabaseError("作品发布失败")
        return artwork

    def save_artwork(self, job_id: str, user_id: str) -> ArtworkRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE artworks SET is_saved = 1 WHERE job_id = ? AND user_id = ?",
                (job_id, user_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseError("图纸不存在或不属于当前用户")
        artwork = self.get_artwork(job_id)
        if artwork is None:  # pragma: no cover
            raise DatabaseError("图纸保存失败")
        return artwork

    def delete_artwork(self, job_id: str, user_id: str) -> ArtworkRecord:
        artwork = self.get_artwork(job_id)
        if artwork is None or artwork.user_id != user_id or not artwork.is_saved:
            raise DatabaseError("作品不存在或不属于当前用户")
        with self._connect() as connection:
            connection.execute("DELETE FROM artworks WHERE job_id = ?", (job_id,))
        return artwork

    def discard_unsaved_for_upload(
        self,
        user_id: str,
        image_id: str,
        keep_job_id: str,
    ) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT job_id FROM artworks WHERE user_id = ? AND image_id = ? "
                "AND is_saved = 0 AND job_id <> ?",
                (user_id, image_id, keep_job_id),
            ).fetchall()
            job_ids = [row["job_id"] for row in rows]
            connection.executemany("DELETE FROM artworks WHERE job_id = ?", [(item,) for item in job_ids])
        return job_ids

    def search_users(self, current_user_id: str, query: str, limit: int = 30) -> list[ChatUserRecord]:
        pattern = f"%{query.casefold()}%"
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, username FROM users WHERE id <> ? AND username_normalized LIKE ? "
                "ORDER BY username_normalized LIMIT ?",
                (current_user_id, pattern, limit),
            ).fetchall()
        return [ChatUserRecord(row["id"], row["username"]) for row in rows]

    def list_conversations(self, user_id: str) -> list[ChatUserRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT u.id, u.username,
                       (SELECT body FROM messages lm
                        WHERE (lm.sender_id = ? AND lm.recipient_id = u.id)
                           OR (lm.sender_id = u.id AND lm.recipient_id = ?)
                        ORDER BY lm.id DESC LIMIT 1) AS last_message,
                       (SELECT created_at FROM messages lm
                        WHERE (lm.sender_id = ? AND lm.recipient_id = u.id)
                           OR (lm.sender_id = u.id AND lm.recipient_id = ?)
                        ORDER BY lm.id DESC LIMIT 1) AS last_message_at,
                       (SELECT COUNT(*) FROM messages um
                        WHERE um.sender_id = u.id AND um.recipient_id = ? AND um.read_at IS NULL) AS unread_count
                FROM users u
                WHERE u.id <> ? AND EXISTS (
                    SELECT 1 FROM messages m
                    WHERE (m.sender_id = ? AND m.recipient_id = u.id)
                       OR (m.sender_id = u.id AND m.recipient_id = ?)
                )
                ORDER BY last_message_at DESC
                """,
                (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id),
            ).fetchall()
        return [
            ChatUserRecord(
                id=row["id"],
                username=row["username"],
                last_message=row["last_message"],
                last_message_at=row["last_message_at"],
                unread_count=row["unread_count"],
            )
            for row in rows
        ]

    def list_messages(
        self,
        user_id: str,
        other_user_id: str,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[MessageRecord]:
        if self.get_user(other_user_id) is None:
            raise DatabaseError("用户不存在")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, sender_id, recipient_id, body, created_at, read_at
                FROM messages
                WHERE id > ? AND ((sender_id = ? AND recipient_id = ?)
                              OR (sender_id = ? AND recipient_id = ?))
                ORDER BY id ASC LIMIT ?
                """,
                (after_id, user_id, other_user_id, other_user_id, user_id, limit),
            ).fetchall()
            connection.execute(
                "UPDATE messages SET read_at = ? WHERE sender_id = ? AND recipient_id = ? AND read_at IS NULL",
                (_now(), other_user_id, user_id),
            )
        return [_message_from_row(row) for row in rows]

    def send_message(self, sender_id: str, recipient_id: str, body: str) -> MessageRecord:
        if sender_id == recipient_id:
            raise DatabaseError("不能给自己发送消息")
        if self.get_user(recipient_id) is None:
            raise DatabaseError("接收用户不存在")
        created_at = _now()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO messages (sender_id, recipient_id, body, created_at) VALUES (?, ?, ?, ?)",
                (sender_id, recipient_id, body, created_at),
            )
            message_id = int(cursor.lastrowid)
        return MessageRecord(message_id, sender_id, recipient_id, body, created_at, None)

    def unpublish_artwork(self, job_id: str, user_id: str) -> ArtworkRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE artworks SET is_public = 0, published_at = NULL "
                "WHERE job_id = ? AND user_id = ?",
                (job_id, user_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseError("作品不存在或不属于当前用户")
        artwork = self.get_artwork(job_id)
        if artwork is None:  # pragma: no cover
            raise DatabaseError("作品取消发布失败")
        return artwork

    def increment_download(self, job_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE artworks SET download_count = download_count + 1 "
                "WHERE job_id = ? AND is_public = 1",
                (job_id,),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_normalized TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS uploads (
                    image_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artworks (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    image_id TEXT NOT NULL REFERENCES uploads(image_id) ON DELETE RESTRICT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    size TEXT NOT NULL,
                    palette TEXT NOT NULL,
                    color_mode TEXT NOT NULL,
                    dithering INTEGER NOT NULL,
                    pattern_type TEXT NOT NULL,
                    active_bead_count INTEGER NOT NULL,
                    is_saved INTEGER NOT NULL DEFAULT 0,
                    is_public INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    download_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    read_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_artworks_user_created
                    ON artworks(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_artworks_public_published
                    ON artworks(is_public, published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_pair
                    ON messages(sender_id, recipient_id, id);
                CREATE INDEX IF NOT EXISTS idx_messages_unread
                    ON messages(recipient_id, read_at, id);
                """
            )
            artwork_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(artworks)").fetchall()
            }
            if "is_saved" not in artwork_columns:
                connection.execute(
                    "ALTER TABLE artworks ADD COLUMN is_saved INTEGER NOT NULL DEFAULT 1"
                )


_ARTWORK_SELECT = """
SELECT a.job_id, a.user_id, u.username, a.image_id, a.title, a.description,
       a.size, a.palette, a.color_mode, a.dithering, a.pattern_type,
       a.active_bead_count, a.is_saved, a.is_public, a.created_at, a.published_at,
       a.download_count
FROM artworks a JOIN users u ON u.id = a.user_id
"""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _user_from_row(row: sqlite3.Row | None) -> UserRecord | None:
    if row is None:
        return None
    return UserRecord(row["id"], row["username"], row["password_hash"], row["created_at"])


def _artwork_from_row(row: sqlite3.Row | None) -> ArtworkRecord | None:
    if row is None:
        return None
    return ArtworkRecord(
        job_id=row["job_id"],
        user_id=row["user_id"],
        username=row["username"],
        image_id=row["image_id"],
        title=row["title"],
        description=row["description"],
        size=row["size"],
        palette=row["palette"],
        color_mode=row["color_mode"],
        dithering=bool(row["dithering"]),
        pattern_type=row["pattern_type"],
        active_bead_count=row["active_bead_count"],
        is_saved=bool(row["is_saved"]),
        is_public=bool(row["is_public"]),
        created_at=row["created_at"],
        published_at=row["published_at"],
        download_count=row["download_count"],
    )


def _message_from_row(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord(
        id=row["id"],
        sender_id=row["sender_id"],
        recipient_id=row["recipient_id"],
        body=row["body"],
        created_at=row["created_at"],
        read_at=row["read_at"],
    )


__all__ = [
    "ArtworkRecord",
    "ChatUserRecord",
    "Database",
    "DatabaseError",
    "MessageRecord",
    "UserRecord",
]
