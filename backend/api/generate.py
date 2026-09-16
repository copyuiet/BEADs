"""拼豆图纸生成及基础数据接口。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api.dependencies import get_current_user
from backend.core.bead_generator import BeadGeneratorError, SPECIFICATIONS
from backend.core.color_mapper import ColorMappingError, PaletteError
from backend.core.database import DatabaseError, UserRecord
from backend.core.image_processor import ImageProcessingError, create_content_mask
from backend.core.pdf_exporter import build_pattern_pdf
from backend.core.services import ApplicationServices
from backend.core.statistic import calculate_statistics, statistics_to_csv
from backend.core.storage import StorageError
from backend.models.schemas import (
    ColorStatisticResponse,
    GenerateRequest,
    GenerateResponse,
    PaletteResponse,
    PatternType,
    SpecificationResponse,
)


router = APIRouter(tags=["generation"])


@router.get("/palettes", response_model=list[PaletteResponse])
def list_palettes(request: Request) -> list[PaletteResponse]:
    services: ApplicationServices = request.app.state.services
    return [PaletteResponse(**item) for item in services.palettes.available()]


@router.get("/specifications", response_model=list[SpecificationResponse])
def list_specifications() -> list[SpecificationResponse]:
    return [SpecificationResponse(**asdict(specification)) for specification in SPECIFICATIONS.values()]


@router.post("/generate", response_model=GenerateResponse)
def generate_pattern(
    payload: GenerateRequest,
    request: Request,
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> GenerateResponse:
    services: ApplicationServices = request.app.state.services
    try:
        if not services.database.owns_upload(payload.image_id, user.id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="上传图片不存在或不属于当前用户")
        upload_path = services.store.upload_path(payload.image_id)
        image = services.image_processor.process(
            upload_path,
            payload.size,
            payload.resize_mode,
            payload.content_scale,
        )
        active_mask = create_content_mask(payload.size, payload.content_scale)
        result = services.generator.generate(
            image=image,
            size=payload.size,
            palette_key=payload.palette,
            color_mode=payload.color_mode,
            dithering=payload.dithering,
            active_mask=active_mask,
        )
        statistics = calculate_statistics(result.mapped)
        pdf = build_pattern_pdf(result, statistics)
        csv_payload = statistics_to_csv(statistics)

        job_id, _ = services.store.create_job()
        color_path = services.store.save_image(job_id, "color", result.color_pattern)
        number_path = services.store.save_image(job_id, "number", result.number_pattern)
        services.store.save_bytes(job_id, "pdf", pdf)
        services.store.save_bytes(job_id, "csv", csv_payload)

        services.database.create_artwork(
            job_id=job_id,
            user_id=user.id,
            image_id=payload.image_id,
            title=f"{payload.size} 拼豆图纸",
            size=payload.size,
            palette=payload.palette,
            color_mode=payload.color_mode,
            dithering=payload.dithering,
            pattern_type=payload.pattern_type.value,
            active_bead_count=sum(item.count for item in statistics),
        )
        stale_job_ids = services.database.discard_unsaved_for_upload(
            user.id,
            payload.image_id,
            job_id,
        )
        for stale_job_id in stale_job_ids:
            services.store.delete_job(stale_job_id)

        selected_kind = "number" if payload.pattern_type is PatternType.NUMBER else "color"
        color_preview_token, _ = services.tokens.issue(f"asset:{job_id}:color", 60 * 60)
        number_preview_token, _ = services.tokens.issue(f"asset:{job_id}:number", 60 * 60)
        color_preview_url = f"/api/assets/{job_id}/color?token={color_preview_token}"
        number_preview_url = f"/api/assets/{job_id}/number?token={number_preview_token}"
        specification = SpecificationResponse(**asdict(result.specification))
        return GenerateResponse(
            job_id=job_id,
            preview_url=number_preview_url if selected_kind == "number" else color_preview_url,
            color_preview_url=color_preview_url,
            number_preview_url=number_preview_url,
            png_url=f"/api/export/{job_id}/{selected_kind}",
            pdf_url=f"/api/export/{job_id}/pdf",
            csv_url=f"/api/export/{job_id}/csv",
            specification=specification,
            palette=payload.palette,
            color_mode=payload.color_mode,
            dithering=payload.dithering,
            active_bead_count=sum(item.count for item in statistics),
            statistics=[ColorStatisticResponse(**asdict(item)) for item in statistics],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (
        StorageError,
        DatabaseError,
        ImageProcessingError,
        BeadGeneratorError,
        PaletteError,
        ColorMappingError,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


__all__ = ["router"]
