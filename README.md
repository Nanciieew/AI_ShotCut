# Movie Analysis Platform

影片自动分段后端：上传视频后，FastAPI 通过受控的进程内 Workflow/Executor 调度 Adapter，完成标准化、镜头检测、关键帧、语音识别、语义连续性、场景合并与 `scene_score` 计算。

## 当前架构

```text
FastAPI Route → TaskService → BackgroundExecutor → WorkflowService → Adapter
                                      ↓
                         PostgreSQL / SQLite + Artifact Storage
```

当前不使用 Celery、Redis 或独立 Worker。长任务在受控线程池中执行；进程重启时遗留任务会被标记为 `INTERRUPTED`。

主流程：

```text
upload → normalize(video.mp4, audio.wav) → detect shots → keyframes
       → Doubao Vision / Doubao ASR → subtitle semantic continuity
       → merge scenes → scene_score → FinalResult
```

评分模式仅支持 `location_only`、`character_only`、`subtitle_only`、`custom`；所有自定义权重按总和归一化。

## 开发启动

```bash
cp .env.example .env
pip install -r requirements/api.txt
alembic upgrade head
uvicorn apps.api.main:app --reload
```

Docker 开发环境会启动 PostgreSQL、迁移、Provider/ngrok（当配置启用）和 API：

```bash
docker compose up --build
```

## API

- `POST /api/v1/videos`：流式上传视频。
- `POST /api/v1/videos/{video_id}/tasks`：创建分析任务，返回新的 `task_id`。
- `GET /api/v1/tasks/{task_id}`：查询状态和进度。
- `POST /api/v1/tasks/{task_id}/retry`：创建不可变重试任务。
- `GET /api/v1/videos/{video_id}/results`：读取最近成功任务的 `FinalResult`。

创建任务时可传 `force_recompute`（`normalize`、`shots`、`keyframes`、`vision`、`asr`、`subtitle_semantic`）绕过对应跨任务缓存。

## 校验

```bash
ruff check .
ruff format --check .
mypy .
pytest tests/unit -q
```

更多架构约束见 [AGENTS.md](AGENTS.md)，Adapter 输入输出 Contract 见 [IO_Rule.md](IO_Rule.md)。
