"""密码哈希和无状态登录令牌。仅使用 Python 标准库。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path


class AuthenticationError(ValueError):
    """凭据或登录令牌无效。"""


class PasswordHasher:
    """使用 PBKDF2-HMAC-SHA256 保存不可逆密码摘要。"""

    iterations = 600_000

    @classmethod
    def hash(cls, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, cls.iterations)
        return f"pbkdf2_sha256${cls.iterations}${salt.hex()}${digest.hex()}"

    @classmethod
    def verify(cls, password: str, encoded: str) -> bool:
        try:
            algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
            return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
        except (ValueError, TypeError):
            return False


class TokenManager:
    """签发带有效期的 HMAC-SHA256 访问令牌。"""

    def __init__(self, runtime_root: Path, lifetime_seconds: int = 7 * 24 * 60 * 60) -> None:
        self.lifetime_seconds = lifetime_seconds
        self.runtime_root = runtime_root
        self.secret: bytes | None = None

    def initialise(self) -> None:
        configured = os.getenv("BEAD_SECRET_KEY")
        self.secret = configured.encode("utf-8") if configured else self._load_or_create_secret(self.runtime_root)

    def issue(self, subject: str, lifetime_seconds: int | None = None) -> tuple[str, int]:
        now = int(time.time())
        lifetime = lifetime_seconds or self.lifetime_seconds
        payload = {
            "sub": subject,
            "iat": now,
            "exp": now + lifetime,
            "nonce": secrets.token_hex(8),
        }
        body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = _b64encode(hmac.new(self._secret(), body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{signature}", lifetime

    def decode(self, token: str) -> str:
        try:
            body, signature = token.split(".", 1)
            expected = _b64encode(hmac.new(self._secret(), body.encode("ascii"), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                raise AuthenticationError("登录状态无效，请重新登录")
            payload = json.loads(_b64decode(body))
            if not isinstance(payload.get("sub"), str) or int(payload.get("exp", 0)) < int(time.time()):
                raise AuthenticationError("登录已过期，请重新登录")
            return payload["sub"]
        except AuthenticationError:
            raise
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AuthenticationError("登录状态无效，请重新登录") from exc

    @staticmethod
    def _load_or_create_secret(runtime_root: Path) -> bytes:
        path = runtime_root / ".auth-secret"
        if path.is_file():
            secret = path.read_bytes()
            if len(secret) >= 32:
                return secret
        secret = secrets.token_bytes(48)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(secret)
        return secret

    def _secret(self) -> bytes:
        if self.secret is None:
            raise AuthenticationError("身份验证服务尚未初始化")
        return self.secret


def _b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _b64decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


__all__ = ["AuthenticationError", "PasswordHasher", "TokenManager"]
