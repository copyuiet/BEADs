# 单镜像部署：先用 Node 构建前端，再放进 Python 运行时由 FastAPI 同源托管。

# ---------- 阶段 1：构建前端 ----------
FROM node:22-alpine AS web

WORKDIR /web

# 先只拷贝依赖清单，命中镜像层缓存
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN npm i -g pnpm@10 && pnpm install --frozen-lockfile

COPY frontend/ ./

# 同源部署时留空即可：前端会用相对路径 /api 访问同一个域名下的后端
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm build

# ---------- 阶段 2：后端运行时 ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 系统依赖说明（缺一个就会静默降级，务必保留）：
#   libglib2.0-0       opencv-python-headless 的运行时依赖
#   fonts-dejavu-core  提供 /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf。
#                      bead_generator 用它渲染图纸上的色号数字，缺失会回退到
#                      PIL 点阵字体，色号会明显发糊。
#   fonts-noto-cjk     提供 /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc。
#                      pdf_exporter 用它渲染 A4 PDF 中的中文，缺失会回退到
#                      reportlab 内置的 STSong-Light（可用，但与本机输出不一致）。
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libglib2.0-0 \
      fonts-dejavu-core \
      fonts-noto-cjk \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY backend ./backend
COPY serve.py ./
COPY --from=web /web/dist ./frontend/dist

# 运行产物（SQLite、uploads、outputs）统一落在 /data，部署时把持久卷挂到这里
ENV BEAD_RUNTIME_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

# 平台会注入 PORT；--proxy-headers 让生成的 URL 使用 https 与真实域名
CMD ["sh", "-c", "uvicorn serve:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
