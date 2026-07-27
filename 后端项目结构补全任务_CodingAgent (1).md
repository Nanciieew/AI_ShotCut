# 后端项目结构补全任务

你正在维护一个多模型视频分析后端项目。当前项目已经具备以下内容：

- 完整目录结构；
- `.gitignore`、`.env.example`、`pyproject.toml`、`requirements.txt`；
- `development.yaml`、`production.yaml`、`models.yaml`、`celery.yaml`；
- Docker Compose：API、Redis、Celery Worker、PostgreSQL；
- Core 层：数据库 ORM、Storage、Exceptions；
- 模型适配层：`BaseModelAdapter` 和模型目录；
- Celery Worker 与多个 Task 模块；
- Pydantic Schema；
- FastAPI 应用与 `/health`、videos、tasks、results 路由；
- 环境检测和数据库初始化脚本；
- `CLAUDE.md`、`IMPROVEMENTS.md`、`IO_Rule.md`、`项目图纸.md`、`README.md`。

本次任务不是接入具体模型，而是检查并补全后端基础结构，使项目能够稳定支持后续 OmniShotCut、Whisper、Scene Boundary 等模型的独立接入和异步运行。

---

# 一、执行原则

1. 先检查现有代码，不要重复创建已经存在的功能。
2. 不要删除或大规模重写当前目录结构。
3. 优先增量修改。
4. 所有配置必须兼容本地开发和 Docker Compose。
5. 所有新增模块必须有清晰注释和类型标注。
6. 不接入真实模型权重。
7. 不将大型文件、模型权重或测试电影提交到 Git。
8. 不在 API Route 中运行耗时模型任务。
9. 所有长任务继续通过 Celery 执行。
10. 不引入 `action_score`、`plot_score` 或相关概念。
11. 最终评分体系只允许存在 `scene_score`。
12. 每完成一个模块，都要补充相应测试或验证脚本。

---

# 二、数据库迁移：接入 Alembic

当前已有 ORM 表和数据库初始化脚本，但需要增加正式的数据库迁移机制。

请完成：

```text
alembic/
├── versions/
├── env.py
├── README
└── script.py.mako

alembic.ini
```

要求：

1. Alembic 使用项目现有 SQLAlchemy Base 和数据库配置。
2. 数据库 URL 从环境变量或统一 Settings 中读取。
3. 支持 PostgreSQL。
4. 保留 SQLite 本地测试兼容性。
5. 生成初始迁移文件，覆盖当前 ORM 表。
6. 不依赖应用启动时的 `Base.metadata.create_all()` 作为正式迁移方案。
7. `initialize_database.py` 可以保留，但应明确它只用于开发或初始化辅助。
8. 在 README 中补充以下命令：

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
alembic current
alembic history
```

验收标准：

- 空数据库执行 `alembic upgrade head` 后可以创建所有表；
- 再次执行不会报错；
- API 和 Worker 可以连接迁移后的数据库。

---

# 三、依赖管理调整

检查当前：

```text
pyproject.toml
requirements.txt
```

避免只使用未固定版本的依赖。

将依赖整理为：

```text
requirements/
├── base.txt
├── api.txt
├── worker.txt
├── dev.txt
└── models/
    ├── omnishotcut.txt
    ├── whisper.txt
    └── scene_boundary.txt
```

要求：

1. 所有核心依赖固定明确版本。
2. `requirements.txt` 可以作为兼容入口，但应引用对应文件。
3. `pyproject.toml` 中配置开发工具。
4. 不随意升级现有依赖版本。
5. 若发现版本冲突，记录到 `IMPROVEMENTS.md`。
6. 不要立即将所有模型依赖加入 API 环境。

建议分类：

- `base.txt`：Pydantic、SQLAlchemy、Redis、日志、YAML 等公共依赖；
- `api.txt`：FastAPI、Uvicorn、python-multipart；
- `worker.txt`：Celery、通用 Worker 工具；
- `dev.txt`：Pytest、Ruff、MyPy、Coverage、Pre-commit；
- `requirements/models/`：各模型专属依赖。

---

# 四、代码质量工具

增加：

```text
.pre-commit-config.yaml
```

至少启用：

- Ruff lint；
- Ruff format；
- trailing whitespace；
- end-of-file fixer；
- YAML 检查；
- 大文件检查；
- 私钥检查。

在 `pyproject.toml` 中配置：

```text
[tool.ruff]
[tool.ruff.lint]
[tool.ruff.format]
[tool.mypy]
[tool.pytest.ini_options]
[tool.coverage.run]
[tool.coverage.report]
```

项目至少支持：

```bash
ruff check .
ruff format --check .
mypy .
pytest
pytest --cov
pre-commit run --all-files
```

要求：

1. 不为通过检查而删除有效类型约束。
2. `third_party/` 和模型缓存目录排除在 lint 范围之外。
3. 不对未来下载的第三方源码强制使用本项目格式化规则。

---

# 五、统一开发命令

考虑项目运行环境包含 Windows，优先增加跨平台 Python 脚本，必要时同时提供 PowerShell。

建议增加：

```text
scripts/dev/
├── start.py
├── stop.py
├── test.py
├── lint.py
├── migrate.py
└── check.py
```

统一支持：

- 启动 Docker Compose；
- 停止 Docker Compose；
- 执行数据库迁移；
- 运行测试；
- 运行 lint；
- 运行类型检查；
- 检查环境；
- 查看 Celery Worker 状态。

不要只依赖 Linux `Makefile`。

---

# 六、CI 配置

增加：

```text
.github/
└── workflows/
    └── ci.yml
```

CI 在每次 push 和 pull request 时执行：

1. 安装基础依赖；
2. Ruff lint；
3. Ruff format check；
4. MyPy；
5. Pytest；
6. Schema 单元测试；
7. Docker Compose 配置检查；
8. Alembic 迁移检查。

普通 CI 不下载模型权重，也不运行 GPU 推理。

验收标准：

- 不需要模型权重即可通过基础 CI；
- CI 不依赖开发者本地 `.env`；
- 使用测试环境变量。

---

# 七、Docker Compose 健康检查和启动顺序

检查当前四个服务：

```text
api
redis
worker
postgres
```

为它们补充健康检查：

- PostgreSQL：`pg_isready`
- Redis：`redis-cli ping`
- API：`GET /health/live`
- Worker：`celery inspect ping`

增加一次性迁移服务：

```text
migrate
```

建议启动顺序：

```text
postgres healthy
redis healthy
    ↓
migrate completed successfully
    ↓
api
worker
```

要求：

1. 不只使用简单 `depends_on`。
2. API 和 Worker 不应在数据库未就绪时立即失败退出。
3. 增加合理的 restart policy。
4. 数据目录和模型目录使用持久化 Volume 或绑定挂载。

---

# 八、健康检查分层

将当前 `/health` 调整或扩展为：

```http
GET /health/live
GET /health/ready
```

`/health/live` 只检查 API 进程是否存活。

`/health/ready` 检查：

- PostgreSQL；
- Redis；
- Storage 可写；
- FFmpeg 可执行；
- 必要配置是否加载；
- Celery Broker 是否可访问。

如果关键依赖异常：

- 返回非 200 状态；
- 明确指出失败项目；
- 不返回密码、连接字符串或密钥。

预留：

```http
GET /api/v1/models/{model_name}/health
```

当前不要求真实加载模型。

---

# 九、Celery Queue 路由

为现有 Task 模块定义独立 Queue：

```text
video
shot
subtitle
feature
scene
final
maintenance
```

建议路由：

```python
task_routes = {
    "workers.tasks.video_tasks.*": {"queue": "video"},
    "workers.tasks.shot_tasks.*": {"queue": "shot"},
    "workers.tasks.subtitle_tasks.*": {"queue": "subtitle"},
    "workers.tasks.feature_tasks.*": {"queue": "feature"},
    "workers.tasks.scene_tasks.*": {"queue": "scene"},
    "workers.tasks.final_tasks.*": {"queue": "final"},
    "workers.tasks.maintenance_tasks.*": {"queue": "maintenance"},
}
```

补充推荐配置：

```python
task_track_started = True
task_acks_late = True
worker_prefetch_multiplier = 1
task_reject_on_worker_lost = True
broker_connection_retry_on_startup = True
```

要求：

1. 不在 Redis 中传输视频、Tensor 或大型数组。
2. Celery Task 只传递 ID、URI 和小型 JSON。
3. Result Backend 不作为长期 Artifact 存储。
4. Task 必须记录数据库状态。
5. Task 必须使用明确名称。
6. Task 必须配置有限重试。
7. 不对所有异常自动重试。

---

# 十、CPU 与 GPU 任务区分

CPU 任务：

- 视频元数据读取；
- FFmpeg 转码；
- 文件哈希；
- JSON 转换；
- Artifact Manifest；
- 数据库更新；
- 最终结果组装。

GPU 任务：

- OmniShotCut；
- Whisper；
- 视觉编码器；
- 音频模型；
- Scene Boundary 模型。

建议配置：

```yaml
workers:
  cpu:
    queues:
      - video
      - final
      - maintenance
  gpu:
    queues:
      - shot
      - subtitle
      - feature
      - scene
    concurrency: 1
```

MVP 可以先共享 Worker，但必须预留未来拆分能力。

---

# 十一、Artifact Manifest

在现有 Artifact 数据库记录之外，增加文件级 Manifest。

建议目录：

```text
core/artifacts/
├── manifest.py
├── writer.py
├── validator.py
└── hashing.py
```

每个主要 Artifact 支持：

```text
shots.json
shots.manifest.json
```

Manifest 至少包含：

```json
{
  "artifact_type": "shot_boundaries",
  "schema_version": "1.0",
  "artifact_id": "artifact_001",
  "video_id": "video_001",
  "run_id": "run_001",
  "producer": {
    "model_name": "omnishotcut",
    "model_version": "1.0.0",
    "code_revision": "git_commit",
    "weight_revision": "weight_revision"
  },
  "input": {
    "video_sha256": "sha256"
  },
  "output": {
    "file": "shots.json",
    "sha256": "sha256",
    "record_count": 100
  },
  "parameters": {},
  "created_at": "ISO-8601 timestamp"
}
```

要求：

1. Manifest 使用 Pydantic Schema。
2. Artifact 先写临时文件，再原子重命名。
3. 数据库记录与 Manifest 中的 ID 保持一致。
4. SHA256 基于最终文件内容。

---

# 十二、Schema 版本管理

明确区分：

- 模型版本；
- 模型权重版本；
- 代码版本；
- Schema 版本。

当前建议：

```text
schema_version = "1.0"
```

规则：

1. 已写入正式 Artifact 后，不得随意修改已有字段语义。
2. 新增可选字段可作为小版本变更。
3. 删除字段或改变含义属于不兼容升级。
4. Schema 版本必须写入 Task 输入、Model Run、Artifact、Manifest 和最终结果。

可以预留：

```text
schemas/
├── v1/
└── compatibility/
```

---

# 十三、测试 Fixtures

增加：

```text
tests/
├── fixtures/
│   ├── videos/
│   ├── audio/
│   ├── expected/
│   ├── raw_outputs/
│   └── schemas/
├── unit/
├── integration/
└── conftest.py
```

准备无版权短测试视频：

```text
no_cut.mp4
hard_cut.mp4
multiple_cuts.mp4
```

增加生成脚本：

```text
scripts/generate_test_fixtures.py
```

不要将真实电影片段提交到 Git。

---

# 十四、模型注册表和 License

增加或补全：

```text
models/registry.yaml
```

结构：

```yaml
models:
  omnishotcut:
    task: shot_boundary_detection
    repository: ""
    revision: ""
    code_license: unknown
    weights_license: unknown
    dataset_license: unknown
    commercial_use: unknown
    adapter: models.omnishotcut.adapter.OmniShotCutAdapter
    enabled: false

  whisper:
    task: speech_to_text
    repository: ""
    revision: ""
    code_license: unknown
    weights_license: unknown
    commercial_use: unknown
    adapter: models.whisper.adapter.WhisperAdapter
    enabled: false

  scene_boundary:
    task: scene_boundary_detection
    repository: ""
    revision: ""
    code_license: unknown
    weights_license: unknown
    commercial_use: unknown
    adapter: models.scene_boundary.adapter.SceneBoundaryAdapter
    enabled: false
```

规则：

1. 未安装模型时保持 `enabled: false`。
2. 未核验 License 时不得标记可商用。
3. 不猜测 License。
4. 接入模型时记录固定 Commit。
5. 权重来源与代码来源分别记录。
6. Registry 由统一 Loader 读取。

---

# 十五、可观测性与链路 ID

统一定义：

```text
request_id
pipeline_task_id
celery_task_id
video_id
run_id
artifact_id
```

建议目录：

```text
core/logging/
├── config.py
├── context.py
└── middleware.py
```

要求：

1. API 日志与 Celery 日志使用统一字段。
2. 禁止日志输出密钥。
3. 错误日志包含 Error Code。
4. 模型任务记录耗时、设备和重试次数。

---

# 十六、临时文件与清理任务

增加：

```text
data/tmp/
workers/tasks/maintenance_tasks.py
```

至少提供：

```text
cleanup_expired_temp_files
cleanup_failed_uploads
cleanup_old_task_results
```

要求：

1. 清理任务不能删除正式 Artifact。
2. 清理范围限制在允许目录中。
3. 支持 dry-run。
4. 输出清理数量和失败列表。
5. 预留 Celery Beat 调度。
6. MVP 可以暂不开启 Beat。

---

# 十七、Storage 安全检查

检查：

```text
core/storage/local.py
core/storage/s3.py
```

Local Storage 必须：

1. 防止路径穿越；
2. 所有文件限制在 `STORAGE_ROOT`；
3. 支持原子写入；
4. 支持 SHA256；
5. 支持文件存在检查；
6. 支持统一 URI；
7. 支持 URI 转本地路径；
8. 不向 API 用户暴露本机绝对路径。

S3 Storage 可以暂未实现，但必须明确报错，不能静默返回假结果。

---

# 十八、配置校验

建立统一 Settings 类，启动时校验：

- DATABASE_URL；
- REDIS_URL；
- CELERY_BROKER_URL；
- CELERY_RESULT_BACKEND；
- STORAGE_ROOT；
- MODEL_STORE_ROOT；
- 环境名称；
- 日志级别；
- FFmpeg 路径。

要求：

1. 缺少关键配置时快速失败。
2. 错误信息说明缺少哪个配置。
3. 不打印敏感值。
4. Development 与 Production 配置明确区分。
5. Production 不允许使用弱默认密码。
6. `.env.example` 与 Settings 字段保持同步。

---

# 十九、文档更新

完成后更新：

## `README.md`

加入：

- 本地启动；
- Docker Compose 启动；
- 数据库迁移；
- 测试；
- Lint；
- Worker Queue；
- 健康检查；
- 项目目录说明。

## `CLAUDE.md`

加入：

- 不直接在 API 中运行模型；
- 模型必须通过 Adapter；
- 长任务必须走 Celery；
- 大文件只通过 URI 传输；
- 所有时间统一为整数毫秒；
- 只允许 `scene_score`；
- 禁止 `action_score` 和 `plot_score`；
- 修改 ORM 后必须创建 Alembic Migration；
- 新增模型前必须登记 Registry 和 License。

## `IMPROVEMENTS.md`

记录：

- 暂未完成的基础设施；
- 依赖冲突风险；
- Docker Worker 拆分计划；
- 监控与指标计划；
- 对象存储切换计划；
- GPU Worker 调度计划。

## `项目图纸.md`

更新：

```text
API
→ Redis
→ Celery Queue
→ Worker
→ Adapter
→ Artifact Storage
→ Database
```

并标记 CPU/GPU Worker 的未来拆分路径。

---

# 二十、测试与验收

至少运行：

```bash
ruff check .
ruff format --check .
mypy .
pytest
docker compose config
alembic upgrade head
```

完整基础验证：

```text
1. 启动 PostgreSQL 和 Redis
2. 执行数据库迁移
3. 启动 API
4. 启动 Celery Worker
5. 请求 /health/live
6. 请求 /health/ready
7. 提交一个测试 Celery Task
8. 查询 Task 状态
9. 验证数据库 Model Run 与 Artifact 记录
10. 执行临时文件 dry-run 清理
```

最终输出实施报告，包括：

1. 新增文件；
2. 修改文件；
3. 数据库迁移内容；
4. 新增配置项；
5. 新增环境变量；
6. 新增测试；
7. 实际运行的验证命令；
8. 验证结果；
9. 尚未完成事项；
10. 发现的风险。

---

# 二十一、禁止事项

本次任务禁止：

1. 接入真实 OmniShotCut 推理。
2. 下载大型模型权重。
3. 大规模重写现有项目。
4. 删除已有 ORM 表。
5. 随意修改现有 Schema 字段含义。
6. 将视频或 Tensor 存入 Redis。
7. 将模型权重提交到 Git。
8. 使用开发者本机绝对路径。
9. 将数据库密码写入代码。
10. 让 API 等待长任务执行完毕。
11. 将 Celery Result Backend 当长期存储。
12. 创建 `action_score`。
13. 创建 `plot_score`。
14. 将第三方模型源码直接复制到业务模块。
15. 未检查现有实现就重复创建相同模块。

---

# 二十二、完成标准

只有满足以下条件，任务才算完成：

```text
□ Alembic 可以正常迁移数据库
□ Docker Compose 有健康检查
□ API 有 live 和 ready 健康检查
□ Celery Queue 路由明确
□ CPU/GPU Task 分类已预留
□ 依赖已分层并固定版本
□ Ruff、MyPy、Pytest 可以运行
□ 基础 CI 已配置
□ Artifact Manifest 已定义
□ Schema 版本规则已明确
□ 测试 Fixture 生成方式已提供
□ 模型 Registry 已建立
□ License 状态不会被猜测
□ 日志支持完整链路 ID
□ 临时文件清理 Task 已建立
□ 配置启动时会被校验
□ README 和 Agent 文档已同步
□ 不引入任何 action_score 或 plot_score
□ 所有新增测试通过
```

请先扫描现有项目并输出一份简短的“现状检查结果”，列出：

- 已完成；
- 部分完成；
- 缺失；
- 与本规范冲突。

然后再开始实施。不要在未检查现有代码前直接批量生成文件。
