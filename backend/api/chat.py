"""站内用户目录、会话和私信接口。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.api.dependencies import get_current_user
from backend.core.database import DatabaseError, UserRecord
from backend.core.services import ApplicationServices
from backend.models.schemas import ChatMessageResponse, ChatUserResponse, SendMessageRequest


router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/users", response_model=list[ChatUserResponse])
def search_users(
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
    query: Annotated[str, Query(max_length=32)] = "",
) -> list[ChatUserResponse]:
    services: ApplicationServices = request.app.state.services
    return [ChatUserResponse(**asdict(item)) for item in services.database.search_users(user.id, query)]


@router.get("/conversations", response_model=list[ChatUserResponse])
def list_conversations(
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> list[ChatUserResponse]:
    services: ApplicationServices = request.app.state.services
    return [ChatUserResponse(**asdict(item)) for item in services.database.list_conversations(user.id)]


@router.get("/{other_user_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    other_user_id: str,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
    after_id: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ChatMessageResponse]:
    services: ApplicationServices = request.app.state.services
    try:
        messages = services.database.list_messages(user.id, other_user_id, after_id, limit)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [ChatMessageResponse(**asdict(item)) for item in messages]


@router.post("/{other_user_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    other_user_id: str,
    payload: SendMessageRequest,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> ChatMessageResponse:
    services: ApplicationServices = request.app.state.services
    try:
        message = services.database.send_message(user.id, other_user_id, payload.body)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ChatMessageResponse(**asdict(message))


__all__ = ["router"]
