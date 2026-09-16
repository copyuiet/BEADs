"""PNG、PDF 和 CSV 文件下载接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from backend.api.dependencies import get_current_user
from backend.core.database import UserRecord
from backend.core.services import ApplicationServices
from backend.core.storage import AssetStore, StorageError


router = APIRouter(tags=["export"])


@router.get("/export/{job_id}/{kind}", response_class=FileResponse)
def export_artifact(
    job_id: str,
    kind: str,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> FileResponse:
    services: ApplicationServices = request.app.state.services
    try:
        artwork = services.database.get_artwork(job_id)
        if artwork is None or artwork.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
        path, media_type = services.store.artifact_path(job_id, kind)
        filename = AssetStore.ARTIFACT_NAMES[kind][0]
        return FileResponse(path, media_type=media_type, filename=filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


__all__ = ["router"]
