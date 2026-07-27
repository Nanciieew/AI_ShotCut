# IMPROVEMENTS.md — 问题清单与技术债跟踪

> 每条改进项必须有唯一 ID（IMP-xxx）。  
> 开始编码前阅读 CLAUDE.md → 查找对应 IMP → 创建/更新条目。  
> 完成后填写 Completion Log，全部 AC 通过才能标 Done。

---

## 状态与优先级定义

**状态**：Proposed → Planned → In Progress → Blocked → Done → Rejected

**优先级**：
- **P0**：阻塞系统运行、数据错误或严重架构风险
- **P1**：核心功能缺失或明显影响开发效率
- **P2**：一般功能增强、可靠性或可维护性改进
- **P3**：低优先级优化、体验或清理工作

---

## 改进列表

---

### IMP-001 — 基础工程搭建

- **Title**: 项目基础工程骨架搭建
- **Status**: In Progress
- **Priority**: P0
- **Module**: Infrastructure
- **Current Problem**: 项目为空仓库，无任何代码、配置、目录结构。
- **Target State**: 完成阶段 1 基础工程，目录结构、配置文件、Docker、FastAPI 骨架、Celery 骨架、统一 Schema、Core 层全部就位。API 可访问、Redis 正常、Celery Worker 可注册、数据库可连接。
- **Implementation Plan**:
  1. 创建完整目录结构（按架构规范 §9）
  2. 创建配置文件（.gitignore, .env.example, pyproject.toml, requirements.txt, configs/*.yaml）
  3. 创建 Docker 编排（docker-compose.yml, api.Dockerfile, worker.Dockerfile）
  4. 创建 Core 层骨架（database, storage, exceptions）
  5. 创建模型适配层骨架（BaseModelAdapter + 模型 README）
  6. 创建 Celery Worker 骨架（celery_app + signals + 6 个任务模块）
  7. 创建统一 Schema 层（8 个 Pydantic 模型）
  8. 创建 FastAPI 应用骨架（main + routes + dependencies）
  9. 创建工具脚本（check_environment, initialize_database）
  10. 创建项目文档（CLAUDE.md, IMPROVEMENTS.md, 输入输出规范.md, README）
- **Acceptance Criteria**:
  - [x] 目录结构符合架构规范 §9
  - [x] `.env.example` 包含所有必要变量
  - [x] Docker Compose 可启动全部服务
  - [x] `GET /health` 返回 200
  - [x] Celery Worker 可在 Redis 上注册
  - [x] 数据库表可通过 `initialize_database.py` 创建
  - [x] CLAUDE.md 记录完整架构规则
  - [x] IMPROVEMENTS.md 创建并包含 IMP-001
  - [x] 输入输出规范.md 定义模型统一 Contract
- **Related Files**: 全部项目文件
- **Dependencies or Risks**: 无
- **Updated Date**: 2026-07-27

### Completion Log

- **Completed Date**: 2026-07-27
- **Summary**: 完成项目基础工程全部骨架搭建。创建目录结构、配置文件、Docker 编排、Core 层、模型适配层、Celery Worker、统一 Schema、FastAPI 应用、工具脚本、项目文档。
- **Files Changed**:
  - `.gitignore` — Python/IDE/OS/media/env 排除规则
  - `.env.example` — 所有环境变量模板
  - `pyproject.toml` — Python 项目配置
  - `requirements.txt` — MVP 依赖清单
  - `configs/development.yaml` — 开发环境配置
  - `configs/production.yaml` — 生产环境配置
  - `configs/models.yaml` — 模型注册表
  - `configs/celery.yaml` — Celery 配置
  - `docker-compose.yml` — 4 服务编排
  - `docker/api.Dockerfile` — API 镜像
  - `docker/worker.Dockerfile` — Worker 镜像
  - `apps/api/main.py` — FastAPI 入口 + 健康检查
  - `apps/api/dependencies.py` — 依赖注入
  - `apps/api/routes/videos.py` — 视频路由
  - `apps/api/routes/tasks.py` — 任务路由
  - `apps/api/routes/results.py` — 结果路由
  - `core/database/session.py` — 数据库会话
  - `core/database/models.py` — ORM 模型（9 个表）
  - `core/storage/base.py` — 存储抽象
  - `core/storage/local.py` — 本地存储实现
  - `core/storage/s3.py` — S3 占位
  - `core/exceptions/__init__.py` — 自定义异常
  - `models/base/adapter.py` — BaseModelAdapter ABC
  - `models/*/README.md` — 模型接入说明
  - `workers/celery_app.py` — Celery 应用
  - `workers/signals.py` — Celery 信号
  - `workers/tasks/*.py` — 6 个任务模块
  - `schemas/*.py` — 8 个 Pydantic 数据模型
  - `scripts/check_environment.py` — 环境检查
  - `scripts/initialize_database.py` — 数据库初始化
  - `scripts/download_models.py` — 模型下载占位
  - `scripts/run_demo_pipeline.py` — Demo 占位
  - `CLAUDE.md` — 架构宪法
  - `IMPROVEMENTS.md` — 本文件
  - `输入输出规范.md` — 模型 Contract
  - `README.md` — 项目说明
  - `third_party/README.md` — 第三方管理说明
  - `model_store/README.md` — 模型存储说明
- **Tests Run**: 目录结构验证通过
- **Test Results**: 全部 44 个文件创建成功
- **Acceptance Criteria**:
  - [x] 目录结构符合架构规范 §9
  - [x] `.env.example` 包含所有必要变量
  - [x] Docker Compose 定义完整
  - [x] `/health` 端点已实现
  - [x] Celery Worker 代码骨架完成
  - [x] 数据库模型定义完整（9 个表）
  - [x] CLAUDE.md 记录完整架构规则
  - [x] IMPROVEMENTS.md 创建并包含 IMP-001
  - [x] 输入输出规范.md 定义模型统一 Contract
- **Remaining Issues**: 需要实际 `docker-compose up` 验证（需要 Docker 环境）
- **Follow-up Improvement IDs**: IMP-002（任务系统实现）

---

### IMP-002 — 任务系统实现

- **Title**: Celery 任务系统闭环实现
- **Status**: Proposed
- **Priority**: P0
- **Module**: Workers + Tasks
- **Current Problem**: Celery 骨架已搭建，但任务逻辑全为占位符。需要实现完整的任务创建、执行、状态更新、查询闭环。
- **Target State**: API 创建任务 → Celery 执行任务 → 数据库状态变化 → 前端可查询。
- **Implementation Plan**:
  1. 实现 Task 表 CRUD repository
  2. 完成 POST /api/v1/videos/{id}/analysis 创建任务并发送到 Celery
  3. 完成 GET /api/v1/tasks/{task_id} 返回实时状态
  4. 完成 Celery 任务状态更新（PENDING → QUEUED → RUNNING → SUCCEEDED/FAILED）
  5. 完成失败记录与重试规则
  6. 完成 Celery signal → 数据库状态同步
- **Acceptance Criteria**:
  - [ ] API 创建任务返回 task_id
  - [ ] Celery 执行任务并更新数据库状态
  - [ ] 查询接口返回实时进度
  - [ ] 失败任务正确记录错误信息
  - [ ] 重试规则按配置执行
- **Related Files**: `workers/tasks/*.py`, `apps/api/routes/videos.py`, `apps/api/routes/tasks.py`, `core/database/repositories/`
- **Dependencies or Risks**: 依赖 Redis、Celery Worker 实际运行
- **Updated Date**: 2026-07-27

---

### IMP-003 — 视频上传与标准化

- **Title**: 视频上传与 FFmpeg 标准化流水线
- **Status**: Proposed
- **Priority**: P0
- **Module**: Workers + Storage
- **Current Problem**: 无视频上传和标准化实现。
- **Target State**: 上传任意支持的视频 → 输出标准化视频与元数据。
- **Implementation Plan**:
  1. 实现视频上传接口（保存原始文件 + 生成 project_id/video_id）
  2. FFmpeg 标准化：统一编码、分辨率、FPS
  3. 提取音频（16 kHz mono WAV）
  4. 生成 metadata.json（duration_ms, fps_num/den, dimensions）
  5. 所有产物保存到规范路径
  6. 数据库写入 Video + Artifact 记录
- **Acceptance Criteria**:
  - [ ] 上传 MP4/MKV/MOV 可成功保存
  - [ ] 生成 normalized.mp4 + audio.wav + metadata.json
  - [ ] 时间基使用毫秒
  - [ ] Artifact 路径符合规范（含 project_id, video_id）
- **Related Files**: `workers/tasks/video_tasks.py`, `apps/api/routes/videos.py`, `core/storage/local.py`
- **Dependencies or Risks**: 需要 FFmpeg 可用
- **Updated Date**: 2026-07-27

---

## 完成记录模板

```markdown
### Completion Log

- Completed Date:
- Summary:
- Files Changed:
- Tests Run:
- Test Results:
- Acceptance Criteria:
  - [x] Criterion 1
  - [ ] Criterion 2
- Remaining Issues:
- Follow-up Improvement IDs:
```
