"""FastAPI 请求和响应模型。"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PatternType(str, Enum):
    COLOR = "color"
    NUMBER = "number"


class UploadResponse(BaseModel):
    image_id: str
    original_url: str
    width: int
    height: int


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=32, pattern=r"^[\w\u4e00-\u9fff-]+$")
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    username: str
    created_at: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class GenerateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    image_id: str = Field(min_length=36, max_length=36)
    size: Literal["52x52", "80x80", "104x104"] = "52x52"
    palette: Literal["mard_221", "mard_291"] = "mard_221"
    color_mode: Literal["lab", "rgb"] = "lab"
    dithering: bool = False
    pattern_type: PatternType = PatternType.NUMBER
    resize_mode: Literal["fit_pad", "crop_fill"] = "fit_pad"
    content_scale: float = Field(default=1.0, ge=0.2, le=1.0)


class ColorStatisticResponse(BaseModel):
    code: str
    name: str | None
    hex: str
    rgb: tuple[int, int, int]
    count: int
    percentage: float


class SpecificationResponse(BaseModel):
    key: str
    columns: int
    rows: int
    bead_count: int
    width_mm: float
    height_mm: float


class GenerateResponse(BaseModel):
    job_id: str
    preview_url: str
    color_preview_url: str
    number_preview_url: str
    png_url: str
    pdf_url: str
    csv_url: str
    specification: SpecificationResponse
    palette: str
    color_mode: str
    dithering: bool
    active_bead_count: int
    statistics: list[ColorStatisticResponse]


class PublishArtworkRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)


class ArtworkResponse(BaseModel):
    job_id: str
    user_id: str
    username: str
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
    color_preview_url: str
    number_preview_url: str
    png_url: str
    pdf_url: str
    csv_url: str


class ChatUserResponse(BaseModel):
    id: str
    username: str
    last_message: str | None = None
    last_message_at: str | None = None
    unread_count: int = 0


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=1000)


class ChatMessageResponse(BaseModel):
    id: int
    sender_id: str
    recipient_id: str
    body: str
    created_at: str
    read_at: str | None


class PaletteResponse(BaseModel):
    key: str
    label: str
    color_count: int


class HealthResponse(BaseModel):
    status: str
    palettes: int


__all__ = [
    "ArtworkResponse",
    "AuthResponse",
    "ChatMessageResponse",
    "ChatUserResponse",
    "ColorStatisticResponse",
    "CredentialsRequest",
    "GenerateRequest",
    "GenerateResponse",
    "HealthResponse",
    "PaletteResponse",
    "PatternType",
    "PublishArtworkRequest",
    "SendMessageRequest",
    "SpecificationResponse",
    "UploadResponse",
    "UserResponse",
]
