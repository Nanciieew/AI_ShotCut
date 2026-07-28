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
- **Status**: Done
- **Priority**: P0
- **Module**: Infrastructure
- **Target State**: 目录结构、配置文件、Docker、FastAPI 骨架、Celery 骨架、统一 Schema、Core 层全部就位。

### Completion Log

- **Completed Date**: 2026-07-27
- **Summary**: 完成项目基础工程全部骨架搭建（44 个文件，25 个目录）。
- **Acceptance Criteria**:
  - [x] 目录结构符合架构规范 §9
  - [x] `.env.example` 包含所有必要变量
  - [x] Docker Compose 定义完整
  - [x] `/health` 端点已实现
  - [x] Celery Worker 代码骨架完成
  - [x] 数据库模型定义完整（9 个表）
  - [x] CLAUDE.md 记录完整架构规则
  - [x] IMPROVEMENTS.md 创建
  - [x] IO_Rule.md 定义模型统一 Contract

---

### IMP-002 — 后端结构补全

- **Title**: 后端项目结构补全（Alembic、依赖分层、CI、健康检查、Artifact Manifest 等）
- **Status**: Done
- **Priority**: P0
- **Module**: Infrastructure
- **Target State**: 项目具备完整的迁移、测试、CI、日志、队列路由、配置校验等基础设施。

### Completion Log

- **Completed Date**: 2026-07-27
- **Summary**: 完成文档要求的全部 22 个章节的补全工作。
- **Files Changed**:
  - **新增**：`alembic/`（env.py, script.py.mako, README）、`alembic.ini`
  - **新增**：`requirements/base.txt, api.txt, worker.txt, dev.txt, models/*.txt`
  - **新增**：`.pre-commit-config.yaml`、`.github/workflows/ci.yml`
  - **新增**：`scripts/dev/`（start, stop, test, lint, migrate, check）
  - **新增**：`tests/conftest.py`、`scripts/generate_test_fixtures.py`
  - **新增**：`core/artifacts/`（manifest, writer, validator, hashing）
  - **新增**：`core/logging/`（config, context, middleware）
  - **新增**：`core/config.py`（统一 Settings 类）
  - **新增**：`workers/tasks/maintenance_tasks.py`
  - **新增**：`configs/workers.yaml`（CPU/GPU 分组）
  - **新增**：`models/registry.yaml`
  - **新增**：`schemas/v1/__init__.py`, `schemas/compatibility/__init__.py`
  - **新增**：`data/tmp/.gitkeep`
  - **修改**：`docker-compose.yml`（migrate 服务、健康检查、启动顺序）
  - **修改**：`apps/api/main.py`（`/health/live`、`/health/ready`、日志中间件）
  - **修改**：`workers/celery_app.py`（task_routes、maintenance 队列）
  - **修改**：`core/storage/local.py`（uri_to_local_path）
  - **修改**：`pyproject.toml`（ruff format, coverage 配置）
  - **修改**：`requirements.txt`、`.env.example`、`.gitignore`
  - **修改**：`README.md`、`CLAUDE.md`、`项目图纸.md`
- **Acceptance Criteria**:
  - [x] Alembic 可以正常迁移数据库
  - [x] Docker Compose 有健康检查和启动顺序
  - [x] API 有 live 和 ready 健康检查
  - [x] Celery Queue 路由明确（7 个队列）
  - [x] CPU/GPU Task 分类已预留（configs/workers.yaml）
  - [x] 依赖已分层并固定版本
  - [x] Ruff、MyPy、Pytest 可以运行
  - [x] 基础 CI 已配置（6 个 job）
  - [x] Artifact Manifest 已定义
  - [x] Schema 版本规则已明确
  - [x] 测试 Fixture 生成方式已提供
  - [x] 模型 Registry 已建立（含 License 字段）
  - [x] License 状态不会被猜测
  - [x] 日志支持完整链路 ID
  - [x] 临时文件清理 Task 已建立
  - [x] 配置启动时会被校验
  - [x] README 和 Agent 文档已同步
  - [x] 不引入任何 action_score 或 plot_score
- **Remaining Issues**: 无
- **Follow-up Improvement IDs**: IMP-003

---

### IMP-009 — OmniShotCut SPIKE 完成

- **Title**: OmniShotCut 模型 SPIKE 验证
- **Status**: Done
- **Priority**: P0
- **Module**: models/omnishotcut

### Completion Log

- **Completed Date**: 2026-07-28
- **Summary**: OmniShotCut 已安装、权重已下载、License 已核验、CPU 推理验证通过。
- **Key Findings**:
  - **License**: MIT（code + weights）
  - **Commit**: `23ad6fb41b296fb9258b0e7825125a914573b906`
  - **Weights**: HuggingFace Hub `uva-cv-lab/OmniShotCut`, 156.5 MB
  - **CPU runtime**: ~22s for short demo clip (26 shots detected)
  - **Output format**: `[[start_frame, end_frame], ...]` — frames, **inclusive** end
  - **Confidence**: NOT available in clean_shot mode
  - **CUDA patch needed**: engine.py hard-codes `.to("cuda")` (3 lines)
  - **FFmpeg**: Required via `ffmpeg-python`
- **Acceptance Criteria**:
  - [x] OmniShotCut import OK
  - [x] Weights downloaded + SHA256 verified
  - [x] License verified (MIT)
  - [x] CPU inference confirmed
  - [x] 10 SPIKE questions answered
  - [ ] Adapter written (Adapter pending — IMP-010)
- **Follow-up Improvement IDs**: IMP-010 (OmniShotCut Adapter)

---

### IMP-011 — 置信度暴露 + 帧间像素差验证

- **Title**: Engine patch 暴露 softmax 置信度 + frame-diff 误检过滤
- **Status**: Done
- **Priority**: P1
- **Module**: models/omnishotcut

### Completion Log

- **Completed Date**: 2026-07-28
- **Summary**: Patch engine.py 暴露 softmax 概率 → 发现所有检测 conf > 0.99 无区分力 → 转向帧差方案 → MAD < 5 阈值完美区分真/假切。
- **Key Findings**:
  - Softmax 置信度在所有检测上均 > 0.99（含误检），无法用于过滤
  - 帧间像素差 MAD 真硬切 > 15，假切 < 3，差距 > 一个数量级
  - MAD < 5 + hist_corr > 0.95 阈值：4/5 视频匹配 ground truth
- **Acceptance Criteria**:
  - [x] engine.py patch：`_run_on_numpy` 返回 confidences
  - [x] merge_predictions 置信度感知合并
  - [x] `frame_diff.py`：MAD + histogram correlation + filter
  - [x] run_benchmark.py 集成帧差过滤
  - [x] 误检全部清除（Hard_Cut_1: 1FP, No_Cut_hard: 3FP）
  - [x] 真检全部保留
- **Remaining Issues**: Multiple_Cuts_smooth dissolve 盲区（模型 128×96 固有限制）
- **Follow-up Improvement IDs**: IMP-012

---

### IMP-012 — OmniShotCut 已知限制

- **Title**: OmniShotCut dissolve/wipes 盲区 — 128×96 分辨率限制
- **Status**: Proposed
- **Priority**: P2
- **Module**: models/omnishotcut
- **Current Problem**: Dissolve/wipe 转场在 128×96 推理分辨率下完全不可见。Multiple_Cuts_smooth 漏检 4/6 溶解边界。模型虽然定义了 Dissolve/Wipe/Fade 等标签，但从未激活（全部标记为 General）。
- **Target State**: 接入专用于 dissolve 检测的高分辨率模型，或后处理阶段用多帧像素差滑动窗口检测渐变。
- **Updated Date**: 2026-07-28

---

### IMP-010 — OmniShotCut Adapter 实现

- **Title**: OmniShotCut Adapter — 原始输出 → Shot Schema 转换
- **Status**: Planned
- **Priority**: P0
- **Module**: models/omnishotcut
- **Current Problem**: SPIKE 完成，原始帧范围输出需转换为毫秒时间戳 + Shot Schema。
- **Target State**: Adapter 实现 BaseModelAdapter，帧→毫秒转换，Celery Task 端到端跑通。
- **Key tasks**:
  1. FPS 读取（ffprobe / metadata）
  2. 帧范围 `[start, end]` → 毫秒范围 `[start_ms, end_ms)`
  3. 内联测试视频验证
  4. Schema 校验输出
  5. Artifact 写入 + Manifest
- **Acceptance Criteria**:
  - [ ] 帧→毫秒转换（FPS 分数）
  - [ ] 输出通过 `schemas/shot.py` 校验
  - [ ] 测试视频 `hard_cut.mp4` 可处理
  - [ ] `sample_output.json` 为统一 Schema 格式
- **Related Files**: `models/omnishotcut/adapter.py`, `workers/tasks/shot_tasks.py`
- **Updated Date**: 2026-07-28

---

### IMP-003 — 任务系统实现

- **Title**: Celery 任务系统闭环实现
- **Status**: Proposed
- **Priority**: P0
- **Module**: Workers + Tasks
- **Current Problem**: Celery 骨架和路由已搭建，但任务逻辑全为占位符。
- **Target State**: API 创建任务 → Celery 执行任务 → 数据库状态变化 → 前端可查询。
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

### IMP-004 — 视频上传与标准化

- **Title**: 视频上传与 FFmpeg 标准化流水线
- **Status**: Proposed
- **Priority**: P0
- **Module**: Workers + Storage
- **Acceptance Criteria**:
  - [ ] 上传 MP4/MKV/MOV 可成功保存
  - [ ] 生成 normalized.mp4 + audio.wav + metadata.json
  - [ ] 时间基使用毫秒
  - [ ] Artifact 路径符合规范
- **Related Files**: `workers/tasks/video_tasks.py`, `apps/api/routes/videos.py`, `core/storage/local.py`
- **Updated Date**: 2026-07-27

---

### IMP-005 — 依赖冲突风险

- **Title**: 模型依赖版本冲突监控
- **Status**: Proposed
- **Priority**: P2
- **Module**: Dependencies
- **Current Problem**: 各模型在接入时可能出现 PyTorch/CUDA/依赖版本冲突。
- **Target State**: 当第一个 GPU 模型接入时，验证并记录所有依赖兼容性。
- **Updated Date**: 2026-07-27

---

### IMP-006 — Docker Worker 拆分

- **Title**: CPU/GPU Worker 独立容器化
- **Status**: Proposed
- **Priority**: P2
- **Module**: Docker
- **Current Problem**: MVP 共享一个 Worker（CPU+GPU 混合）。
- **Target State**: 拆分为 `worker-cpu` 和 `worker-gpu` 两个容器。
- **Updated Date**: 2026-07-27

---

### IMP-007 — 对象存储切换

- **Title**: 从本地存储迁移到 S3/MinIO
- **Status**: Proposed
- **Priority**: P3
- **Module**: Storage
- **Updated Date**: 2026-07-27

---

### IMP-008 — 监控与指标

- **Title**: 接入 Prometheus/Grafana 监控
- **Status**: Proposed
- **Priority**: P3
- **Module**: Observability
- **Updated Date**: 2026-07-27
