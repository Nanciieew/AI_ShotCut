# 本地运行 FFmpeg + OmniShotCut 单模型闭环方案

## 1. 背景

当前 Docker Desktop 的 WSL2 Linux Engine 持续崩溃，错误码：

```text
0xc00000fd
```

当前不继续阻塞在 Docker 修复上，改为：

> 使用本地 Python 环境完成 FFmpeg 标准化与 OmniShotCut 单模型闭环验证，同时保持与未来 Celery、Docker Worker 和多模型任务编排完全兼容。

本方案不是放弃 Docker，而是将：

```text
Docker Worker
```

临时替换为：

```text
Local Python Executor
```

核心业务接口、Adapter、Artifact、Schema 和 Pipeline Service 不得因此改变。

---

## 2. 本次目标

实际跑通：

```text
Hard_Cut_1.mp4
→ FFprobe 原视频
→ FFmpeg 标准化
→ normalized.mp4
→ probe_before.json
→ probe_after.json
→ normalized_video.manifest.json
→ normalized_video Artifact
→ OmniShotCut Raw Inference
→ Converter
→ Validation
→ shots.json
→ shots.manifest.json
→ shot_boundaries Artifact
→ 本地验证报告
```

本阶段完成后，状态应标记为：

```text
LOCAL_MODEL_PIPELINE_VERIFIED
```

不得标记为：

```text
DOCKER_CELERY_LOOP_VERIFIED
```

---

## 3. 对未来任务编排的兼容要求

本地运行不能修改正式工作流的接口设计。

未来任务编排器只应关心：

```text
输入 Artifact
→ 执行器
→ 输出 Artifact
→ 状态
```

不应关心模型运行在本地 Python、Celery Worker、Docker Worker、远程 GPU 服务或云端 API。

当前和未来必须共用：

1. Adapter
2. Converter
3. Validation
4. Input Schema
5. Output Schema
6. Artifact Contract
7. Manifest
8. Pipeline Service
9. 错误码
10. 运行状态定义

---

## 4. 禁止事项

1. 不为了本地运行重写 Adapter。
2. 不把核心逻辑全部塞进一个临时脚本。
3. 不让脚本绕过 Artifact 层。
4. 不修改标准时间单位。
5. 不修改帧区间定义。
6. 不把原始视频直接作为 OmniShotCut 正式输入。
7. 不接入 Whisper、Claude、SceneSeg 或 BaSSL。
8. 不计算 SceneScore。
9. 不筛选最终切点。
10. 不生成最终剪辑视频。
11. 不运行 Redis、Celery、PostgreSQL 或 FastAPI 异步闭环。
12. 不安装 CUDA Toolkit。
13. 不为了兼容 Python 3.14 随意升级模型依赖。

---

## 5. 先扫描现有代码

实施前先扫描并报告：

- `core/media/`
- FFmpeg / FFprobe 封装
- 视频标准化逻辑
- `models/omnishotcut/adapter.py`
- `models/omnishotcut/converter.py`
- `models/omnishotcut/validation.py`
- `models/omnishotcut/config.yaml`
- `core/artifacts/`
- Artifact Writer
- Manifest Schema
- Shot Schema
- Video Artifact Schema
- Storage 接口
- Local Storage 实现
- OmniShotCut Raw Inference 脚本
- 固定测试视频路径
- 权重路径
- requirements 文件
- 当前 Python 版本
- PyTorch / torchvision 兼容要求
- 当前测试文件

按以下状态输出：

```text
READY
PARTIAL
MISSING
CONFLICT
```

开始修改前先给出预计新增文件、预计修改文件、实际运行命令、风险和阻塞项。

---

## 6. Python 环境要求

当前主机已有：

```text
Python 3.14
FFmpeg
FFprobe
```

但不要默认 OmniShotCut 兼容 Python 3.14。

优先确认固定 Commit `23ad6fb` 的真实依赖要求，并创建独立环境：

```text
.venv-omnishotcut/
```

先执行：

```powershell
py -0p
```

如果已有兼容 Python，例如 Python 3.10：

```powershell
py -3.10 -m venv .venv-omnishotcut
.\.venv-omnishotcut\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

如果没有兼容 Python：

1. 明确报告缺失版本；
2. 不强行使用 Python 3.14；
3. 不修改模型依赖绕过；
4. 标记 `BLOCKED_BY_PYTHON_COMPATIBILITY`；
5. 给出需要安装的准确 Python 版本。

使用：

```text
requirements/models/omnishotcut.txt
```

安装并记录：

- Python version
- pip version
- torch version
- torchvision version
- opencv version
- omnishotcut revision

---

## 7. 推荐代码结构

```text
core/
├── media/
│   ├── ffmpeg.py
│   ├── ffprobe.py
│   ├── normalization.py
│   ├── schemas.py
│   └── exceptions.py
├── artifacts/
│   ├── writer.py
│   ├── manifest.py
│   └── schemas.py
└── storage/

models/
└── omnishotcut/
    ├── adapter.py
    ├── converter.py
    ├── validation.py
    ├── config.yaml
    └── exceptions.py

pipelines/
└── services/
    └── omnishotcut_pipeline.py

scripts/
└── local/
    └── run_omnishotcut_pipeline.py
```

核心原则：

```text
脚本
→ 调用 Pipeline Service
→ Pipeline Service 调用标准化服务与 Adapter
→ Artifact Writer 落盘
```

禁止脚本自己拼 FFmpeg、自己加载模型、自己拼最终 JSON。

---

## 8. 定义 Pipeline Service

新增或补全：

```text
pipelines/services/omnishotcut_pipeline.py
```

建议接口：

```python
def run_omnishotcut_pipeline(
    *,
    video_id: str,
    source_video_path: Path,
    source_artifact_id: str | None = None,
    output_root: Path,
) -> PipelineResult:
    ...
```

职责：

```text
1. 校验输入
2. FFprobe 原视频
3. FFmpeg 标准化
4. FFprobe 标准化视频
5. 校验标准化结果
6. 写 normalized_video Artifact
7. 调用 OmniShotCut Adapter
8. Converter
9. Validation
10. 写 shots Artifact
11. 返回小型 PipelineResult
```

标准返回：

```json
{
  "status": "SUCCEEDED",
  "video_id": "video_001",
  "source_artifact_id": "artifact_source_001",
  "normalized_artifact_id": "artifact_normalized_001",
  "shots_artifact_id": "artifact_shots_001",
  "normalized_artifact_uri": "...",
  "shots_artifact_uri": "...",
  "runtime_ms": 0
}
```

禁止返回完整视频、Tensor 或完整 Shot 数组。

---

## 9. 固定测试输入

固定使用：

```text
Hard_Cut_1.mp4
```

自动搜索真实路径，优先：

```text
tests/fixtures/videos/omnishotcut/
data/
```

如果存在多个同名文件，输出候选路径并优先使用测试 Fixture。不得修改原始文件，并记录输入 SHA256。

---

## 10. FFprobe Before

保存：

```text
probe_before.json
```

至少提取：

```json
{
  "video_codec": "h264",
  "audio_codec": "aac",
  "pixel_format": "yuv420p",
  "width": 0,
  "height": 0,
  "fps_num": 30,
  "fps_den": 1,
  "frame_rate_mode": "CFR",
  "duration_ms": 0,
  "frame_count": 0,
  "start_time_ms": 0,
  "has_video": true,
  "has_audio": true
}
```

如无法直接获取 Frame Count，应明确记录计算方式。

---

## 11. FFmpeg 标准化

输出：

```text
normalized.mp4
```

规范：

```text
Container: MP4
Video codec: H.264
Pixel format: yuv420p
Frame rate mode: CFR
Audio codec: AAC
Audio sample rate: 48000 Hz
Faststart: enabled
Start timestamp: normalized to zero
```

规则：

1. 合理 CFR 输入优先保留原 FPS；
2. VFR 输入转换为 CFR；
3. 不无条件固定为 30 FPS；
4. Manifest 记录 Before 和 After FPS。

FFmpeg 调用要求：

- 使用参数列表；
- 禁止 `shell=True`；
- 捕获 stderr；
- 检查返回码；
- 设置超时；
- 输出临时文件；
- 成功后原子重命名；
- 不覆盖原视频；
- 无音轨时仍可成功。

---

## 12. FFprobe After

保存：

```text
probe_after.json
```

验证：

1. 视频流存在；
2. Codec 可读取；
3. Container 为 MP4；
4. Pixel Format 为 yuv420p；
5. FPS、Frame Count 和 Duration 合理；
6. Start Timestamp 接近零；
7. 文件非空；
8. 可再次解码。

推荐容差：

```text
duration_delta_ms <= max(100ms, 1 frame duration)
```

---

## 13. Normalized Video Artifact

生成：

```text
normalized.mp4
probe_before.json
probe_after.json
normalized_video.manifest.json
```

推荐路径：

```text
data/local_validation/projects/{project_id}/videos/{video_id}/artifacts/video_normalization/{version}/
```

本地无 PostgreSQL 时：

- 使用标准 Artifact Schema；
- 生成真实 Artifact ID；
- 持久化 Manifest；
- 数据库登记标记 `NOT RUN`。

---

## 14. OmniShotCut 输入规则

OmniShotCut 只能读取：

```text
normalized_video Artifact
```

不得读取原始 `Hard_Cut_1.mp4`。

输入路径必须来自：

```text
normalized_video.manifest.json
```

Adapter 输入示例：

```json
{
  "video_id": "video_001",
  "input_artifact_id": "artifact_normalized_001",
  "input_artifact_type": "normalized_video",
  "video_path": ".../normalized.mp4",
  "mode": "clean_shot"
}
```

---

## 15. OmniShotCut Raw Inference

运行固定 Commit：

```text
23ad6fb
```

记录：

- 模型是否成功加载；
- 权重路径和修订；
- Device；
- Python / PyTorch 版本；
- 模型加载耗时；
- 推理耗时；
- Raw Frame Ranges；
- 错误信息。

保存：

```text
omnishotcut.raw.json
```

---

## 16. Converter 与 Validation

调用正式实现：

```text
models/omnishotcut/converter.py
models/omnishotcut/validation.py
```

统一：

```text
[start_frame, end_frame_exclusive)
[start_ms, end_ms)
整数毫秒
```

必须确认：

- End Frame inclusive / exclusive 语义；
- Shot 顺序递增；
- Shot 不重叠；
- Shot 不越界；
- 第一 Shot 覆盖起点；
- 最后一 Shot 覆盖终点；
- 不伪造 confidence；
- Pydantic 校验通过。

---

## 17. Shot Artifact

生成：

```text
shots.json
shots.manifest.json
```

推荐路径：

```text
data/local_validation/projects/{project_id}/videos/{video_id}/artifacts/omnishotcut/{model_version}/
```

Manifest 必须记录：

- Artifact ID；
- Input Artifact ID；
- Model Revision；
- Weight Revision；
- Input / Output SHA256；
- Parameters；
- Runtime；
- Device；
- Record Count。

---

## 18. 本地入口脚本

新增：

```text
scripts/local/run_omnishotcut_pipeline.py
```

命令建议：

```powershell
.\.venv-omnishotcut\Scripts\python.exe `
  scripts/local/run_omnishotcut_pipeline.py `
  --video tests/fixtures/videos/omnishotcut/Hard_Cut_1.mp4 `
  --output-root data/local_validation `
  --mode clean_shot
```

脚本职责仅限：

1. 解析参数；
2. 调用 Pipeline Service；
3. 输出小型结果摘要；
4. 设置退出码。

不得复制核心业务逻辑。

---

## 19. 为未来 Celery 保留接口

当前不运行 Celery，但未来 Task 必须调用同一套 Service：

```python
@celery_app.task(queue="video")
def normalize_video_task(...):
    return normalize_video_service(...)

@celery_app.task(queue="shot")
def detect_shots_task(...):
    return omnishotcut_service(...)
```

不得创建 LocalPipeline 和 DockerPipeline 两套实现。

---

## 20. 本地失败路径测试

至少测试：

### 无效视频

```text
FFprobe FAILED
FFmpeg NOT RUN
OmniShotCut NOT RUN
无成功 Artifact
```

### FFmpeg 失败

```text
VIDEO_NORMALIZATION_FAILED
无 normalized Artifact
OmniShotCut NOT RUN
```

### 缺失权重

```text
OMNISHOTCUT_WEIGHT_NOT_FOUND
无 Shot Artifact
```

### 缺失 normalized Artifact

```text
NORMALIZED_ARTIFACT_NOT_FOUND
OmniShotCut 不运行
```

不得删除正式权重。

---

## 21. 测试要求

保留并运行已有 43 个单元测试。

补充：

```text
tests/unit/pipelines/
└── test_omnishotcut_pipeline.py

tests/integration/local/
├── test_video_normalization_local.py
├── test_omnishotcut_local.py
├── test_full_local_pipeline.py
└── test_local_failure_paths.py
```

标记：

```python
@pytest.mark.local
@pytest.mark.model
@pytest.mark.slow
```

普通单元测试不得自动下载权重。

---

## 22. 本阶段完成标准

只有全部满足，才能标记：

```text
LOCAL_MODEL_PIPELINE_VERIFIED
```

验收清单：

```text
□ OmniShotCut 专属 Python 环境建立
□ Python 版本兼容
□ 固定依赖安装成功
□ FFmpeg / FFprobe 可用
□ Hard_Cut_1.mp4 可读取
□ probe_before.json 生成
□ FFmpeg 标准化成功
□ normalized.mp4 生成
□ probe_after.json 生成
□ 标准化校验通过
□ normalized_video.manifest.json 生成
□ normalized_video Artifact 生成
□ OmniShotCut 只读取 normalized.mp4
□ 权重加载成功
□ Raw Inference 成功
□ omnishotcut.raw.json 生成
□ Converter / Validation 成功
□ shots.json / shots.manifest.json 生成
□ Artifact 父子关系正确
□ Input / Output SHA256 正确
□ 本地入口脚本成功
□ 失败路径测试通过
□ 单元测试通过
□ 本地集成测试通过
```

---

## 23. 明确保持 NOT RUN 的项目

以下不得标记 PASSED：

```text
Docker Worker Build
Docker Volume
Redis
Celery Broker
Celery Worker
Queue Routing
PostgreSQL Service
真实数据库 Artifact 记录
FastAPI 异步提交
FastAPI Task / Result 查询
Celery Retry / ACK
多模型编排
```

统一标记：

```text
NOT RUN — BLOCKED BY DOCKER/WSL ENVIRONMENT
```

---

## 24. 最终报告

生成：

```text
models/omnishotcut/LOCAL_PIPELINE_VALIDATION_REPORT.md
```

报告必须包含：

- Environment
- Input
- Probe Before
- Normalization
- Probe After
- Normalized Artifact
- OmniShotCut
- Shot Artifact
- Tests
- Commands Run
- Files Changed
- Not Run
- Risks
- Final Status

最终总状态只允许：

```text
LOCAL_MODEL_PIPELINE_VERIFIED
LOCAL_MODEL_RUNTIME_BLOCKED
FAILED
```

没有真实证据的步骤不得标记为 PASSED。

---

## 25. 完成后下一步

本地闭环完成后：

```text
1. 固定 OmniShotCut 本地依赖锁
2. 固定 Artifact Contract
3. 固定 Pipeline Service 接口
4. 将 Docker/Celery 接入项记录为待恢复
5. 开始其他模型的独立 Raw Test
6. Docker 修复后，让 Celery Task 调用同一套 Service
```

未来恢复 Docker 时只需要：

```text
安装同一套锁定依赖
→ Worker 调用现有 Service
→ Redis / PostgreSQL / FastAPI 接回
```

不得重新实现 OmniShotCut 核心流程。
