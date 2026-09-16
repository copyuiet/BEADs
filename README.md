# MARD 拼豆图纸生成器

基于真实 MARD 色卡的前后端分离 Web 应用。注册用户可以生成并主动保存拼豆图纸、管理个人作品，将作品发布到社区在线预览和下载，并通过站内私信交流。

## 数据原则

- 唯一颜色数据源是 `backend/data/palette.py`。
- 后端不会创建、修正、合并或模拟任何 MARD 颜色。
- Web 产品只开放 `MARD 221` 和 `MARD 291` 两套颜色库。
- 原始数据没有权威颜色名称字段，因此材料统计只展示色号、色块、HEX、数量和占比。
- `Q4` 与 `R11` 在原数据中具有相同 RGB；距离相同时保持原文件顺序，稳定选择 `Q4`。
- `content_scale` 小于 1 时，图案外围格子为空位，不匹配颜色、不显示色号，也不计入材料数量。

## 技术栈

- Python 3.12、FastAPI、Pydantic
- Pillow、NumPy、OpenCV、scikit-image
- ReportLab
- SQLite、PBKDF2-HMAC-SHA256、HMAC 访问令牌
- Vue 3、TypeScript、Vite、Element Plus

## 本地运行

### 1. 后端

```powershell
cd D:\Pindou_codex\bead-generator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

后端地址：`http://127.0.0.1:8000`  
API 文档：`http://127.0.0.1:8000/docs`

### 2. 前端

另开一个 PowerShell：

```powershell
cd D:\Pindou_codex\bead-generator\frontend
pnpm install
pnpm dev
```

前端地址：`http://127.0.0.1:5173`

开发环境通过 Vite 将 `/api` 代理到 FastAPI。分离部署时，在 `.env` 中设置：

```dotenv
VITE_API_BASE_URL=https://your-api.example.com
```

后端跨域来源可通过环境变量配置：

```powershell
$env:BEAD_CORS_ORIGINS="https://your-web.example.com"
```

运行产物与 SQLite 数据库默认存放于 `runtime/`。可通过 `BEAD_RUNTIME_DIR` 指定外部持久化目录。首次启动会自动创建数据库结构和本地令牌密钥；生产环境应通过 `BEAD_SECRET_KEY` 设置稳定的高强度密钥。

## 测试与构建

```powershell
cd D:\Pindou_codex\bead-generator
python -B -m unittest discover -s backend/tests -v

cd frontend
pnpm build
```

## API

除社区列表和社区下载外，账户、上传、生成、个人作品和私人导出接口均使用：

```http
Authorization: Bearer <access_token>
```

### 账户

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

### 上传图片

`POST /api/upload`，使用 `multipart/form-data` 的 `file` 字段上传 PNG/JPEG。

### 生成图纸

`POST /api/generate`

```json
{
  "image_id": "上传接口返回的 UUID",
  "size": "52x52",
  "palette": "mard_221",
  "color_mode": "lab",
  "dithering": true,
  "pattern_type": "number",
  "resize_mode": "fit_pad",
  "content_scale": 1.0
}
```

### 基础数据

- `GET /api/palettes`
- `GET /api/specifications`
- `GET /api/health`

### 导出

- `GET /api/export/{job_id}/color`
- `GET /api/export/{job_id}/number`
- `GET /api/export/{job_id}/pdf`
- `GET /api/export/{job_id}/csv`

### 个人作品与社区

- `GET /api/me/artworks`
- `POST /api/artworks/{job_id}/save`
- `POST /api/artworks/{job_id}/publish`
- `POST /api/artworks/{job_id}/unpublish`
- `DELETE /api/artworks/{job_id}`
- `GET /api/community`
- `GET /api/community/{job_id}`
- `GET /api/community/{job_id}/preview/{kind}`
- `GET /api/community/{job_id}/download/{kind}`

生成完成的图纸首先是临时草稿，只有调用 `save` 接口后才会进入个人作品库。同一上传图片的新草稿生成后，旧的未保存草稿会自动清理。

### 站内聊天

- `GET /api/chat/users?query=`
- `GET /api/chat/conversations`
- `GET /api/chat/{user_id}/messages`
- `POST /api/chat/{user_id}/messages`

消息保存在 SQLite 中，前端每 3 秒增量获取新消息。消息正文最长 1000 个字符，只有发送者和接收者能够读取。

## 核心模块

```text
backend/core/
├─ image_processor.py  图片校验、方向修正、补白/裁剪和降采样
├─ color_mapper.py     MARD 色库加载、RGB/Lab 和 Delta E 1976 匹配
├─ dithering.py        Floyd–Steinberg 误差扩散
├─ bead_generator.py   拼豆矩阵、色块图和色号图
├─ statistic.py        数量、占比和 CSV
├─ pdf_exporter.py     A4 矢量 PDF
├─ auth.py             密码哈希和访问令牌
├─ database.py         用户、上传和作品 SQLite 持久化
├─ storage.py          上传与产物安全存储
└─ services.py         应用服务组合
```

核心算法与 HTTP API 完全分离。未来可以在不改动颜色匹配模块的前提下增加评论、点赞、关注、内容审核、WebSocket 实时消息、异步任务、对象存储和电商材料购买流程。
