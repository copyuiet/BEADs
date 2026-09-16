"""上传文件和生成产物的本地安全存储。"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from PIL import Image


class StorageError(ValueError):
    """资源标识或文件类型无效。"""


class AssetStore:
    ARTIFACT_NAMES: dict[str, tuple[str, str]] = {
        "color": ("color-pattern.png", "image/png"),
        "number": ("number-pattern.png", "image/png"),
        "pdf": ("mard-pattern.pdf", "application/pdf"),
        "csv": ("materials.csv", "text/csv; charset=utf-8"),
    }

    def __init__(self, root: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        configured = root or os.getenv("BEAD_RUNTIME_DIR") or project_root / "runtime"
        self.root = Path(configured).resolve()
        self.uploads = self.root / "uploads"
        self.outputs = self.root / "outputs"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.outputs.mkdir(parents=True, exist_ok=True)

    def save_upload(self, image: Image.Image) -> tuple[str, Path]:
        image_id = str(uuid.uuid4())
        path = self.uploads / f"{image_id}.png"
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", compress_level=6)
        self._atomic_write(path, buffer.getvalue())
        return image_id, path

    def upload_path(self, image_id: str) -> Path:
        safe_id = self._normalise_uuid(image_id)
        path = self.uploads / f"{safe_id}.png"
        if not path.is_file():
            raise FileNotFoundError("上传图片不存在或已过期")
        return path

    def create_job(self) -> tuple[str, Path]:
        job_id = str(uuid.uuid4())
        directory = self.outputs / job_id
        directory.mkdir(parents=False, exist_ok=False)
        return job_id, directory

    def save_image(self, job_id: str, kind: str, image: Image.Image) -> Path:
        path = self._artifact_destination(job_id, kind)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", compress_level=6)
        self._atomic_write(path, buffer.getvalue())
        return path

    def save_bytes(self, job_id: str, kind: str, payload: bytes) -> Path:
        path = self._artifact_destination(job_id, kind)
        self._atomic_write(path, payload)
        return path

    def artifact_path(self, job_id: str, kind: str) -> tuple[Path, str]:
        path = self._artifact_destination(job_id, kind)
        if not path.is_file():
            raise FileNotFoundError("导出文件不存在或已过期")
        return path, self.ARTIFACT_NAMES[kind][1]

    def delete_job(self, job_id: str) -> None:
        safe_id = self._normalise_uuid(job_id)
        directory = (self.outputs / safe_id).resolve()
        if directory.parent != self.outputs.resolve():
            raise StorageError("生成任务路径无效")
        if directory.is_dir():
            shutil.rmtree(directory)

    def _artifact_destination(self, job_id: str, kind: str) -> Path:
        safe_id = self._normalise_uuid(job_id)
        if kind not in self.ARTIFACT_NAMES:
            raise StorageError("不支持的导出文件类型")
        directory = self.outputs / safe_id
        if not directory.is_dir():
            raise FileNotFoundError("生成任务不存在或已过期")
        return directory / self.ARTIFACT_NAMES[kind][0]

    @staticmethod
    def _normalise_uuid(value: str) -> str:
        try:
            return str(uuid.UUID(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise StorageError("资源标识格式无效") from exc

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            os.replace(temporary_name, path)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)


__all__ = ["AssetStore", "StorageError"]
