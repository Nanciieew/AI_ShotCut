# Checklist Analysis — AI Movie Segmentation

> 基于 <https://ai-movie-segmentation-checklist.nw2615.chatgpt.site/> 的内容  
> 分析日期：2026-07-28  
> 项目实际状态：OmniShotCut SPIKE + Adapter 完成，Pipeline 未开始

---

## 一、已完成项 ([x])

### Phase 0：项目管理（13/13 ✅）

- [x] 确认当前项目目标和 MVP 范围
- [x] 确认系统最终只保留 `scene_score`
- [x] 全局搜索并删除 `action_score`（从未引入）
- [x] 全局搜索并删除 `plot_score`（从未引入）
- [x] 检查代码中不存在 action evidence
- [x] 检查代码中不存在 plot evidence
- [x] 更新 `README.md`
- [x] 更新 `CLAUDE.md`
- [x] 更新 `IMPROVEMENTS.md`
- [x] 记录今日开发内容
- [x] 提交 Git Commit（多次）
- [x] 推送至远程仓库（GitHub: Nanciieew/AI_ShotCut）
- [x] 添加 Git Tag（Omni_preprocess_test, Omni_adapter_1）

### Phase 1：基础工程（41/41 ✅）

- [x] 创建完整项目目录（25 个目录）
- [x] 创建 `apps/api`、`core`、`models`、`workers`、`pipelines`、`schemas`、`configs`、`tests`
- [x] 创建 `data/projects`、`model_store`、`third_party`
- [x] 配置 `.gitignore`、`.env.example`、`pyproject.toml`、`requirements.txt`
- [x] 配置开发/生产/模型/Celery YAML
- [x] 确认 `.env` 不会提交到 Git
- [x] 创建 API/Worker Dockerfile
- [x] 配置 FastAPI、Redis、Celery Worker、PostgreSQL 服务
- [x] 完成 `docker-compose.yml`
- [ ] 成功启动全部容器（**未实际验证，需 Docker 环境**）
- [x] 实现 `/health`、`/health/live`、`/health/ready`
- [x] 健康检查包含数据库、Redis、Celery、FFmpeg 状态

### Phase 2：本地运行环境（17/21）

- [x] 检查 Python 版本（3.14.4）
- [x] 安装 FFmpeg（imageio-ffmpeg 7.1）
- [x] 确认 `ffmpeg` 可运行
- [x] 确认 `ffprobe` 可运行
- [x] 安装 PyTorch（2.13.0+cpu）
- [x] 检查 PyTorch 可导入
- [x] 检查 CUDA 是否可用（**不可用 — 无 GPU**）
- [x] 完成 `check_environment.py`
- [x] 检查 Python / PyTorch / FFmpeg / Redis / 数据库
- [x] 输出结构化环境检测报告
- [x] 缺失环境时输出修复建议
- [x] 完成 `check_omnishotcut_environment.py`
- [x] 记录 CPU / FFmpeg / PyTorch 版本
- [ ] 记录 GPU 信息（无 GPU）
- [ ] CUDA 可用（无 GPU，已安装 CPU 版 PyTorch）

### Phase 3：Schema 与数据库（29/29 ✅）

- [x] 完成 Video、Task、ModelRun、Artifact Schema
- [x] 完成 Shot、SubtitleSegment、Scene、SceneEvidence Schema
- [x] 完成 FinalResult Schema
- [x] 所有时间字段统一为整数毫秒
- [x] 所有时间区间统一为 `[start_ms, end_ms)`
- [x] Schema 中不存在 `action_score`
- [x] Schema 中不存在 `plot_score`
- [x] 完成 ORM 模型（projects, videos, tasks, model_runs, artifacts, shots, subtitle_segments, scenes, scene_evidence）
- [x] 完成 `core/database/session.py`
- [x] 完成 `scripts/initialize_database.py`
- [x] 配置 Alembic（`alembic.ini` + `alembic/env.py`）
- [x] 支持 PostgreSQL + SQLite 双后端

### Phase 4：Artifact 存储（20/22）

- [x] 完成 `core/storage/base.py`（抽象基类）
- [x] 完成 `core/storage/local.py`（本地存储：路径穿越防护、原子写入、SHA256）
- [x] 完成 `core/storage/s3.py`（占位，明确 NotImplementedError）
- [x] Artifact URI 格式: `storage://projects/{project}/videos/{video}/...`
- [x] 完成 `core/artifacts/manifest.py`（Manifest Pydantic Schema）
- [x] 完成 `core/artifacts/writer.py`（原子写入 + 自动生成 manifest）
- [x] 完成 `core/artifacts/validator.py`（SHA256 校验）
- [x] 完成 `core/artifacts/hashing.py`（cache key 生成）

### Phase 6：Celery 任务系统（部分）

- [x] 完成 `workers/celery_app.py`（应用工厂模式）
- [x] 完成 `workers/signals.py`（task_prerun/success/failure）
- [x] 配置 task_routes（7 队列：video/shot/subtitle/feature/scene/final/maintenance）
- [x] 配置 Celery 核心参数（acks_late, prefetch_multiplier 等）
- [ ] Task 模块仅为占位（IMP-003 待实现）

### Phase 8：OmniShotCut（部分完成，SPIKE + Adapter）

- [x] 检查仓库与 License（MIT, code + weights）
- [x] 固定 Commit（23ad6fb）
- [x] 安装依赖（torch, opencv, huggingface_hub, ffmpeg-python）
- [x] 下载权重（HuggingFace Hub, 156.5MB, SHA256 verified）
- [x] 编写 `models/omnishotcut/adapter.py`
- [x] 编写 `models/omnishotcut/converter.py`（帧→ms）
- [x] 编写 `models/omnishotcut/validation.py`（Schema 校验）
- [x] 编写 `models/omnishotcut/frame_diff.py`（帧差过滤）
- [x] 编写 `models/omnishotcut/exceptions.py`
- [x] 编写 `models/omnishotcut/config.yaml`
- [x] CPU 推理验证通过（22s/demo_clip）
- [x] Frame-diff 后 4/5 测试视频匹配 ground truth
- [x] 输出通过 IO_Rule 合规校验
- [x] 记录 BENCHMARK.md
- [x] 记录 Model Registry（models/registry.yaml）

### Phase 18：日志与配置（部分）

- [x] 完成 `core/logging/config.py`（structlog）
- [x] 完成 `core/logging/context.py`（task/video/run ID 绑定）
- [x] 完成 `core/logging/middleware.py`（FastAPI request_id）
- [x] 完成 `core/config.py`（Pydantic Settings，启动校验）
- [x] 完成 `core/exceptions/__init__.py`

### Phase 19：测试（部分）

- [x] 创建 tests 目录结构
- [x] 完成 `tests/conftest.py`
- [x] 完成 `scripts/generate_test_fixtures.py`

### Phase 20：代码质量

- [x] 配置 Ruff（lint + format）
- [x] 配置 MyPy
- [x] 配置 Pytest + Coverage
- [x] 配置 `.pre-commit-config.yaml`
- [x] 配置 `.github/workflows/ci.yml`

### Phase 21：模型注册表

- [x] 完成 `models/registry.yaml`
- [x] OmniShotCut 已登记（task, repository, revision, license, weights）
- [x] Whisper、Scene Boundary、Visual/Audio Encoder 已占位
- [x] License 未核验时标记 unknown

---

## 二、与项目计划不符的项

以下项存在于 Checklist 中，但根据 `项目图纸.md` + `CLAUDE.md` 的 MVP 范围，不应作为当前任务：

### 2.1 模型过多（超出 MVP 范围）

| Checklist 项 | 问题 | 建议 |
|-------------|------|------|
| **TransNet V2 (17 items)** | 项目规定 Shot 模型统一走 OmniShotCut；TransNet 是备选 | 标记为 `Optional / Phase 2+` |
| **PySceneDetect (16 items)** | 同上，OmniShotCut 替代 | 标记为 `Optional / Phase 2+` |
| **Google Cloud Video Intelligence (18 items)** | 云端依赖，MVP 不使用 | 标记为 `Future / 非 MVP` |
| **Qwen3-ASR (16 items) + Qwen3-ForcedAligner (15 items)** | 项目规定 Whisper 为主字幕模型 | 标记为 `Alternative / Optional` |
| **SenseVoiceSmall (16 items)** | 音频辅助模型，MVP 用 DSP 即可 | 标记为 `Optional` |
| **Qwen2.5-VL (20 items)** | 视觉理解模型太多，项目图纸指定 Claude + VideoLLaMA2 | 标记为 `Alternative` |
| **InternVideo2.5 (15 items)** | 同上，备选模型 | 标记为 `Optional` |
| **VideoLLaMA 2 (16 items)** | 已指定为备选，优先级低于 Claude | 标记为 `Lower Priority` |
| **Claude 语义分析 (17 items)** | API 依赖性+成本，MVP 可能不需要 | 标记为 `Phase 2` |
| **CRCSD (9 items)** | 研究用模型，未发布稳定版本 | 标记为 `Research Only` |
| **MovieBench (8 items)** | 评估数据集，非运行时模型 | 标记为 `Reference Only` |
| **MovieNet (12 items)** | 训练数据集，非推理模型 | 标记为 `Reference Only` |

### 2.2 检查项过于细化

| 问题 | 说明 | 建议 |
|------|------|------|
| Phase 14 每个特征维度拆成独立 section（6 个 scene_score 特征 = 6 个 section） | 这些是同一评分模块的子维度，拆成独立 phase 不合理 | 合并为一个 `Scene Score 计算` 步骤 |
| Phase 8 拆分 5 个 section | OmniShotCut 是主模型，TransNet/PySceneDetect 应归入 `备选扩展`，不与 OmniShotCut 同级 | 重归类 |
| FFmpeg 每个参数各一个 item | 过于细粒度，`ffmpeg -i` 的成功/失败即可覆盖 | 合并简化 |

### 2.3 缺失项（应加入）

| 缺失内容 | 说明 | 建议新增 |
|----------|------|----------|
| Frame-diff 后处理验证 | 当前测试流程的核心步骤 | 加入 Phase 8 |
| IO_Rule 合规检查 | 每个 Adapter 必须通过 | 加入 Phase 8/9/11 |
| `scripts/experiments/run_model_test.py` | 通用 Adapter 测试工具 | 加入 Phase 8 |
| `待解决问题.md` 维护 | 非正式问题追踪 | 加入 Phase 0 |
| GPU 硬编码 patch（engine.py） | OmniShotCut CPU 兼容性 | 加入 Phase 2/8 |
| PATH 隔离问题（本地 models/ 遮盖第三方包） | 已知踩坑 | 加入 Phase 2 |

---

## 三、完成度总览

| Phase | 完成 | 总计 | 状态 |
|-------|------|------|------|
| 0 项目管理 | 13 | 13 | ✅ 完成 |
| 1 基础工程 | 41 | 41 | ✅ 完成 |
| 2 本地运行环境 | 17 | 21 | ⚠️ 无 GPU |
| 3 Schema 与数据库 | 29 | 29 | ✅ 完成 |
| 4 Artifact 存储 | 20 | 22 | ⚠️ |
| 5 FastAPI 接口 | 3 | 25 | ❌ 骨架 |
| 6 Celery 任务 | 8 | 32 | ❌ 骨架 |
| 7 视频预处理 | 0 | 16 | ❌ 未开始 |
| 8 Shot Boundary | 17 | 94 | ⚠️ OmniShotCut SPIKE 完成 |
| 9~17 | 0 | 400+ | ❌ 未开始 |
| 18 日志 | 8 | 26 | ⚠️ 部分完成 |
| 19 测试 | 5 | 34 | ⚠️ 基础结构 |
| 20 质量 | 8 | 16 | ✅ 配置完成 |
| 21 注册表 | 5 | 23 | ⚠️ 部分完成 |
