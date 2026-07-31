# FFmpeg 标准化 + OmniShotCut Docker/Celery 单模型闭环

## 当前状态

当前已完成：

- Docker Desktop 已安装并可运行；
- Worker 镜像已配置；
- FFmpeg / FFprobe 已安装到 Worker；
- OmniShotCut 依赖已安装；
- OmniShotCut 权重 Volume 已配置；
- `/data` 视频与 Artifact Volume 已配置；
- OmniShotCut Adapter / Converter / Validation 已实现；
- 相关单元测试已通过。

本次目标不是继续做环境重构，而是实际跑通：

```text
固定测试视频 Hard_Cut_1.mp4
→ 创建 Video / Task / Input Artifact
→ 提交视频标准化任务
→ Redis
→ Celery Worker
→ FFprobe 分析原视频
→ FFmpeg 标准化视频
→ normalized_video.mp4
→ normalized_video.manifest.json
→ 提交 detect_shots 任务
→ OmniShotCut Adapter
→ Raw Inference
→ Converter
→ Validation
→ shots.json
→ shots.manifest.json
→ PostgreSQL Artifact / Model Run / Task 状态
→ FastAPI 查询结果
```

最终必须证明：

> 原始视频先经过 FFmpeg 标准化，OmniShotCut 只读取标准化后的视频 Artifact，不直接读取用户上传的原始视频。

---

# 一、本阶段禁止事项

本次禁止：

- 接入 Whisper；
- 接入 Claude；
- 接入 SceneSeg；
- 接入 BaSSL；
- 接入其他视觉、音频或人物模型；
- 计算 SceneScore；
- 计算最终切点；
- 使用 FFmpeg 输出最终剪辑视频；
- 搭建多模型 Scene Pipeline；
- 大规模重构已有代码。

FFmpeg 本阶段只负责：

```text
原始视频检查
→ 视频标准化
→ 生成 normalized video Artifact
```

不是负责最终剪辑。

---

# 二、先扫描现有实现

实施前先检查并报告以下真实状态：

1. `docker-compose.yml`
2. Worker 服务和 Queue 配置
3. FFmpeg / FFprobe 公共封装
4. 视频预处理或标准化 Task
5. `video_tasks.py`
6. `shot_tasks.py`
7. Celery App 入口
8. Storage 接口
9. Artifact Writer
10. Video ORM
11. Task ORM
12. Model Run ORM
13. Artifact ORM
14. 原始视频 Artifact 类型
15. 标准化视频 Artifact 类型
16. OmniShotCut Adapter 输入接口
17. FastAPI videos / tasks / results 路由
18. 数据库迁移方式
19. Fixture 视频路径
20. 模型权重路径

按以下状态输出：

```text
READY
PARTIAL
MISSING
CONFLICT
```

不要在扫描完成前批量新增代码。

---

# 三、固定测试输入

本次输入固定为：

```text
Hard_Cut_1.mp4
```

必须明确区分：

```text
Original Input Artifact
→ Hard_Cut_1.mp4

Normalized Video Artifact
→ normalized.mp4
```

不得覆盖原始测试视频。

原始视频保持只读。

推荐存储结构：

```text
/data/projects/{project_id}/videos/{video_id}/
├── source/
│   └── Hard_Cut_1.mp4
└── artifacts/
    ├── video_normalization/{normalization_version}/
    │   ├── normalized.mp4
    │   ├── probe_before.json
    │   ├── probe_after.json
    │   └── normalized_video.manifest.json
    └── omnishotcut/{model_version}/
        ├── shots.json
        └── shots.manifest.json
```

---

# 四、阶段 A：验证 Docker Worker 环境

实际执行：

```powershell
docker info
docker compose config
docker compose build worker
```

构建成功后验证：

```powershell
docker compose run --rm --no-deps worker ffmpeg -version

docker compose run --rm --no-deps worker ffprobe -version

docker compose run --rm --no-deps worker python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"

docker compose run --rm --no-deps worker python -c "import torchvision; print(torchvision.__version__)"

docker compose run --rm --no-deps worker python -c "import cv2; print(cv2.__version__)"

docker compose run --rm --no-deps worker python -c "import omnishotcut; print('omnishotcut import OK')"
```

如果 FFmpeg、FFprobe 或 OmniShotCut 任一关键检查失败：

1. 标记 `FAILED`；
2. 只做最小修复；
3. 重新构建；
4. 不继续后续闭环。

---

# 五、阶段 B：实现或补全视频标准化模块

推荐公共目录：

```text
core/media/
├── __init__.py
├── ffmpeg.py
├── ffprobe.py
├── normalization.py
├── schemas.py
└── exceptions.py
```

如果已有同类模块，优先复用，不要重复创建。

## FFprobe 职责

对原始视频生成结构化元数据：

```json
{
  "video_codec": "h264",
  "audio_codec": "aac",
  "pixel_format": "yuv420p",
  "width": 1920,
  "height": 1080,
  "fps_num": 30,
  "fps_den": 1,
  "frame_rate_mode": "CFR",
  "duration_ms": 42200,
  "frame_count": 1266,
  "start_time_ms": 0,
  "has_video": true,
  "has_audio": true
}
```

必须保存原始 FFprobe 结果：

```text
probe_before.json
```

不要只打印到日志。

---

# 六、定义标准化规格

当前标准化输出统一为：

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

关于 FPS：

1. 优先保留原视频的合理固定 FPS；
2. 如果原视频是 VFR，则转换为 CFR；
3. 不要无条件把所有视频都改成 30 FPS；
4. 输出 Manifest 中必须记录原始 FPS 和标准化后 FPS；
5. 如果为了当前系统必须统一 FPS，先扫描现有 Schema 和模型约束，并明确报告后再采用固定值。

当前 Fixture 如果已经是：

```text
30 FPS CFR
H.264
yuv420p
```

仍然要执行标准化任务，生成独立的 `normalized.mp4`，以验证正式链路。

不得因为输入已经兼容而直接把原始 URI 冒充为标准化 Artifact。

---

# 七、FFmpeg 标准化命令

由公共封装生成参数，不要在多个 Task 中散落字符串命令。

概念命令：

```powershell
ffmpeg `
  -hide_banner `
  -y `
  -i <input_video> `
  -map 0:v:0 `
  -map 0:a:0? `
  -c:v libx264 `
  -pix_fmt yuv420p `
  -vsync cfr `
  -c:a aac `
  -ar 48000 `
  -movflags +faststart `
  -avoid_negative_ts make_zero `
  <normalized_video>
```

实际参数必须根据当前 FFmpeg 版本验证。

要求：

- 使用 `subprocess` 参数列表；
- 禁止 `shell=True`；
- 捕获 stdout / stderr；
- 设置超时；
- 检查返回码；
- 清理临时失败文件；
- 使用临时文件写入后原子重命名；
- 不覆盖原始视频。

如果输入无音轨：

```text
-map 0:a:0?
```

不得导致失败。

---

# 八、标准化后再次 FFprobe

对 `normalized.mp4` 再执行 FFprobe，保存：

```text
probe_after.json
```

验证：

1. 视频流存在；
2. 编码可读取；
3. Duration 合理；
4. Frame Count 合理；
5. FPS 合理；
6. 时间戳从零附近开始；
7. Pixel Format 为 `yuv420p`；
8. Container 为 MP4；
9. 标准化输出不为空；
10. FFmpeg退出状态为成功。

如果标准化前后时长偏差超过允许阈值，任务失败。

推荐容差：

```text
duration_delta_ms <= max(100 ms, 1 frame duration)
```

如项目已有容差规范，优先采用已有规范。

---

# 九、标准化 Artifact

生成：

```text
normalized.mp4
probe_before.json
probe_after.json
normalized_video.manifest.json
```

Manifest 至少包含：

```json
{
  "schema_version": "1.0",
  "artifact_type": "normalized_video",
  "video_id": "...",
  "source_artifact_id": "...",
  "producer": {
    "name": "ffmpeg_normalizer",
    "version": "...",
    "ffmpeg_version": "..."
  },
  "normalization": {
    "container": "mp4",
    "video_codec": "h264",
    "pixel_format": "yuv420p",
    "frame_rate_mode": "cfr",
    "audio_codec": "aac",
    "audio_sample_rate": 48000
  },
  "input": {
    "uri": "...",
    "sha256": "..."
  },
  "output": {
    "uri": "...",
    "sha256": "...",
    "size_bytes": 0
  },
  "probe_before_uri": "...",
  "probe_after_uri": "...",
  "created_at": "..."
}
```

PostgreSQL 创建 `normalized_video` Artifact 记录。

原始 Artifact 和标准化 Artifact 必须通过：

```text
source_artifact_id
```

建立父子关系。

---

# 十、实现或补全 normalize_video Celery Task

建议位置：

```text
workers/tasks/video_tasks.py
```

任务名称：

```python
workers.tasks.video_tasks.normalize_video
```

输入只允许小型参数：

```json
{
  "task_id": "...",
  "video_id": "...",
  "input_artifact_id": "..."
}
```

任务流程：

```text
1. 查询 Video / Task / Input Artifact
2. 更新 Task Stage = normalize_video
3. 更新状态 = RUNNING
4. 创建处理记录，若已有合适 ORM
5. 解析原始视频 Storage URI
6. FFprobe 原始视频
7. 执行 FFmpeg 标准化
8. FFprobe 标准化视频
9. 校验标准化结果
10. 写 Manifest
11. 计算 SHA256
12. 创建 normalized_video Artifact
13. 更新 Task 的当前 Stage
14. 返回小型结果
```

Celery 返回值：

```json
{
  "task_id": "...",
  "video_id": "...",
  "normalized_artifact_id": "...",
  "normalized_artifact_uri": "...",
  "status": "SUCCEEDED"
}
```

不得返回视频内容、FFprobe完整大结果或二进制数据。

---

# 十一、修改 OmniShotCut 输入规则

`detect_shots` 不再读取原始上传视频。

它必须读取：

```text
artifact_type = normalized_video
```

正确流程：

```text
Video
→ 查询最新有效 normalized_video Artifact
→ 解析 Artifact URI
→ OmniShotCut Adapter
```

如果没有标准化 Artifact：

```text
detect_shots = BLOCKED / FAILED_PRECONDITION
```

不得自动退回原始视频，避免正式链路出现隐式旁路。

OmniShotCut Manifest 中必须记录：

```json
{
  "input_artifact_id": "...",
  "input_artifact_type": "normalized_video",
  "input_sha256": "..."
}
```

---

# 十二、先手动验证标准化

在进入 Celery 前，先运行一次容器内标准化脚本。

输入：

```text
Hard_Cut_1.mp4
```

输出：

```text
/data/test_outputs/video_normalization/Hard_Cut_1/normalized.mp4
```

依次验证：

```text
原始视频 FFprobe
→ FFmpeg 标准化
→ 标准化视频 FFprobe
→ 文件校验
→ Manifest
```

然后确认 OmniShotCut 可以直接读取：

```text
normalized.mp4
```

不要继续使用原始 `Hard_Cut_1.mp4` 做 Raw Inference。

---

# 十三、运行标准化后的 Raw Inference

输入必须改为：

```text
/data/test_outputs/video_normalization/Hard_Cut_1/normalized.mp4
```

执行：

```powershell
docker compose run --rm --no-deps worker python scripts/experiments/omnishotcut/run_raw_inference.py --video /data/test_outputs/video_normalization/Hard_Cut_1/normalized.mp4 --mode clean_shot
```

输出：

```text
/data/test_outputs/omnishotcut/Hard_Cut_1.normalized.clean_shot.raw.json
```

报告中记录：

```json
{
  "source_input": "Hard_Cut_1.mp4",
  "omnishotcut_input": "normalized.mp4",
  "ffmpeg_normalized": true,
  "probe_before": "...",
  "probe_after": "..."
}
```

---

# 十四、启动基础服务

标准化和 Raw Inference 均通过后执行：

```powershell
docker compose up -d redis postgres
docker compose ps
docker compose logs redis --tail=100
docker compose logs postgres --tail=100
```

执行数据库迁移。

优先使用：

```powershell
docker compose run --rm migrate
```

若项目没有 migrate 服务，使用现有 Alembic 命令。

确认：

- Redis healthy；
- PostgreSQL healthy；
- Migration 成功。

---

# 十五、启动 Worker

执行：

```powershell
docker compose up -d worker
docker compose logs worker --tail=200
```

执行 Worker Ping：

```powershell
docker compose exec worker celery -A <实际CeleryApp入口> inspect ping
```

确认：

- Worker连接 Redis；
- Worker注册 `video` Queue；
- Worker注册 `shot` Queue；
- `normalize_video` Task 已注册；
- `detect_shots` Task 已注册；
- 无 Import Error；
- 无 FFmpeg路径错误；
- 无数据库错误。

---

# 十六、创建测试记录

为 `Hard_Cut_1.mp4` 创建：

```text
Project
Video
Original Input Artifact
Pipeline Task
```

记录：

```text
project_id
video_id
input_artifact_id
task_id
```

初始输入 Artifact：

```text
artifact_type = original_video
```

不得提前手工创建 `normalized_video` Artifact。

---

# 十七、编排单模型链路

当前链路只包含两个 Task：

```text
normalize_video
→ detect_shots
```

优先使用 Celery Chain：

```python
chain(
    normalize_video.s(task_id, video_id, input_artifact_id),
    detect_shots.s()
)
```

但必须根据现有 Task 参数和返回值设计，避免依赖隐式 positional argument。

更推荐明确传递 ID：

```text
normalize_video 成功
→ 返回 normalized_artifact_id
→ detect_shots 读取 normalized_artifact_id
```

若项目当前不适合直接使用 `chain`，可以由编排 Task：

```text
run_omnishotcut_pipeline
```

依次提交两个步骤。

不要在 `normalize_video` 函数内部直接调用 OmniShotCut Python 方法。

---

# 十八、状态设计

总体 Task 状态：

```text
QUEUED
→ RUNNING
→ SUCCEEDED
```

阶段状态：

```text
normalize_video
→ detect_shots
→ complete
```

建议 Progress：

```text
0   = QUEUED
10  = normalization started
40  = normalized video ready
50  = shot detection started
90  = shots artifact ready
100 = complete
```

失败时必须记录：

```text
failed_stage
error_code
error_message
```

例如：

```text
VIDEO_PROBE_FAILED
VIDEO_NORMALIZATION_FAILED
NORMALIZED_VIDEO_VALIDATION_FAILED
NORMALIZED_ARTIFACT_NOT_FOUND
OMNISHOTCUT_INFERENCE_FAILED
```

---

# 十九、验证 Artifact 链

最终必须存在：

```text
Original Video Artifact
        ↓ source_artifact_id
Normalized Video Artifact
        ↓ input_artifact_id
Shot Boundaries Artifact
```

PostgreSQL 中验证：

```text
original_video.artifact_id
normalized_video.source_artifact_id = original_video.artifact_id
shots.input_artifact_id = normalized_video.artifact_id
```

文件系统验证：

```text
Hard_Cut_1.mp4
normalized.mp4
probe_before.json
probe_after.json
normalized_video.manifest.json
shots.json
shots.manifest.json
```

---

# 二十、验证 FastAPI

提交入口可以是：

```http
POST /api/v1/videos/{video_id}/analyze-shots
```

或复用项目现有接口。

接口只负责：

```text
创建 / 查询 Task
→ 提交 Celery Chain
→ 返回 task_id
```

不得同步运行 FFmpeg 或 OmniShotCut。

查询：

```http
GET /api/v1/tasks/{task_id}
GET /api/v1/videos/{video_id}/results
```

结果至少显示：

- 原始视频 Artifact；
- 标准化视频 Artifact；
- Shot Artifact；
- 当前状态；
- 当前阶段；
- Progress。

---

# 二十一、失败路径测试

至少测试两个失败场景。

## 失败场景 1：无效视频

使用损坏视频副本或无效文件。

预期：

```text
normalize_video = FAILED
detect_shots = NOT RUN
无 normalized_video Artifact
无 shots Artifact
```

## 失败场景 2：缺失标准化 Artifact

直接提交 `detect_shots`，但不给有效 `normalized_artifact_id`。

预期：

```text
detect_shots = FAILED_PRECONDITION
OmniShotCut 不运行
无 shots Artifact
```

不得删除正式权重或原始 Fixture。

---

# 二十二、必须测试的内容

## 视频标准化单元测试

```text
tests/unit/core/media/
├── test_ffprobe.py
├── test_normalization.py
├── test_commands.py
└── test_manifest.py
```

覆盖：

- 有音轨；
- 无音轨；
- VFR；
- CFR；
- 负时间戳；
- FFmpeg返回非零；
- FFprobe失败；
- 输出文件不存在；
- 时长偏差过大；
- 命令参数转义；
- 不使用 `shell=True`。

## OmniShotCut测试

保留并继续运行：

```text
test_converter
test_validation
test_adapter
test_contract
```

## 集成测试

至少增加：

```text
test_normalize_video_task
test_normalized_video_to_omnishotcut
test_full_single_model_chain
test_invalid_video_failure
test_missing_normalized_artifact
```

真实 Docker / 模型测试标记：

```python
@pytest.mark.docker
@pytest.mark.model
@pytest.mark.slow
```

---

# 二十三、完成标准

只有全部满足才标记：

```text
FFMPEG_OMNISHOTCUT_SINGLE_MODEL_LOOP_VERIFIED
```

验收清单：

```text
□ Docker Worker 构建成功
□ FFmpeg 可用
□ FFprobe 可用
□ 原始视频 Artifact 创建成功
□ 原始视频 FFprobe 成功
□ FFmpeg 标准化成功
□ normalized.mp4 生成
□ 标准化后 FFprobe 成功
□ normalized_video.manifest.json 生成
□ normalized_video Artifact 创建成功
□ OmniShotCut 只读取 normalized.mp4
□ 容器内 Raw Inference 成功
□ Adapter 成功
□ Converter 成功
□ Validation 成功
□ shots.json 生成
□ shots.manifest.json 生成
□ Redis 成功
□ PostgreSQL 成功
□ Migration 成功
□ Worker 注册 video Queue
□ Worker 注册 shot Queue
□ normalize_video Task 成功
□ detect_shots Task 成功
□ Celery 两阶段链路成功
□ Artifact 父子关系正确
□ Task 状态正确
□ FastAPI 查询成功
□ 无效视频失败路径通过
□ 缺失 normalized Artifact 失败路径通过
```

---

# 二十四、最终报告

生成：

```text
models/omnishotcut/FFMPEG_SINGLE_MODEL_LOOP_REPORT.md
```

报告必须包含：

## Input

- 原始视频路径；
- 原始 Artifact ID；
- 原始 SHA256。

## FFprobe Before

- Codec；
- FPS；
- Frame Count；
- Duration；
- Pixel Format；
- Audio；
- Timestamp。

## FFmpeg Normalization

- 实际执行参数；
- FFmpeg版本；
- 输出路径；
- 耗时；
- 文件大小；
- 状态。

## FFprobe After

- Codec；
- FPS；
- Frame Count；
- Duration；
- Pixel Format；
- Audio；
- Timestamp；
- 与原视频差异。

## Normalized Artifact

- Artifact ID；
- Artifact URI；
- Manifest；
- SHA256。

## OmniShotCut

- 输入必须是 normalized Artifact；
- 模型 Commit；
- 权重；
- Device；
- Raw Output；
- 推理耗时。

## Shot Artifact

- Shot Count；
- Artifact ID；
- Artifact URI；
- SHA256；
- Manifest。

## Celery

- Task ID；
- Celery Task ID；
- normalize_video 状态；
- detect_shots 状态；
- Worker日志摘要。

## Database

- Video；
- Task；
- Normalized Artifact；
- Model Run；
- Shot Artifact；
- 父子关系。

## FastAPI

- 提交结果；
- Task查询结果；
- Result查询结果。

## Failure Tests

- 无效视频；
- 缺失标准化 Artifact。

## Commands Run

列出实际执行命令。

## Files Changed

列出所有新增和修改文件。

## Not Run

明确列出未执行项目。

## Final Status

只允许：

```text
PASSED
FAILED
NOT RUN
BLOCKED
```

任何没有真实证据的步骤不得标记为 PASSED。
