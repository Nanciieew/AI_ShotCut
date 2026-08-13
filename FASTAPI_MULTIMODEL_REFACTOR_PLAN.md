# FastAPI 多模型后端一致性改造方案

> 适用项目：Movie Analysis Platform / AI_ShotCut
> 方案目标：修复 `FASTAPI_MULTIMODEL_WEB_ARCHITECTURE.md` 与现有 Task、Adapter、FastAPI、PostgreSQL、Artifact 和文件流转实现之间的冲突。
> 文档性质：实施方案。具体完成进度、临时问题和待办事项应记录到 `IMPROVEMENTS.md`，不在本文件维护短期状态。

---

## 1. 改造目标

本次改造需要同时满足以下结果：

1. 上传一次视频只创建一个 `video_id`，每次分析创建独立 `task_id`。
2. FastAPI 只负责请求、校验、上传、创建任务和查询，不执行长时间 FFmpeg 或模型推理。
3. FastAPI 通过项目内 Python Workflow/Executor 直接调用 Adapter，不重建 Celery、Redis 或独立 Worker 系统。
4. 每次模型调用先创建 `ModelRun`，Artifact 必须关联真实存在的 `run_id`。
5. PostgreSQL 通过 Alembic Migration 初始化和升级，不依赖 `create_all()`。
6. Adapter 只负责模型输入输出转换，不访问数据库、不决定文件布局、不拼接公网 URL、不调度其他模型。
7. 所有跨模块数据符合 `schemas/` 和统一模型 Contract。
8. 最终评分只保留 `scene_score`，彻底移除 `plot_score`、`action_score` 及对应 Evidence。
9. Artifact 路径同时包含 `project_id`、`video_id`、`task_id`、模型名和模型版本。
10. 文件上传采用流式写入，路径不可穿越，公网文件访问必须授权且可过期。
11. 中间 Artifact 可追踪、可复用、可单独重跑，并有 Manifest 和数据库索引。

---

## 2. 目标架构

```text
Frontend
   │
   │ POST /api/v1/videos
   ▼
FastAPI ──流式上传──> Storage
   │                    │
   │ 创建 Video         └─ video.original Artifact
   │
   │ POST /api/v1/videos/{video_id}/tasks
   ▼
PostgreSQL <──创建 Task / WorkflowRun
   │
   └──> Python Workflow / Executor
            │
            ├── normalize_video
            ├── detect_shots
            ├── transcribe
            ├── extract_features
            ├── detect_scene_boundaries
            └── merge / score / assemble
                      │
                      ▼
              Adapter → Model Provider
                      │
                      ▼
             Artifact + Manifest + DB Record
```

职责边界：

| 模块 | 允许职责 | 禁止职责 |
|---|---|---|
| FastAPI | 上传、校验、创建 Task、启动 Workflow、查询结果、鉴权下载 | 直接调用第三方模型 API、在路由函数中堆叠业务步骤 |
| Workflow/Executor | 按顺序执行步骤、选择缓存、创建 ModelRun、调用 Adapter、写 Artifact、处理失败和更新状态 | 绕过 Adapter 调用第三方模型 API |
| Adapter | Contract 校验、模型参数映射、原始输出标准化 | 数据库、HTTP 文件路由、最终评分、跨模型调用 |
| Storage | 路径生成、原子写入、读取、签名 URL、路径安全 | 业务 DAG |
| PostgreSQL | 元数据、状态、关系、索引、审计 | 保存视频、音频、大型特征矩阵 |

---

## 3. ID 与生命周期设计

### 3.1 ID 关系

```text
Project 1 ── N Video
Video   1 ── N Task
Task    1 ── N WorkflowRun
Task    1 ── N ModelRun
ModelRun N ── N Artifact（通过输入/输出关系表）
```

- `project_id`：业务项目隔离标识。
- `video_id`：上传视频的稳定身份，上传后不因重新分析而改变。
- `task_id`：一次分析请求的身份；同一视频可以创建多个 Task。
- `workflow_run_id`：一次指定版本 DAG 的执行记录。
- `run_id`：一次具体模型或处理器执行记录。
- `artifact_id`：一个不可变 Artifact 的身份，不得与 `run_id` 共用。
- `provider_request_id`：豆包等外部服务的请求 ID，禁止命名成内部 `task_id`。

所有 ID 使用 UUID，数据库字段至少保留 36 字符；若使用无连字符 UUID，则统一为 32 字符。禁止同时存在 12、16、32 字符的随机截断方案。

### 3.2 正确创建流程

```text
上传视频：
创建 project/video → 流式写入源文件 → 写 Manifest → 创建 video.original Artifact

启动分析：
接收已有 video_id → 创建 task_id → 创建 workflow_run_id
→ 启动 Python Workflow → 返回 task_id
```

`TaskService.create_task()` 必须调整为接收：

```python
create_task(project_id: str, video_id: str, parameters: dict) -> Task
```

该方法不得复制源视频，不得重新创建 Video。

---

## 4. API 改造

统一采用 `/api/v1/` 前缀：

原架构文档中的：

```http
POST /api/tasks
GET /api/tasks/{task_id}
```

与当前实现中的：

```http
POST /api/v1/videos
POST /api/v1/videos/{video_id}/analyze-shots
GET /api/v1/tasks/{task_id}
```

存在接口前缀和资源建模不一致。改造后不再维护两套正式定义，以本节的 `/api/v1/` 资源式 API 为唯一规范，并同步修改 OpenAPI、前端调用和旧架构文档。

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/v1/projects/{project_id}/videos` | 上传视频并创建 Video |
| `GET` | `/api/v1/videos/{video_id}` | 查询视频元数据 |
| `POST` | `/api/v1/videos/{video_id}/tasks` | 创建完整分析任务 |
| `GET` | `/api/v1/tasks/{task_id}` | 查询 Task 状态与进度 |
| `POST` | `/api/v1/tasks/{task_id}/retry` | 重试允许重试的失败步骤 |
| `GET` | `/api/v1/tasks/{task_id}/artifacts` | 查询本次 Task 的 Artifact |
| `GET` | `/api/v1/artifacts/{artifact_id}/download` | 获取授权下载或短期签名 URL |
| `GET` | `/api/v1/videos/{video_id}/results` | 查询最新或指定 Task 的最终结果 |

创建任务成功返回 HTTP `202 Accepted`：

```json
{
  "task_id": "...",
  "video_id": "...",
  "status": "PENDING",
  "stage": "created",
  "progress": 0
}
```

移除或废弃：

- `video_path` 表单参数；客户端不能提交服务器本地路径。
- `asyncio.create_task(asyncio.to_thread(...))` 主流程。
- 旧版按固定磁盘目录读取关键帧的路由。
- 未鉴权的整个 `/files` 静态目录挂载。

如果需要兼容旧前端，应保留旧路由一个版本周期，但内部转调新 Service，并返回弃用响应头。

---

## 5. PostgreSQL 与 Alembic 方案

### 5.1 必需数据表

保留并调整：

- `projects`
- `videos`
- `tasks`
- `workflow_runs`
- `model_runs`
- `artifacts`
- `model_run_inputs`
- `model_run_outputs`
- `shots`
- `subtitle_segments`
- `scenes`
- `scene_evidence`

### 5.2 关键字段

`tasks`：

```text
task_id PK
project_id FK
video_id FK
workflow_run_id FK
task_type
status
stage
progress
parameters_json
executor_run_id
retry_count
error_code
error_message
created_at / started_at / finished_at
```

`model_runs`：

```text
run_id PK
task_id FK
video_id FK
model_name
model_version
code_revision
weight_revision
schema_version
parameters_json
cache_key
status
runtime_ms
device
error_code
error_message
retryable
started_at / finished_at
```

`artifacts`：

```text
artifact_id PK
project_id FK
video_id FK
producer_run_id FK
artifact_type
uri
format
mime_type
size_bytes
sha256
schema_version
metadata_json
created_at
```

Artifact 不必直接保存 `task_id`；生产关系由 `producer_run_id → model_runs.task_id` 得出。为了查询性能，也可以增加只读冗余 `task_id`，但必须由 Service 写入并设置外键。

### 5.3 输入输出依赖表

```text
model_run_inputs(run_id, artifact_id, input_role)
model_run_outputs(run_id, artifact_id, output_role)
```

这两张表用于：

- 重建 DAG；
- 判断缓存是否可复用；
- 定位某个结果使用了哪些上游文件；
- 支持单步骤重跑；
- 防止 Adapter 依赖硬编码文件名。

### 5.4 写入事务

Workflow 中的每一步使用以下顺序：

1. 创建或锁定 `ModelRun`，状态设为 `RUNNING`。
2. 查询并登记输入 Artifact。
3. 调用 Adapter。
4. 将结果写到临时文件。
5. 计算 SHA-256、文件大小和记录数。
6. 原子重命名为正式文件。
7. 写伴随 `.manifest.json`。
8. 创建 Artifact 数据库记录。
9. 创建 `model_run_outputs` 关系。
10. 将 ModelRun 标记为 `SUCCEEDED` 并提交事务。

文件写入成功但数据库提交失败时，将文件移动到隔离目录，由维护脚本清理或恢复索引；不得静默留下孤儿文件。

### 5.5 Alembic 实施

1. 为当前全部 ORM 模型生成初始 Migration。
2. 人工检查外键、索引、唯一约束、升级和回滚逻辑。
3. 空数据库执行 `alembic upgrade head`。
4. 执行 `alembic downgrade base` 后再次升级。
5. CI 比较 ORM metadata 与 Migration head，禁止漂移。
6. 正式启动只运行 Migration，不调用 `Base.metadata.create_all()`。

建议索引：

```text
tasks(video_id, created_at)
tasks(status, created_at)
model_runs(task_id, model_name, status)
model_runs(cache_key, status)
artifacts(video_id, artifact_type, created_at)
model_run_inputs(run_id, input_role)
model_run_outputs(run_id, output_role)
```

开发默认可继续使用 SQLite；PostgreSQL 是集成测试和 Production 的标准数据库。Docker Compose 中的弱密码只能用于本地，并通过 `.env` 注入，不得写死。

数据库驱动必须按实际执行方式验证：

- 异步 FastAPI Session 使用 `postgresql+asyncpg://`，镜像必须安装 `asyncpg`；
- 同步 Workflow/Repository 使用 `postgresql+psycopg2://`，运行环境必须安装 `psycopg2` 或明确改为受支持的 psycopg 3 同步驱动；
- CI 启动 PostgreSQL 后应分别执行异步和同步 `SELECT 1`，避免只验证其中一条连接链路；
- 当前 Docker 示例中的 `POSTGRES_USER=postgres`、`POSTGRES_PASSWORD=postgres` 只能作为本地临时配置，必须改为从 `.env` 或 Secret 注入；Production 启动校验应拒绝 `postgres/postgres` 等弱凭据。

---

## 6. Artifact 与文件布局

### 6.1 统一路径

```text
{storage_root}/
└── projects/{project_id}/
    └── videos/{video_id}/
        ├── source/
        │   └── original.{ext}
        └── tasks/{task_id}/
            ├── ffmpeg/{version}/
            │   ├── normalized.mp4
            │   ├── audio.wav
            │   └── metadata.json
            ├── omnishotcut/{version}/
            │   └── shots.json
            ├── doubao_asr/{version}/
            │   ├── raw_response.json
            │   └── subtitles.json
            ├── scene_boundary/{version}/
            │   └── candidates.json
            ├── scene_score/{version}/
            │   └── scene_scores.json
            └── final/{version}/
                └── final_result.json
```

对应 URI：

```text
storage://projects/{project_id}/videos/{video_id}/tasks/{task_id}/...
```

源视频只保存一份。Task 通过 `video.original` Artifact 引用源视频，禁止再次复制为 `tasks/{task_id}/input/original.mp4`。

### 6.2 StorageService 接口

```python
class StorageService:
    def build_key(self, context, artifact_type, filename) -> str: ...
    def resolve_local_path(self, uri: str) -> Path: ...
    def put_stream(self, key: str, stream, limits) -> StoredObject: ...
    def write_artifact_atomic(self, key: str, data) -> StoredObject: ...
    def open(self, uri: str): ...
    def exists(self, uri: str) -> bool: ...
    def create_download_url(self, artifact_id: str, expires_s: int) -> str: ...
    def create_provider_url(self, artifact_id: str, expires_s: int) -> str: ...
```

业务代码不得直接调用 `Path(STORAGE_ROOT) / ...`。`core/task_storage.py` 的功能应迁移进统一 StorageService，随后删除重复路径实现。

### 6.3 路径安全

所有 key 和 URI 必须满足：

- 拒绝绝对路径、盘符、UNC 路径和空字节；
- 拒绝 `.`、`..` 路径段；
- ID 只允许 UUID 格式；
- 文件名由服务端生成，不信任上传文件名；
- 使用 `Path.resolve()` 后通过 `Path.is_relative_to(storage_root)` 校验；
- 禁止用字符串 `startswith()` 判断目录包含关系；
- Windows 路径比较应处理大小写和路径分隔符。

### 6.4 上传逻辑

上传过程改为固定大小分块：

```text
UploadFile
→ 校验声明大小
→ 逐块写入临时文件
→ 同时计算 SHA-256
→ FFprobe 校验真实容器/编码
→ 原子重命名
→ 写 Manifest 和 DB Artifact
```

不得使用无参数 `await file.read()` 将整部电影读入内存。应设置：

- 单文件大小上限；
- 允许的容器和 MIME 白名单；
- 上传超时；
- 磁盘剩余空间阈值；
- 重复文件 SHA-256 检测；
- 临时文件清理策略。

原始扩展名根据检测结果确定，禁止把 MKV 内容简单命名为 `.mp4`。

---

## 7. 公网文件访问与豆包 ASR

### 7.1 禁止公开整个 Storage

移除：

```python
app.mount("/files", StaticFiles(directory=STORAGE_ROOT))
```

替换为 Artifact 下载端点：

```text
GET /api/v1/artifacts/{artifact_id}/content?token=...
```

Token 至少绑定：

- `artifact_id`
- 用途：用户下载或模型拉取
- 过期时间
- 可选的最大访问次数
- HMAC 签名

生产环境优先使用对象存储预签名 URL。本地 ngrok 只用于开发，不得暴露 PostgreSQL、Redis、调试文档或完整 Storage。

原实现中由 Adapter 读取 `PUBLIC_BASE_URL` 并拼接 `PUBLIC_BASE_URL/files/...` 的逻辑必须删除。`PUBLIC_BASE_URL` 如在本地开发中仍需保留，只能由 StorageService 或签名下载服务使用，Adapter 只能接收已经生成的完整临时 URL。

EEG 原始数据、清洗数据和指标 Artifact 默认均为私有数据，禁止通过 StaticFiles、ngrok 公共目录或可猜测 URL 暴露。只有通过项目权限校验并签发短期 Token 后才允许下载；提供给模型时也必须使用用途受限、可过期的 URL。

### 7.2 豆包 Adapter 输入

Workflow/StorageService 层负责：

```text
查询 audio.normalized Artifact
→ StorageService.create_provider_url()
→ 构造标准 ModelInput
→ DoubaoASRAdapter.predict()
```

Adapter 输入：

```json
{
  "schema_version": "1.0",
  "task_id": "...",
  "video_id": "...",
  "model": {"name": "doubao_asr", "version": "..."},
  "input": {
    "audio_artifact_id": "...",
    "audio_url": "https://..."
  },
  "parameters": {"language": "zh-CN"}
}
```

Adapter 不再：

- 调用 FFmpeg；
- 解析 `storage://`；
- 读取 `STORAGE_ROOT`；
- 拼接 `/files/`；
- 读取或写入 PostgreSQL。

豆包外部请求 ID 使用 `provider_request_id`，写入结构化日志和 ModelRun metadata，避免和平台 `task_id` 混淆。

---

## 8. Python Workflow 与进程内执行方案

### 8.1 执行边界

本项目当前不引入 Celery、Redis、独立 Worker 或 Queue。FastAPI 创建 Task 后，由 Python WorkflowService/Executor 直接调用各 Adapter。

路由层只负责参数解析和调用 Service，不应直接拼接完整模型流程。实际步骤集中在 `core/orchestration/` 或等价的 Workflow 模块中，以便测试、复用和未来替换执行器。

建议保留两种明确执行模式：

- `inline`：请求等待 Workflow 完成后返回，适合短任务、调试和测试。
- `local_background`：返回 `task_id` 后在受控线程池或进程池中执行，适合当前本地 MVP。

`local_background` 必须明确接受以下限制：API 进程退出时运行中的任务可能中断，不能提供 Celery 式持久队列和跨机器恢复保证。Task 启动时应把 Executor 标识和运行状态写入 PostgreSQL；应用启动后将遗留的 `RUNNING` Task 标记为 `INTERRUPTED` 或按幂等步骤重新执行，不能长期保持虚假运行状态。

### 8.2 Workflow 调用参数

Workflow 步骤之间只传：

```text
task_id
video_id
run_id
artifact_id
storage URI
小型 JSON 参数
```

禁止在步骤之间复制或传递视频字节、音频字节、NumPy 大数组或 Tensor。大型数据必须先写入 Artifact，再传 URI 或 ID。

### 8.3 Workflow 顺序

```text
normalize_video
   ├── detect_shots
   ├── transcribe
   └── extract_audio_features

detect_shots → extract_visual_features

shots + subtitles + features
→ build_scene_features
→ detect_scene_boundaries
→ merge_shots_to_scenes
→ calculate_scene_score
→ assemble_final_result
```

WorkflowService 按上述依赖顺序调用 Python 函数和 Adapter。每个步骤根据输入 Artifact 的 SHA-256、模型版本、参数和 Schema 版本生成 Cache Key。只有 Manifest、数据库记录和实际文件全部一致时才能复用缓存。

### 8.4 失败处理与幂等

- 网络超时、对象存储临时失败：由 Workflow 执行有限次数指数退避重试。
- 视频损坏、Schema 错误、权重不兼容、CUDA 环境错误：不可自动重试。
- 同一 Cache Key 同时只能有一个有效执行，本地 MVP 通过 PostgreSQL 唯一约束和行锁控制。
- 重试创建新的 `run_id`，不能覆盖旧 Artifact。

### 8.5 与 AGENTS.md 的规则同步

当前 `AGENTS.md` 仍把 Celery 规定为 MVP 硬性要求。采用本节方案前，必须单独修订 `AGENTS.md`，把执行规则改为“当前阶段使用 FastAPI + Python Workflow 直接调用 Adapter”，否则本方案与项目架构宪法仍然冲突。

建议在 `AGENTS.md` 中同时记录进程内执行的适用边界和已知限制；以后若决定引入 Celery，应作为新的架构变更处理，而不是本次修复的组成部分。

---

## 9. 评分与 Schema 清理

### 9.1 删除禁止字段

全仓移除：

```text
action_score
plot_score
action_evidence
plot_evidence
plot_scores
plot_only
plot_weight
plot_change
```

删除或重构：

- `models/llm_plot/adapter.py` 的评分输出；
- Workflow 的 `_score_plot()`；
- 前端 `plot_only` 和剧情权重；
- `plot_scores.json` Artifact；
- 相关 API 参数、测试、README 和示例。

### 9.2 合法替代

剧情/LLM 模型可以输出语义观察结果，但不能输出最终评分维度。观察结果必须转换为允许的 Evidence：

```text
visual_continuity
character_continuity
location_continuity
subtitle_continuity
audio_continuity
temporal_gap_ms
```

所有连续性、置信度和 `scene_score` 均在 `[0, 1]`。最终切点由：

```text
候选边界 + 合法 Evidence + scene_score + 选择算法
```

共同决定，模型不得直接决定最终切点。

---

## 10. 状态、错误与日志

统一状态：

```text
PENDING → QUEUED → RUNNING → SUCCEEDED
                         ├→ RETRYING
                         ├→ FAILED
                         └→ CANCELLED
```

Task 进度只由 Workflow 根据已完成阶段计算，Adapter 不自行写任意百分比。

每条 Workflow/Adapter 日志至少包含：

```text
timestamp
level
task_id
video_id
run_id
model
event
```

失败日志额外包含：

```text
error_code
retryable
provider_request_id（如有）
```

禁止在核心流程使用 `print()`；统一使用 structlog。

---

## 11. 分阶段实施

### 阶段 A：数据库与身份修复

1. 统一 UUID 长度和生成函数。
2. 修改 `TaskService`，复用现有 `video_id`。
3. 增加 `projects`、`workflow_runs`、输入输出关系表。
4. 修复 `ModelRun → Artifact` 写入顺序。
5. 创建初始 Alembic Migration。
6. 增加 PostgreSQL 集成测试。

验收：新建空 PostgreSQL 后，Migration 可以升级、回滚、再次升级；上传和创建 Task 后只有一个 Video 记录。

### 阶段 B：Storage 与文件安全

1. 建立统一 StorageService。
2. 迁移到包含 project/video/task/model/version 的路径。
3. 实现流式上传、哈希、FFprobe 和原子写入。
4. 修复路径穿越检查。
5. 移除重复源视频复制。
6. 移除全目录 StaticFiles，增加授权下载端点。

验收：大文件上传内存保持稳定；构造 `../`、绝对路径、UNC 路径均被拒绝；未授权请求不能读取 Artifact。

### 阶段 C：Workflow 整理

1. 建立 `core/orchestration/`。
2. 把路由中的流程控制集中到 WorkflowService/Executor。
3. 配置受控的线程池或进程池，禁止每个请求无上限创建线程。
4. 实现状态更新、中断识别、有限重试、幂等和缓存复用。
5. 为 `inline` 和 `local_background` 两种模式分别编写测试。

验收：Workflow 可直接调用 Adapter；并发数有上限；API 重启后遗留 Task 能标记为 `INTERRUPTED` 或安全重跑；步骤之间不传大型数据。

### 阶段 D：Adapter 解耦

1. 豆包 Adapter 只接收公共 `audio_url`。
2. FFmpeg 音频提取迁移至 normalize Workflow 步骤。
3. Storage URI 和公网 URL 生成迁移至 StorageService。
4. 所有 Adapter 按统一 Contract 返回 Schema 化结果。
5. 模型或 API Client 在应用/Executor 生命周期内安全复用。

验收：Adapter 单元测试不需要数据库、FastAPI 或固定磁盘目录。

### 阶段 E：评分清理

1. 删除全部禁止字段及 UI 参数。
2. 将语义信息映射为合法 Evidence。
3. 所有数值强制验证为 `[0, 1]`。
4. 最终结果只输出 Scene 和 `scene_score`。

验收：全仓搜索不存在禁止字段；Schema 对非法字段设置拒绝策略；回归结果只包含合法 Evidence。

### 阶段 F：端到端验证

1. 执行 Ruff、MyPy、Pytest、Alembic check。
2. 运行 FastAPI → Workflow → Adapter → Artifact → PostgreSQL → 查询 API 集成测试。
3. 使用固定短视频验证时间戳、缓存、失败重试和结果复现。
4. 使用长视频验证磁盘、内存、超时和豆包文件拉取。

---

## 12. 测试矩阵

| 测试类型 | 必测内容 |
|---|---|
| Schema | 禁止字段、毫秒整数、半开区间、分数范围 |
| ID | 一个 Video 多个 Task、Task 与 ModelRun 关联 |
| Migration | 空库升级、回滚、metadata 漂移 |
| Repository | 外键、事务回滚、并发 Cache Key |
| Storage | 路径穿越、原子写入、哈希、孤儿文件 |
| Upload | 大文件分块、伪扩展名、损坏视频、磁盘不足 |
| Adapter | 输入 Contract、错误映射、外部请求 ID |
| Workflow | inline/background 模式、并发限制、中断识别、重试和幂等 |
| API | 202 创建、状态查询、404、权限和签名过期 |
| E2E | FastAPI + PostgreSQL + Workflow + 模型 Stub 完整链路 |

必须新增的关键回归用例：

1. 上传返回的 `video_id` 与 Task 中的 `video_id` 完全一致。
2. 不存在 ModelRun 时无法创建 Artifact；正常 Workflow 流程可以创建。
3. 同一视频启动两个 Task 时，Artifact 不串任务。
4. 同一模型不同版本不会覆盖 Artifact。
5. `../secret`、绝对 Windows 路径和编码后的穿越路径全部返回拒绝。
6. API 进程重启后，遗留的 `RUNNING` Task 会被识别为 `INTERRUPTED`，并能按幂等规则安全重跑。
7. 最终 JSON 不包含任何禁止字段。

---

## 13. 兼容与迁移策略

现有 `data/tasks/{task_id}` 文件不能直接假定有效，应编写一次性迁移工具：

1. 读取数据库 Task、Video、ModelRun 和 Artifact 记录。
2. 校验旧文件是否存在并计算 SHA-256。
3. 能确定 project/video/model/version 的文件迁移到新路径。
4. 缺少 ModelRun 的旧 Artifact 标记为 `legacy_unverified`，不得作为正式缓存复用。
5. 写新 Manifest 和数据库 URI。
6. 保留迁移日志和旧路径映射。
7. 完整验收后再归档旧目录，不直接删除。

API 兼容期内：

- 旧任务查询可以继续读取；
- 新 Task 只能写新布局；
- 禁止新旧写入逻辑同时写同一 Artifact；
- 兼容代码应设置明确删除版本。

---

## 14. 完成定义

只有同时满足以下条件，改造才算完成：

- [ ] 上传与分析全过程只使用一个稳定 `video_id`。
- [ ] FastAPI 通过统一 Python Workflow/Executor 调用 Adapter，路由层不堆叠模型流程。
- [ ] 进程内执行并发受控，且进程中断后的 Task 状态可识别、可安全重跑。
- [ ] 所有 Artifact 都关联有效 ModelRun 和 Manifest。
- [ ] Alembic 可以从空 PostgreSQL 创建全部表并可回滚。
- [ ] 文件路径包含 project/video/task/model/version。
- [ ] Adapter 不访问数据库、Storage Root 或 FastAPI 文件路由。
- [ ] 不公开整个 Storage，所有下载都经过授权或签名。
- [ ] 上传采用流式写入并验证真实媒体格式。
- [ ] 路径穿越测试全部通过。
- [ ] 全仓不存在禁止的评分字段。
- [ ] 最终结果只包含 Scene、合法 Evidence 和 `scene_score`。
- [ ] `scripts/dev/check.py` 全部通过。
- [ ] PostgreSQL 端到端集成测试通过。

---

## 15. 推荐实施顺序总结

```text
修复 video_id
→ 建立 Migration 和正确 ModelRun/Artifact 事务
→ 统一安全 StorageService
→ 整理 Python Workflow/Executor
→ Adapter 解耦
→ 删除禁止评分字段
→ 迁移旧数据
→ 完整 E2E 与安全验收
```

数据库身份和 Artifact 外键应最先修复，因为后续的缓存、Workflow、文件迁移和结果查询都依赖这两部分具有可靠语义。
