"""图片上传接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.dependencies import get_current_user
from backend.core.auth import AuthenticationError
from backend.core.database import UserRecord
from backend.core.image_processor import ImageProcessingError
from backend.core.services import ApplicationServices
from backend.models.schemas import UploadResponse


router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> UploadResponse:
    services: ApplicationServices = request.app.state.services
    limit = services.image_processor.config.max_upload_bytes
    try:
        payload = await file.read(limit + 1)
        image = services.image_processor.load_image(payload)
        image_id, path = services.store.save_upload(image)
        services.database.register_upload(image_id, user.id)
        preview_token, _ = services.tokens.issue(f"upload:{image_id}", 60 * 60)
        return UploadResponse(
            image_id=image_id,
            original_url=f"/api/uploads/{image_id}?token={preview_token}",
            width=image.width,
            height=image.height,
        )
    except ImageProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await file.close()


@router.get("/uploads/{image_id}", response_class=FileResponse)
def preview_upload(image_id: str, request: Request, token: str = Query(...)) -> FileResponse:
    services: ApplicationServices = request.app.state.services
    try:
        if services.tokens.decode(token) != f"upload:{image_id}":
            raise AuthenticationError("预览地址无效")
        return FileResponse(services.store.upload_path(image_id), media_type="image/png")
    except (AuthenticationError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


__all__ = ["router"]
