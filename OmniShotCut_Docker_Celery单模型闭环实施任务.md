# OmniShotCut Docker + Celery 单模型闭环实施任务

## 1. 当前目标

本阶段只完成以下闭环：

```text
固定测试视频
→ 创建 Video 记录
→ 创建 Task 记录
→ FastAPI / 调试脚本提交 Celery 任务
→ Redis Broker
→ Celery Worker
→ OmniShotCut Adapter
→ Raw Inference
→ Converter
→ Validation
→ shots.json
→ shots.manifest.json
→ Artifact 数据库记录
→ Model Run 更新
→ Task 更新为 SUCCEEDED / FAILED
→ FastAPI 查询任务和结果
```

本阶段不接入：

- Whisper；
- Scene Boundary；
- 多模态特征模型；
- SceneScore；
- 切点筛选；
- FFmpeg 最终剪辑；
- 完整端到端电影分析 Pipeline。

本阶段的唯一目标是证明：

> OmniShotCut 可以在 Docker Worker 中，通过 Celery 被异步调用，并将标准 Shot Artifact 持久化到存储和 PostgreSQL，再由 FastAPI 查询。

---

# 2. 当前已知状态

当前已完成：

- OmniShotCut 固定测试输入；
- OmniShotCut 固定 Commit：`23ad6fb`；
- `requirements/models/omnishotcut.txt`；
- `docker/worker.Dockerfile`；
- `docker-compose.yml`；
- `/data` 与 `/models` Volume；
- FFmpeg；
- PyTorch CPU 依赖声明；
- OmniShotCut 环境检查脚本；
- OmniShotCut Raw Inference 脚本；
- BaseModelAdapter；
- Celery；
- Redis；
- PostgreSQL；
- FastAPI；
- Task、Model Run、Artifact ORM / Schema；
- videos、tasks、results 路由。

当前尚未完成或未验证：

- Docker Engine 真实运行；
- Worker 镜像构建；
- 容器内依赖 Import；
- 权重挂载；
- Fixture 挂载；
- 容器内 Raw Inference；
- OmniShotCut Adapter；
- Converter；
- Validation；
- `detect_shots` Celery Task；
- Artifact 写入；
- Model Run / Task 状态更新；
- FastAPI 结果查询闭环。

---

# 3. 执行原则

1. 先扫描现有代码，再修改。
2. 优先增量修改，不大规模重写。
3. 不修改固定测试视频。
4. 不接入其他模型。
5. 不把权重复制进 Docker Image。
6. 权重只通过 `/models` 只读 Volume 挂载。
7. 视频和 Artifact 通过 `/data` Volume 挂载。
8. 当前使用 CPU PyTorch。
9. 不安装 CUDA Toolkit。
10. `torch.cuda.is_available() == False` 属于预期。
11. 不在 FastAPI Route 中直接执行模型推理。
12. FastAPI 只提交 Celery Task。
13. Celery Task 只传 ID、URI 和小型 JSON。
14. 不把完整 Shot 数组写入 Redis Result Backend。
15. Raw Output、标准输出和 Manifest 必须落盘。
16. 所有时间统一使用整数毫秒。
17. 所有时间区间统一为 `[start_ms, end_ms)`。
18. 所有帧区间统一为 `[start_frame, end_frame_exclusive)`。
19. 不伪造 confidence。
20. 不引入 `action_score`、`plot_score` 或 `scene_score`。
21. 未执行步骤标记 `NOT RUN`。
22. 失败步骤标记 `FAILED`。
23. 不得将未执行或失败描述为通过。

---

# 4. 开始前必须输出的检查结果

开始实施前，先扫描并输出：

## 已有文件

- Worker Dockerfile；
- Docker Compose；
- OmniShotCut requirements；
- Adapter 基类；
- Shot Schema；
- Task Schema；
- Artifact Schema；
- Model Run ORM；
- `shot_tasks.py`；
- videos / tasks / results 路由；
- Storage；
- Artifact Writer；
- 环境检查脚本；
- Raw Inference 脚本。

## 当前状态

按以下分类列出：

```text
已完成
部分完成
缺失
冲突
```

## 计划

列出：

1. 计划新增文件；
2. 计划修改文件；
3. 计划执行命令；
4. 可能的阻塞项；
5. 验收顺序。

不要在未完成扫描前批量生成代码。

---

# 5. 阶段 A：验证 Docker Worker 环境

## A1. Docker 环境

执行：

```powershell
docker --version
docker compose version
docker info
docker compose config
```

要求：

- Docker CLI 可用；
- Docker Engine 正在运行；
- Compose v2 可用；
- Compose 配置合法。

如 Docker 不可用：

```text
Overall Status = BLOCKED
```

并停止后续真实运行，不伪造结果。

---

## A2. Worker 镜像构建

执行：

```powershell
docker compose build --no-cache worker
docker compose build worker
```

记录：

- 首次构建耗时；
- 缓存构建耗时；
- 镜像名称；
- 镜像大小；
- 失败步骤；
- 关键依赖版本。

---

## A3. 容器依赖检查

执行：

```powershell
docker compose run --rm worker python --version

docker compose run --rm worker python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"

docker compose run --rm worker python -c "import torchvision; print(torchvision.__version__)"

docker compose run --rm worker python -c "import cv2; print(cv2.__version__)"

docker compose run --rm worker python -c "import omnishotcut; print('omnishotcut import OK')"

docker compose run --rm worker ffmpeg -version

docker compose run --rm worker ffprobe -version

docker compose run --rm worker celery --version
```

每项状态只允许：

```text
PASSED
FAILED
NOT RUN
BLOCKED
```

只有全部关键 Import 成功，才进入下一阶段。

---

# 6. 阶段 B：验证 Volume 与固定输入

## B1. 权重挂载

确认：

```text
宿主机：./model_store
容器内：/models
权限：只读
```

执行：

```powershell
docker compose run --rm worker python -c "from pathlib import Path; p=Path('/models'); print(p.exists()); print([str(x) for x in p.rglob('*') if x.is_file()][:50])"
```

检查：

- 权重文件存在；
- 路径和配置一致；
- 文件大小合理；
- Worker 可读；
- Worker 不可修改正式权重。

如已有 SHA256，执行校验。

---

## B2. Fixture 挂载

确认：

```text
宿主机：./data
容器内：/data
```

执行：

```powershell
docker compose run --rm worker python -c "from pathlib import Path; p=Path('/data'); print(p.exists()); print([str(x) for x in p.rglob('*.mp4')][:50])"
```

优先测试：

```text
Hard_Cut_1.mp4
```

---

## B3. FFprobe 解码

对固定测试视频执行：

```powershell
docker compose run --rm worker ffprobe -v error -show_format -show_streams -of json /data/<fixture-path>/Hard_Cut_1.mp4
```

确认：

- 视频可读取；
- FPS 可获取；
- Duration 可获取；
- Frame Count 可获取或可计算；
- 编码格式可识别。

---

# 7. 阶段 C：容器内 Raw Inference

执行现有 Raw Inference 脚本：

```powershell
docker compose run --rm worker python scripts/experiments/omnishotcut/run_raw_inference.py --video /data/<fixture-path>/Hard_Cut_1.mp4 --mode clean_shot
```

Raw Output 必须保存到：

```text
/data/test_outputs/omnishotcut/Hard_Cut_1.clean_shot.raw.json
```

Raw Output 至少包含：

```json
{
  "schema_version": "raw-1.0",
  "model": {
    "name": "omnishotcut",
    "code_revision": "23ad6fb",
    "weight_revision": ""
  },
  "input": {
    "filename": "Hard_Cut_1.mp4",
    "fps_num": 30,
    "fps_den": 1,
    "frame_count": 0,
    "duration_ms": 0
  },
  "parameters": {
    "mode": "clean_shot"
  },
  "raw_result": [],
  "metrics": {
    "device": "cpu",
    "model_load_ms": null,
    "inference_ms": null
  },
  "error": null
}
```

要求：

1. 保留原始 Frame Range 语义。
2. NumPy / Tensor 转为普通 JSON 类型。
3. 不添加 Shot ID。
4. 不转换成毫秒。
5. 不伪造置信度。
6. 失败时仍保存错误报告。
7. 输出必须位于持久化 `/data`。

若 CPU 推理超时：

```text
Status = BLOCKED_BY_CPU_PERFORMANCE
```

不要修改模型源码伪造结果。

---

# 8. 阶段 D：实现标准化模型层

正式目录：

```text
models/omnishotcut/
├── __init__.py
├── adapter.py
├── converter.py
├── validation.py
├── exceptions.py
├── config.yaml
├── README.md
└── BENCHMARK.md
```

---

## D1. Adapter

实现：

```python
class OmniShotCutAdapter(BaseModelAdapter):
    name = "omnishotcut"
    version = "23ad6fb"

    def load(self) -> None:
        ...

    def predict(self, model_input: dict) -> dict:
        ...

    def health_check(self) -> bool:
        ...

    def unload(self) -> None:
        ...
```

职责：

- 加载模型；
- 复用模型实例；
- 调用 Raw Inference；
- 捕获模型错误；
- 调用 Converter；
- 调用 Validation；
- 返回标准结果。

禁止：

- 直接操作 FastAPI；
- 直接创建 Celery Task；
- 直接写数据库；
- 计算 Scene；
- 计算 SceneScore；
- 调用最终 FFmpeg 切片。

---

## D2. Converter

负责：

```text
Raw Frame Range
→ 标准 Shot
```

统一换算：

```python
timestamp_ms = round(frame_index * fps_den * 1000 / fps_num)
```

标准 Shot：

```json
{
  "shot_id": "shot_000001",
  "video_id": "video_001",
  "index": 0,
  "start_frame": 0,
  "end_frame_exclusive": 100,
  "start_ms": 0,
  "end_ms": 3333,
  "boundary_type": null,
  "confidence": null
}
```

必须通过源码和测试确认：

```text
OmniShotCut raw end_frame 是否包含
```

若 raw end_frame 为包含式：

```python
end_frame_exclusive = raw_end_frame + 1
```

不得猜测。

---

## D3. Validation

至少检查：

1. Shot 列表非空；
2. Shot index 连续；
3. Shot ID 唯一；
4. `start_frame >= 0`；
5. `end_frame_exclusive > start_frame`；
6. `start_ms >= 0`；
7. `end_ms > start_ms`；
8. Shot 顺序递增；
9. Shot 不重叠；
10. Shot 不越界；
11. 第一段接近视频起点；
12. 最后一段接近视频终点；
13. 相邻 Shot 不存在异常空隙。

语义错误必须抛出明确异常，不得全部静默修复。

---

# 9. 阶段 E：Artifact 输出

标准输出路径：

```text
/data/projects/{project_id}/videos/{video_id}/artifacts/omnishotcut/{model_version}/
├── shots.json
└── shots.manifest.json
```

`shots.json`：

```json
{
  "schema_version": "1.0",
  "video_id": "video_001",
  "producer": {
    "model_name": "omnishotcut",
    "model_version": "23ad6fb",
    "mode": "clean_shot"
  },
  "shot_count": 0,
  "shots": []
}
```

写入顺序：

```text
shots.json.tmp
→ Pydantic 校验
→ 原子重命名
→ 计算 SHA256
→ 写入 Manifest
→ 创建数据库 Artifact
```

Manifest 至少包含：

- artifact_id；
- video_id；
- run_id；
- model_name；
- model_version；
- code_revision；
- weight_revision；
- schema_version；
- input SHA256；
- output SHA256；
- record_count；
- parameters；
- created_at。

---

# 10. 阶段 F：Celery detect_shots 单任务

实现或补全：

```text
workers/tasks/shot_tasks.py
```

任务名称：

```python
workers.tasks.shot_tasks.detect_shots
```

输入只允许：

```json
{
  "task_id": "task_001",
  "video_id": "video_001"
}
```

Task 流程：

```text
1. 查询 Task
2. 更新 Task = RUNNING
3. 更新 Stage = detect_shots
4. 创建 Model Run
5. 检查缓存
6. 查询 Video / 输入 Artifact
7. 解析 Storage URI
8. 构造标准 Model Input
9. 获取 OmniShotCut Adapter
10. 执行推理
11. Converter
12. Validation
13. 写 shots.json
14. 写 Manifest
15. 创建 Artifact
16. 更新 Model Run = SUCCEEDED
17. 更新 Task = SUCCEEDED
18. 返回小型结果
```

Celery 返回值只允许：

```json
{
  "task_id": "task_001",
  "video_id": "video_001",
  "run_id": "run_001",
  "artifact_id": "artifact_001",
  "artifact_uri": "storage://...",
  "status": "SUCCEEDED"
}
```

禁止返回完整 Shot 数组。

---

# 11. 阶段 G：启动 Redis、PostgreSQL 与 Worker

执行：

```powershell
docker compose up -d redis postgres
docker compose ps
```

执行数据库迁移：

```powershell
docker compose run --rm migrate
```

若项目没有 migrate 服务，则使用现有 Alembic 命令。

启动 Worker：

```powershell
docker compose up -d worker
docker compose logs worker --tail=200
```

Worker Ping：

```powershell
docker compose exec worker celery -A workers.celery_app inspect ping
```

确认：

- Redis healthy；
- PostgreSQL healthy；
- Migration 成功；
- Worker 连接 Redis；
- Worker 注册 `shot` Queue；
- 无 Import Error；
- 无数据库连接错误。

---

# 12. 阶段 H：创建单模型测试记录

不要运行完整 Pipeline。

为固定测试视频创建：

- Project；
- Video；
- Input Artifact；
- Task。

允许使用：

- 现有 API；
- 测试脚本；
- Fixtures；
- 数据库初始化脚本。

必须记录：

```text
project_id
video_id
input_artifact_id
task_id
```

输入视频 URI 必须可被 Worker 解析到 `/data`。

---

# 13. 阶段 I：提交 detect_shots

优先使用调试脚本：

```powershell
docker compose run --rm api python scripts/run_omnishotcut_task.py --video-id <VIDEO_ID>
```

或调用开发接口：

```http
POST /api/v1/videos/{video_id}/steps/detect-shots
```

要求：

1. FastAPI 只提交 Celery Task。
2. 不同步等待推理。
3. 返回 `task_id` 与 `celery_task_id`。
4. Worker 从 `shot` Queue 消费。
5. 不运行其他模型。

---

# 14. 阶段 J：验证闭环结果

## Task

检查：

```text
QUEUED
→ RUNNING
→ SUCCEEDED
```

失败时：

```text
QUEUED
→ RUNNING
→ FAILED
```

## Model Run

检查：

- model_name；
- model_version；
- code_revision；
- weight_revision；
- parameters；
- device；
- runtime_ms；
- status；
- error_code；
- error_message。

## Artifact

检查：

- artifact_id；
- artifact_type；
- URI；
- SHA256；
- schema_version；
- run_id；
- video_id。

## 文件

检查：

```text
shots.json
shots.manifest.json
```

要求：

1. 文件存在；
2. JSON 合法；
3. Pydantic 校验通过；
4. Shot Count 一致；
5. SHA256 一致；
6. 数据库 URI 可解析；
7. 旧版本 Artifact 未被覆盖。

## Redis

确认：

- Task 消息正常；
- Result 中无完整 Shot 数组；
- Redis 未保存视频、Tensor 或大型 Artifact。

---

# 15. 阶段 K：FastAPI 查询

验证：

```http
GET /api/v1/tasks/{task_id}
GET /api/v1/videos/{video_id}/results
```

Task 查询至少返回：

```json
{
  "task_id": "task_001",
  "video_id": "video_001",
  "status": "SUCCEEDED",
  "stage": "detect_shots",
  "progress": 100
}
```

结果查询至少返回：

```json
{
  "video_id": "video_001",
  "status": "SUCCEEDED",
  "artifacts": [
    {
      "artifact_type": "shot_boundaries",
      "artifact_uri": "storage://..."
    }
  ]
}
```

API 不直接返回本机绝对路径。

---

# 16. 阶段 L：失败测试

至少测试一个非破坏性失败场景：

- 错误 Video ID；
- 无效输入 Artifact URI；
- 临时指定不存在的测试权重路径；
- 损坏测试视频副本。

验证：

```text
Task = FAILED
Model Run = FAILED
Error Code 存在
Error Message 已清理
无成功 Artifact
Worker 未崩溃
后续正常任务仍可执行
```

不要删除正式权重文件。

---

# 17. 必须测试的内容

## 单元测试

```text
tests/unit/models/omnishotcut/
├── test_converter.py
├── test_validation.py
├── test_adapter.py
└── test_contract.py
```

至少覆盖：

- 24 FPS；
- 25 FPS；
- 24000/1001 FPS；
- 30000/1001 FPS；
- end_frame inclusive 转 exclusive；
- 单 Shot；
- 多 Shot；
- 重叠；
- 越界；
- 空结果；
- 不伪造 confidence；
- 模型未加载；
- 推理异常映射。

## 集成测试

```text
tests/integration/models/omnishotcut/
├── test_container_runtime.py
├── test_raw_inference.py
├── test_adapter_inference.py
├── test_celery_task.py
└── test_failure_path.py
```

真实模型测试必须标记：

```python
@pytest.mark.model
@pytest.mark.slow
```

默认普通 `pytest` 不自动下载权重或执行真实推理。

---

# 18. 当前阶段禁止事项

1. 不测试其他模型。
2. 不接入 Whisper。
3. 不接入 Scene Boundary。
4. 不计算 SceneScore。
5. 不筛选最终切点。
6. 不调用 FFmpeg 输出最终视频。
7. 不搭建完整多模型 Pipeline。
8. 不修改公共 Scene Schema。
9. 不将权重写入 Docker Image。
10. 不将完整 Shot 数组放入 Redis。
11. 不让 FastAPI 同步运行模型。
12. 不因为无 GPU 安装 CUDA Toolkit。
13. 不引入 `action_score`。
14. 不引入 `plot_score`。

---

# 19. 阶段状态定义

## `ENVIRONMENT_VERIFIED`

满足：

- Worker 镜像构建成功；
- 所有关键 Import 成功；
- FFmpeg / FFprobe 成功；
- Volume 可见。

## `MODEL_RUNTIME_VERIFIED`

额外满足：

- Raw Inference 成功；
- Raw Output 持久化；
- Adapter / Converter / Validation 通过。

## `TASK_VERIFIED`

额外满足：

- Celery Worker 成功消费；
- detect_shots 成功；
- Task / Model Run 更新正确。

## `OMNISHOTCUT_SINGLE_MODEL_LOOP_VERIFIED`

额外满足：

- Artifact 写入；
- PostgreSQL 记录；
- FastAPI 查询；
- 失败路径验证；
- Redis 未承载大型结果。

只有达到最后一个状态，本阶段才算完成。

---

# 20. 最终验收清单

```text
□ Docker Engine 可用
□ Compose 配置通过
□ Worker 镜像构建成功
□ torch import 成功
□ torchvision import 成功
□ cv2 import 成功
□ omnishotcut import 成功
□ ffmpeg 可用
□ ffprobe 可用
□ 权重 Volume 可见
□ Fixture Volume 可见
□ Fixture 可解码
□ Raw Inference 成功
□ Raw Output 持久化
□ Adapter 已实现
□ Converter 已实现
□ Validation 已实现
□ Shot Schema 校验通过
□ shots.json 已生成
□ shots.manifest.json 已生成
□ Redis 启动成功
□ PostgreSQL 启动成功
□ 数据库迁移成功
□ Celery Worker 启动成功
□ Worker Ping 成功
□ detect_shots Task 成功
□ Task 状态更新正确
□ Model Run 记录正确
□ Artifact 记录正确
□ FastAPI Task 查询成功
□ FastAPI Result 查询成功
□ Redis 未存储完整 Shot 数组
□ 失败路径验证通过
□ 单元测试通过
□ 集成测试通过
```

---

# 21. 最终报告

完成后生成：

```text
models/omnishotcut/SINGLE_MODEL_LOOP_REPORT.md
```

报告包含：

1. 当前环境；
2. Docker / Compose 版本；
3. Worker 镜像；
4. Python / PyTorch / torchvision / OpenCV；
5. FFmpeg / FFprobe；
6. OmniShotCut Commit；
7. 权重信息；
8. Volume；
9. Raw Inference；
10. Frame Range 语义；
11. Adapter；
12. Converter；
13. Validation；
14. Celery Task；
15. Task ID；
16. Model Run ID；
17. Artifact ID；
18. Artifact URI；
19. shots.json；
20. Manifest；
21. FastAPI 查询结果；
22. 失败测试；
23. 实际执行命令；
24. 新增文件；
25. 修改文件；
26. 测试结果；
27. 未执行项；
28. 风险；
29. 下一步。

状态只允许：

```text
PASSED
FAILED
NOT RUN
BLOCKED
```

没有真实证据的步骤不得标记为 PASSED。
