"""个人作品库和公开社区接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse

from backend.api.dependencies import get_current_user
from backend.core.auth import AuthenticationError
from backend.core.database import ArtworkRecord, DatabaseError, UserRecord
from backend.core.services import ApplicationServices
from backend.core.storage import AssetStore, StorageError
from backend.models.schemas import ArtworkResponse, PublishArtworkRequest


router = APIRouter(tags=["artworks"])


@router.post("/artworks/{job_id}/save", response_model=ArtworkResponse)
def save_artwork(
    job_id: str,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> ArtworkResponse:
    services: ApplicationServices = request.app.state.services
    try:
        artwork = services.database.save_artwork(job_id, user.id)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _artwork_response(artwork, services, public_links=False)


@router.delete("/artworks/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artwork(
    job_id: str,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> Response:
    services: ApplicationServices = request.app.state.services
    try:
        services.database.delete_artwork(job_id, user.id)
        services.store.delete_job(job_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/artworks", response_model=list[ArtworkResponse])
def my_artworks(
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> list[ArtworkResponse]:
    services: ApplicationServices = request.app.state.services
    return [_artwork_response(item, services, public_links=False) for item in services.database.list_user_artworks(user.id)]


@router.post("/artworks/{job_id}/publish", response_model=ArtworkResponse)
def publish_artwork(
    job_id: str,
    payload: PublishArtworkRequest,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> ArtworkResponse:
    services: ApplicationServices = request.app.state.services
    try:
        artwork = services.database.publish_artwork(job_id, user.id, payload.title, payload.description)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _artwork_response(artwork, services, public_links=False)


@router.post("/artworks/{job_id}/unpublish", response_model=ArtworkResponse)
def unpublish_artwork(
    job_id: str,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> ArtworkResponse:
    services: ApplicationServices = request.app.state.services
    try:
        artwork = services.database.unpublish_artwork(job_id, user.id)
    except DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _artwork_response(artwork, services, public_links=False)


@router.get("/community", response_model=list[ArtworkResponse])
def community_artworks(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ArtworkResponse]:
    services: ApplicationServices = request.app.state.services
    return [
        _artwork_response(item, services, public_links=True)
        for item in services.database.list_public_artworks(limit, offset)
    ]


@router.get("/community/{job_id}", response_model=ArtworkResponse)
def community_artwork(job_id: str, request: Request) -> ArtworkResponse:
    services: ApplicationServices = request.app.state.services
    artwork = services.database.get_artwork(job_id)
    if artwork is None or not artwork.is_public:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社区作品不存在")
    return _artwork_response(artwork, services, public_links=True)


@router.get("/assets/{job_id}/{kind}", response_class=FileResponse)
def preview_private_artwork(job_id: str, kind: str, token: str, request: Request) -> FileResponse:
    services: ApplicationServices = request.app.state.services
    if kind not in {"color", "number"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预览文件不存在")
    try:
        if services.tokens.decode(token) != f"asset:{job_id}:{kind}":
            raise AuthenticationError("预览地址无效")
        path, media_type = services.store.artifact_path(job_id, kind)
        return FileResponse(path, media_type=media_type)
    except (AuthenticationError, FileNotFoundError, StorageError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/community/{job_id}/preview/{kind}", response_class=FileResponse)
def preview_community_artwork(job_id: str, kind: str, request: Request) -> FileResponse:
    services: ApplicationServices = request.app.state.services
    artwork = services.database.get_artwork(job_id)
    if artwork is None or not artwork.is_public or kind not in {"color", "number"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社区作品不存在")
    try:
        path, media_type = services.store.artifact_path(job_id, kind)
        return FileResponse(path, media_type=media_type)
    except (FileNotFoundError, StorageError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/community/{job_id}/download/{kind}", response_class=FileResponse)
def download_community_artwork(job_id: str, kind: str, request: Request) -> FileResponse:
    services: ApplicationServices = request.app.state.services
    artwork = services.database.get_artwork(job_id)
    if artwork is None or not artwork.is_public:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="社区作品不存在")
    try:
        path, media_type = services.store.artifact_path(job_id, kind)
        services.database.increment_download(job_id)
        return FileResponse(path, media_type=media_type, filename=AssetStore.ARTIFACT_NAMES[kind][0])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _artwork_response(
    artwork: ArtworkRecord,
    services: ApplicationServices,
    *,
    public_links: bool,
) -> ArtworkResponse:
    base = f"/api/community/{artwork.job_id}/download" if public_links else f"/api/export/{artwork.job_id}"
    if public_links:
        color_preview_url = f"/api/community/{artwork.job_id}/preview/color"
        number_preview_url = f"/api/community/{artwork.job_id}/preview/number"
    else:
        color_token, _ = services.tokens.issue(f"asset:{artwork.job_id}:color", 60 * 60)
        number_token, _ = services.tokens.issue(f"asset:{artwork.job_id}:number", 60 * 60)
        color_preview_url = f"/api/assets/{artwork.job_id}/color?token={color_token}"
        number_preview_url = f"/api/assets/{artwork.job_id}/number?token={number_token}"
    return ArtworkResponse(
        job_id=artwork.job_id,
        user_id=artwork.user_id,
        username=artwork.username,
        title=artwork.title,
        description=artwork.description,
        size=artwork.size,
        palette=artwork.palette,
        color_mode=artwork.color_mode,
        dithering=artwork.dithering,
        pattern_type=artwork.pattern_type,
        active_bead_count=artwork.active_bead_count,
        is_saved=artwork.is_saved,
        is_public=artwork.is_public,
        created_at=artwork.created_at,
        published_at=artwork.published_at,
        download_count=artwork.download_count,
        color_preview_url=color_preview_url,
        number_preview_url=number_preview_url,
        png_url=f"{base}/{artwork.pattern_type}",
        pdf_url=f"{base}/pdf",
        csv_url=f"{base}/csv",
    )


__all__ = ["router"]
