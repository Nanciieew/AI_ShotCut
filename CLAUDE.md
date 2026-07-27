# CLAUDE.md — 项目长期规则与架构宪法

> **角色**：本项目是影片自动分段系统（Movie Analysis Platform）。  
> **更新规则**：只有架构、模块职责、数据流、Schema 或长期开发规则变化时才更新此文件。  
> **临时进度、Bug、TODO 请写入 `IMPROVEMENTS.md`。**

---

## 1. 项目目标

构建支持持续接入多个 AI 模型的视频分析后端。

核心流程：

```text
上传电影 → 视频标准化 → 镜头检测 → 字幕生成
→ 多模态特征提取 → 场景边界判断 → Shot 合并为 Scene
→ 计算 Scene Score → 保存并返回最终结果
```

---

## 2. 核心架构原则

### 2.1 六层架构

系统分为六层，各层职责严格分离：

| 层 | 目录 | 职责 |
|----|------|------|
| API 层 | `apps/api/` | 接收请求、校验输入、创建任务、返回 task_id、查询状态。**禁止直接执行模型推理。** |
| 编排层 | `core/orchestration/` | 定义任务执行顺序、并行/串行决策、调用 Celery Task、处理失败、缓存复用。 |
| Worker 层 | `workers/` | Celery Worker：FFmpeg 预处理、模型推理、保存 Artifact、更新进度。 |
| 适配层 | `models/*/adapter.py` | 所有模型通过统一 Adapter 接入。上层禁止直接调用第三方模型 API。 |
| 存储层 | `core/storage/` | 文件/Artifact 存储 + 数据库（PostgreSQL/SQLite）。数据库不保存视频。 |
| Schema 层 | `schemas/` | 跨模块统一数据结构，不得任意定义字段名。 |

### 2.2 多模型数据流

```text
原始视频 → normalize_video → normalized.mp4 + audio.wav + metadata.json
    ↓
并行: detect_shots | transcribe | extract_audio_features
    ↓
shots.json + subtitles.json + audio_features.npy
    ↓
extract_visual_features → visual_features.npy
    ↓
build_scene_features → scene_features.npz
    ↓
detect_scene_boundaries → scene_boundaries.json
    ↓
merge_shots_to_scenes → scenes.json
    ↓
calculate_scene_score → scene_scores.json
    ↓
assemble_final_result → final_result.json
```

---

## 3. 硬性规则（不可违反）

### 评分
- **系统只计算 `scene_score`。**
- **禁止创建或重新引入 `action_score`、`plot_score`。**
- **禁止创建 `action_evidence`、`plot_evidence`。**
- 允许的 Evidence：`visual_continuity`、`character_continuity`、`location_continuity`、`subtitle_continuity`、`audio_continuity`、`temporal_gap_ms`。

### 时间
- 内部时间统一使用 **整数毫秒 `timestamp_ms`**。
- 时间区间：**[start_ms, end_ms)**（含 start，不含 end）。
- 禁止使用浮点秒作为唯一时间依据。
- FPS 保存为分数：`fps_num` / `fps_den`。

### 数值范围
- 所有特征值、置信度、score 必须归一化到 **[0, 1]**。

### 模型职责
- **Shot 模型**（OmniShotCut）：只负责 Shot Boundary Detection。
- **Scene 模型**（SceneSeg/BaSSL）：只负责 Scene Boundary 候选。
- **模型不得直接决定最终切点**，最终切点由候选点 + scene_score + 选择算法决定。
- **模型之间不能直接调用**，必须由编排层调度。

### 接入规则
- 所有模型通过**统一 Adapter** 接入（`models/base/adapter.py`）。
- 第三方源码与业务代码隔离（`third_party/`）。
- 模型权重禁止提交到 GitHub。

### 执行规则
- API 层不得执行长推理或长时间 FFmpeg。
- 所有耗时任务从 MVP 开始使用 **Celery**。
- Celery Task 之间只传 ID / URI / JSON，不传大型数组。
- 大型数据先保存为 Artifact，下游通过 URI 读取。
- Redis 不保存整部视频或大型特征矩阵。

### 数据规则
- 所有中间产物必须落盘或进入对象存储。
- 模型原始输出必须转换成统一 Schema 后才能进入下游流程。
- Artifact 路径必须包含：project_id、video_id、模型名、版本号。

---

## 4. 命名与目录规范

参见 `多模型视频分析后端架构与实施规范.md` §9 项目目录规范。

关键约定：
- 对外 API 前缀：`/api/v1/`
- 所有 `__init__.py` 中的导出使用 `from module import Class` 模式
- 文件名：snake_case
- 类名：PascalCase
- Celery Task 名称：`{domain}.{action}` 如 `video.normalize`

---

## 5. 统一数据 Schema 索引

所有跨模块数据使用 `schemas/` 目录下的 Pydantic 模型：

| Schema | 文件 | 核心字段 |
|--------|------|----------|
| Video | `schemas/video.py` | video_id, project_id, duration_ms, fps_num/den, uris |
| Task | `schemas/task.py` | task_id, video_id, status, stage, progress |
| ModelRun | `schemas/model_run.py` | run_id, model_name, model_version, status, runtime_ms |
| Artifact | `schemas/artifact.py` | artifact_id, artifact_type, uri, sha256 |
| Shot | `schemas/shot.py` | shot_id, start_ms, end_ms, boundary_type, confidence |
| SubtitleSegment | `schemas/subtitle.py` | subtitle_id, start_ms, end_ms, text, language |
| Scene | `schemas/scene.py` | scene_id, shot_ids, scene_score |
| SceneEvidence | `schemas/scene.py` | visual/character/location/subtitle/audio_continuity |
| FinalResult | `schemas/result.py` | video + shots + subtitles + scenes + evidence |

---

## 6. 模型输入输出 Contract

所有模型必须遵守 `输入输出规范.md` 中定义的统一 Contract。

核心要求：
- 输入使用统一外壳（schema_version, task_id, video_id, model, input, parameters）
- 成功输出包含 artifacts + metrics
- 失败输出包含 error { code, message, retryable }

---

## 7. Celery 配置规则

```python
task_track_started = True
task_acks_late = True
worker_prefetch_multiplier = 1
task_reject_on_worker_lost = True
broker_connection_retry_on_startup = True
```

重试策略：
- **可重试**：临时网络错误、对象存储超时、Redis 短暂不可用、Worker 临时退出
- **不可重试**：视频损坏、格式不支持、Schema 错误、权重不兼容、CUDA 环境错误

---

## 8. 禁止事项清单

1. 禁止模型互相直接调用
2. 禁止在 API 请求中执行长推理
3. 禁止使用 FastAPI BackgroundTasks 替代 Celery 主流程
4. 禁止将视频或大型 Tensor 放进 Redis
5. 禁止把模型权重提交到 GitHub
6. 禁止直接跟踪第三方仓库主分支
7. 禁止写死本机绝对路径
8. 禁止使用多套时间单位进行模型对齐
9. 禁止只保存最终结果（中间产物也要保存）
10. 禁止覆盖旧模型版本 Artifact
11. 禁止每次任务重新下载权重
12. 禁止每个请求重新加载模型
13. 禁止把整部视频写入数据库
14. 禁止无限自动重试
15. 禁止未检查 License 就用于商业项目
16. **禁止在系统中引入 `action_score`**
17. **禁止在系统中引入 `plot_score`**
18. 禁止模型内部自行操作 API、数据库和最终输出
19. 禁止 Celery Task 直接返回大型数据
20. 禁止没有 `task_id`、`video_id`、`run_id` 的日志

---

## 9. Agent 执行原则

1. 先定义 Schema，再写模型调用
2. 先完成 Celery 骨架，再接模型
3. 先完成单模型闭环，再接第二个模型
4. 每个模型必须独立 Adapter
5. 每个模型必须独立 README
6. 每个模型必须记录版本、权重与 License
7. 每个 Celery Task 必须：可追踪、可重试、尽量幂等、保存 Artifact、更新状态、记录日志
8. 大文件通过 URI 传递
9. 小型结构数据通过 JSON 传递
10. 所有跨模型时间对齐使用整数毫秒
11. 所有结果必须可复现
12. 所有失败必须可定位
13. 所有中间步骤必须可单独重跑
14. 已有成功 Artifact 必须允许复用
15. 最终只输出 Scene 层结果和 Scene Score

---

## 10. 测试规则

- 每个模型至少包含单元测试（Schema 转换、时间转换、Cache Key、路径生成）
- 集成测试覆盖完整链路：FastAPI → Celery → Redis → Model Adapter → Artifact → Database → API 查询
- 回归测试：保存固定测试视频与预期输出范围，升级模型/依赖/CUDA/FFmpeg/Schema 后重跑

---

## 11. 日志规范

- 禁止只使用 `print()`
- 每条日志至少包含：timestamp、level、task_id、video_id、run_id、model、event
- 使用 structlog 进行结构化日志输出
- 失败日志必须包含 error_code 与 retryable 标志

---

## 12. 基础设施规则

### 数据库迁移
- 修改 ORM 模型后必须创建 Alembic Migration（`alembic revision --autogenerate`）
- 禁止仅依赖 `Base.metadata.create_all()` 作为正式迁移方案
- 迁移文件必须可升级和可回滚

### 模型接入
- 新增模型前必须在 `models/registry.yaml` 中登记
- 包括：task、repository、revision、code_license、weights_license、commercial_use
- License 状态未核验时标记 `unknown`，不得猜测
- 模型启用前 `enabled: false`

### Artifact 管理
- 每个主要 Artifact 必须生成伴随 `.manifest.json`（使用 `core/artifacts/writer.py`）
- Artifact 先写临时文件，再原子重命名
- 数据库记录与 Manifest 中的 ID 保持一致

### Worker Queue
- 7 个独立 Queue：video, shot, subtitle, feature, scene, final, maintenance
- CPU 任务（video, final, maintenance）与 GPU 任务（shot, subtitle, feature, scene）分开
- Celery Task 不传输视频、Tensor 或大型数组，只传 ID/URI/JSON

## 13. 配置管理

- 禁止写死路径或配置
- 统一使用 `core/config.py` Settings 类 + `configs/*.yaml` + 环境变量
- 启动时校验关键配置，缺失时快速失败
- `.env` 必须加入 `.gitignore`
- 环境变量模板在 `.env.example`
- Production 不允许弱默认密码

## 14. 代码质量

- CI 必须通过：Ruff lint、Ruff format、MyPy、Pytest、Alembic migration check
- `third_party/` 和 `model_store/` 排除在 lint 范围之外
- 使用 `scripts/dev/check.py` 运行全部检查

---

## 15. 更新记录

| 日期 | 修改内容 | 原因 |
|------|----------|------|
| 2026-07-27 | 初始创建 | 项目基础工程搭建，确立架构宪法 |
| 2026-07-27 | 新增基础设施规则 | 后端结构补全：Alembic、Registry、Manifest、Queue、Settings |
