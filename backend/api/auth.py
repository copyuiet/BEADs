"""用户注册、登录及当前账户接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api.dependencies import get_current_user
from backend.core.auth import PasswordHasher
from backend.core.database import DatabaseError, UserRecord
from backend.core.services import ApplicationServices
from backend.models.schemas import AuthResponse, CredentialsRequest, UserResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: CredentialsRequest, request: Request) -> AuthResponse:
    services: ApplicationServices = request.app.state.services
    try:
        user = services.database.create_user(payload.username, PasswordHasher.hash(payload.password))
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _auth_response(services, user)


@router.post("/login", response_model=AuthResponse)
def login(payload: CredentialsRequest, request: Request) -> AuthResponse:
    services: ApplicationServices = request.app.state.services
    user = services.database.get_user_by_username(payload.username)
    if user is None or not PasswordHasher.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return _auth_response(services, user)


@router.get("/me", response_model=UserResponse)
def current_user(user: Annotated[UserRecord, Depends(get_current_user)]) -> UserResponse:
    return _user_response(user)


def _auth_response(services: ApplicationServices, user: UserRecord) -> AuthResponse:
    token, expires_in = services.tokens.issue(user.id)
    return AuthResponse(access_token=token, expires_in=expires_in, user=_user_response(user))


def _user_response(user: UserRecord) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, created_at=user.created_at)


__all__ = ["router"]
