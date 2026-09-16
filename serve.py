"""生产入口：在 FastAPI 之上托管已构建的前端，单域名对外提供服务。

- 本地开发仍然用 ``uvicorn backend.main:app --reload``（前端走 Vite 代理）。
- 部署时用 ``uvicorn serve:app``：同源提供前端页面与 /api 接口，因此不需要配置 CORS。

本文件不修改 backend/ 下的任何代码，只是在既有 app 上追加静态资源挂载与 SPA 回退。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.main import app


DIST = (Path(__file__).resolve().parent / "frontend" / "dist").resolve()

if not DIST.is_dir():
    raise RuntimeError(f"未找到前端构建产物：{DIST}。请先在 frontend/ 下执行构建。")


app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str) -> FileResponse:
    """命中真实文件就返回文件，否则回退到 index.html 交给前端路由。

    该路由注册在所有 /api 路由之后，因此不会拦截接口请求。
    """

    # 未匹配到的接口路径要返回 404，不能回退成首页，否则会掩盖接口拼写错误
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="接口不存在")

    if full_path:
        candidate = (DIST / full_path).resolve()
        # 只允许返回构建目录内的文件，避免路径穿越
        if candidate.is_file() and candidate.is_relative_to(DIST):
            return FileResponse(candidate)
    return FileResponse(DIST / "index.html")


__all__ = ["app"]
