"""FastAPI 共享依赖。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from backend.core.auth import AuthenticationError
from backend.core.database import UserRecord
from backend.core.services import ApplicationServices


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> UserRecord:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    services: ApplicationServices = request.app.state.services
    try:
        user_id = services.tokens.decode(authorization[7:].strip())
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = services.database.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账户不存在")
    return user


__all__ = ["get_current_user"]
