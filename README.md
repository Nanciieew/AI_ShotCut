# Movie Analysis Platform

多模型视频分析后端 — 电影镜头切分、场景合并、多模态特征分析与 Scene Score 计算。

## 技术栈

- **API**: FastAPI
- **任务队列**: Celery + Redis
- **数据库**: PostgreSQL（生产）/ SQLite（开发）
- **视频处理**: FFmpeg
- **模型运行**: PyTorch / Python
- **容器化**: Docker Compose

## 快速启动

### 1. 环境配置

```bash
cp .env.example .env
# 编辑 .env（开发环境可使用默认值）
```

### 2. 安装依赖

```bash
# 完整开发环境
pip install -r requirements.txt

# 仅 API
pip install -r requirements/api.txt

# 仅 Worker
pip install -r requirements/worker.txt
```

### 3. Docker Compose 启动

```bash
# 启动全部服务（PostgreSQL > Redis > migrate > API + Worker）
docker compose up -d

# 仅启动基础设施
docker compose up -d postgres redis

# 查看日志
docker compose logs -f api
docker compose logs -f worker

# 停止
docker compose down
```

### 4. 数据库迁移

```bash
# 生成迁移文件
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1

# 查看当前版本
alembic current

# 查看历史
alembic history
```

### 5. 本地开发（无 Docker）

```bash
# 启动 Redis
redis-server &

# 初始化数据库
python scripts/initialize_database.py

# 启动 Celery Worker
celery -A workers.celery_app worker --loglevel=info -Q video,shot,subtitle,feature,scene,final,maintenance &

# 启动 API
uvicorn apps.api.main:app --reload
```

### 6. 环境检查

```bash
# 项目级完整环境报告
python scripts/check_environment.py
python scripts/check_environment.py --json
python scripts/check_environment.py --output report.json

# OmniShotCut 专项检查（含模型权重、测试视频、兼容性）
python scripts/check_omnishotcut_environment.py
python scripts/check_omnishotcut_environment.py --check-fixtures
python scripts/check_omnishotcut_environment.py --load-model
python scripts/check_omnishotcut_environment.py --run-smoke-test
```

环境检查模块位于 `core/environment/`，覆盖：
- 操作系统 / 架构 / Python / CPU / 内存
- FFmpeg / FFprobe / Docker / nvidia-smi
- PyTorch / CUDA / GPU / Torchvision
- STORAGE_ROOT / MODEL_STORE_ROOT 磁盘空间和可写性

### 7. 验证

```bash
# 健康检查
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/health
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health/live` | 存活检查（进程） |
| `GET` | `/health/ready` | 就绪检查（DB+Redis+Storage+FFmpeg+Celery） |
| `GET` | `/health` | 兼容旧版，等同 `/health/ready` |
| `POST` | `/api/v1/videos` | 上传视频 |
| `GET` | `/api/v1/videos/{id}` | 获取视频信息 |
| `POST` | `/api/v1/videos/{id}/analysis` | 启动分析 |
| `GET` | `/api/v1/tasks/{id}` | 查询任务状态 |
| `GET` | `/api/v1/videos/{id}/results` | 获取分析结果 |
| `GET` | `/api/v1/models/{name}/health` | 模型健康检查（预留） |

## 模型接入

| 模型 | Task Name | 类型 | 说明 |
|------|-----------|------|------|
| FFmpeg | `video.normalize` | CPU | 视频归一化 (H.264+yuv420p CFR) |
| OmniShotCut | `shot.detect` | CPU | Shot 边界检测 |
| PyAV | `video.extract_keyframes` | CPU | 每 shot 2 帧关键帧 (25%+75%) |
| Doubao ASR | `subtitle.transcribe` | CPU | 语音转文字（火山引擎） |
| Qwen2.5-VL | `scene.score_vlm` | API | Location + Character 评分 |
| DeepSeek | `scene.score_plot` | API | 叙事事件 + Plot 评分 |
| Score Merger | `scene.merge_scores` | CPU | 加权合并 → 最终场景 |

## Worker Queue 路由

| Queue | 任务 |
|-------|------|
| `video` | `video.normalize`, `video.extract_keyframes` |
| `shot` | `shot.detect` |
| `subtitle` | `subtitle.transcribe` |
| `scene` | `scene.score_vlm`, `scene.score_plot`, `scene.merge_scores` |
| `final` | `final.pipeline_complete` |
| `maintenance` | 临时文件清理 |

## Pipeline

```
video.normalize → shot.detect
  → group(video.extract_keyframes, subtitle.transcribe)
    → group(scene.score_vlm, scene.score_plot)
      → scene.merge_scores → final.pipeline_complete
```

关键帧 320px proxy 模式（`--vlm-proxy`）使 2h 电影 VLM 评分从 ~57h 降至 ~3min。
Doubao ASR 自动对大音频分片并行（`>15min` → `ThreadPoolExecutor`）。

## 开发命令

```bash
python scripts/dev/start.py           # 启动全部服务
python scripts/dev/stop.py            # 停止全部服务
python scripts/dev/check.py           # lint + type + test
python scripts/dev/lint.py            # ruff check + format
python scripts/dev/test.py            # pytest
python scripts/dev/migrate.py upgrade # 数据库迁移
```

## 代码质量

```bash
ruff check .
ruff format --check .
mypy .
pytest
pytest --cov
pre-commit run --all-files
```

## 项目结构

```
apps/api/         — FastAPI 路由、依赖、Schema
core/             — 数据库、存储、异常、Artifact、日志、配置
models/           — 模型适配器 + Registry
workers/          — Celery 应用 + 7 任务队列
schemas/          — 统一数据 Schema（v1）
pipelines/        — 编排层
configs/          — YAML 配置
scripts/dev/      — 开发命令
alembic/          — 数据库迁移
tests/            — 测试 + Fixtures
requirements/     — 分层依赖
```

## 开发规范

- **开始前**：阅读 [CLAUDE.md](CLAUDE.md) → 查找 [IMPROVEMENTS.md](IMPROVEMENTS.md) 对应 IMP
- **模型接入**：遵守 [IO_Rule.md](IO_Rule.md) + [项目图纸.md](项目图纸.md)
- **禁止**：`action_score`、`plot_score`、API 内长推理、Redis 存大文件、覆盖旧 Artifact

## License

MIT
