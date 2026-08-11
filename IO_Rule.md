# 模型输入输出规范

> **适用范围**：所有通过 Adapter 接入的 AI 模型（OmniShotCut、Doubao ASR、Qwen2.5-VL、DeepSeek 等）。  
> **强制级别**：每个模型 Adapter 必须严格遵守此规范。  
> **版本**：1.1（新增 VLM/LLM scoring + Score Merge 规范）

---

## 1. 通用输入外壳

所有模型 Task 的输入必须使用以下统一外壳：

```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": {
    "name": "omnishotcut",
    "version": "1.0.0"
  },
  "input": {
    "<model-specific>": "..."
  },
  "parameters": {
    "<model-specific>": "..."
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | 固定 `"1.0"`，Schema 变更时升级 |
| `task_id` | string | 是 | 父级 Pipeline 任务 ID |
| `video_id` | string | 是 | 关联的视频 ID |
| `model.name` | string | 是 | 模型标识（omnishotcut, whisper, ...） |
| `model.version` | string | 是 | 固定版本号 |
| `input` | object | 是 | 模型特定输入（URI、选项等） |
| `parameters` | object | 否 | 模型运行参数 |

---

## 2. 通用成功输出

```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "status": "SUCCEEDED",
  "model": {
    "name": "omnishotcut",
    "version": "1.0.0"
  },
  "artifacts": {
    "shots": "storage://projects/project_001/videos/video_001/artifacts/omnishotcut/1.0.0/shots.json"
  },
  "metrics": {
    "shot_count": 842,
    "runtime_ms": 162400
  },
  "error": null
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `status` | string | 是 | 固定 `"SUCCEEDED"` |
| `artifacts` | object | 是 | key-value 映射，key 为 artifact 类型名，value 为 URI |
| `metrics` | object | 是 | 至少包含 `runtime_ms`；可包含模型特定指标 |
| `error` | null | 是 | 成功时固定为 `null` |

---

## 3. 通用失败输出

```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "status": "FAILED",
  "model": {
    "name": "omnishotcut",
    "version": "1.0.0"
  },
  "artifacts": {},
  "metrics": {},
  "error": {
    "code": "VIDEO_DECODE_FAILED",
    "message": "FFmpeg could not decode the input video.",
    "retryable": false
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `status` | string | 是 | 固定 `"FAILED"` |
| `artifacts` | object | 是 | 失败时为空对象 `{}` |
| `metrics` | object | 是 | 失败时为空对象 `{}` |
| `error.code` | string | 是 | 错误码，大写下划线格式 |
| `error.message` | string | 是 | 人类可读错误描述 |
| `error.retryable` | boolean | 是 | 是否允许重试 |

### 标准错误码

| 错误码 | retryable | 说明 |
|--------|-----------|------|
| `VIDEO_DECODE_FAILED` | false | FFmpeg 无法解码视频 |
| `UNSUPPORTED_FORMAT` | false | 不支持的视频/音频格式 |
| `SCHEMA_VALIDATION_FAILED` | false | 输入数据不符合 Schema |
| `WEIGHT_INCOMPATIBLE` | false | 权重与代码版本不兼容 |
| `CUDA_ERROR` | false | CUDA 环境错误 |
| `MODEL_CODE_ERROR` | false | 模型内部代码错误 |
| `NETWORK_ERROR` | true | 临时网络错误 |
| `STORAGE_TIMEOUT` | true | 对象存储超时 |
| `REDIS_UNAVAILABLE` | true | Redis 短暂不可用 |
| `WORKER_LOST` | true | Worker 进程退出 |
| `MODEL_DOWNLOAD_TIMEOUT` | true | 模型下载超时 |
| `TRANSCRIPTION_FAILED` | false | Doubao ASR API 调用失败 |
| `VLM_INFERENCE_FAILED` | true | Qwen VL API 调用失败 |
| `PLOT_INFERENCE_FAILED` | true | DeepSeek API 调用失败 |
| `AUDIO_EXTRACTION_FAILED` | false | FFmpeg 音频提取失败 |
| `SHOTS_NOT_FOUND` | false | 上游 shot.detect 未执行或无输出 |
| `SUBTITLES_NOT_FOUND` | false | 上游字幕未生成 |
| `TOO_FEW_SHOTS` | false | Shot 数量不足以评分 (<2) |

---

## 4. 各模型特定 Contract

### 4.1 OmniShotCut — Shot Boundary Detection

**输入**：
```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "omnishotcut", "version": "1.0.0" },
  "input": {
    "video_uri": "storage://projects/project_001/videos/video_001/normalized/video.mp4"
  },
  "parameters": {
    "mode": "clean_shot"
  }
}
```

**输出 Artifact**：`shots.json`

```json
{
  "video_id": "video_001",
  "model": { "name": "omnishotcut", "version": "1.0.0" },
  "shots": [
    {
      "shot_id": "shot_000001",
      "index": 0,
      "start_ms": 0,
      "end_ms": 4280,
      "start_frame": 0,
      "end_frame_exclusive": 103,
      "boundary_type": "hard_cut",
      "confidence": 0.94
    }
  ]
}
```

---

### 4.2 Doubao ASR — REMOVED (2026-08)

> Whisper/Doubao ASR module removed — not currently needed.
> Recover `models/whisper/` from git history if ASR is required in the future.

---

### 4.3 VLM Scene Boundary — Location + Character 评分 (scene.score_vlm)

**输入**：
```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "vlm_scene_boundary", "version": "0.1.0" },
  "input": {
    "shots_uri": "storage://.../shots.json",
    "keyframes_dir": "storage://.../shot_keyframes/1.0.0"
  },
  "parameters": {}
}
```

> Qwen2.5-VL via modelarts-maas API。自适应 batch_size（320px→200, 672px→3）。
> 优先使用 `shot_keyframes_proxy/` 目录。

**输出 Artifact**：`location_character_scores.json`

```json
{
  "video_id": "video_001",
  "scores": [
    {
      "shot_id": "shot_000105",
      "location_change": 92,
      "character_group_change": 15,
      "reason": "室内办公室→户外街道"
    }
  ]
}
```

---

### 4.4 LLM Plot — 叙事事件 + Plot 评分 (scene.score_plot)

**输入**：
```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "deepseek_plot", "version": "1.0.0" },
  "input": {
    "subtitles_uri": "storage://.../subtitles.json",
    "shots_uri": "storage://.../shots.json"
  }
}
```

> DeepSeek 从完整字幕规划大/中/小三级叙事事件 → 映射到 shot boundary。
> Plot 分: major=100, medium=60, minor=30。

**输出 Artifact**：`plot_scores.json`

```json
{
  "video_id": "video_001",
  "events": [
    { "label": "准备武器", "level": "major", "time_range": { "start_ms": 0, "end_ms": 600000 } }
  ],
  "plot_scores": [
    { "shot_id": "shot_000105", "plot_change": 60 }
  ]
}
```

---

### 4.5 Score Merge — 加权合并 (scene.merge_scores)

**四种模式** (`mode` 参数):

| mode | 权重 (L, C, P) | 说明 |
|------|---------------|------|
| `weighted` | (0.35, 0.35, 0.30) | 默认均衡 |
| `location_only` | (1, 0, 0) | 只看场所 |
| `character_only` | (0, 1, 0) | 只看人物 |
| `plot_only` | (0, 0, 1) | 只看情节 |
| `custom` | (L/total, C/total, P/total) | 用户 1-10 slider |

```python
scene_score = round(w_l * location + w_c * character + w_p * plot)
```

> 阈值=50，最小场景=30s。Greedy 选点。

**输出 Artifact**：`final_result.json`

---

### 4.6 Visual Encoder (stub)

**输入**：
```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "visual_encoder", "version": "1.0.0" },
  "input": {
    "video_uri": "storage://.../normalized/video.mp4",
    "shots_uri": "storage://.../artifacts/omnishotcut/1.0.0/shots.json"
  },
  "parameters": {
    "frame_sample_strategy": "begin_middle_end"
  }
}
```

**输出 Artifact**：`visual_embeddings.npy`（形状: `[num_shots, embedding_dim]`）

---

### 4.4 Audio Encoder — Audio Feature Extraction

**输入**：
```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "audio_encoder", "version": "1.0.0" },
  "input": {
    "audio_uri": "storage://.../normalized/audio.wav",
    "shots_uri": "storage://.../artifacts/omnishotcut/1.0.0/shots.json"
  }
}
```

**输出 Artifact**：`audio_embeddings.npy`（形状: `[num_shots, embedding_dim]`）

---

### 4.5 Scene Boundary — Scene Boundary Detection

**输入**：
```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "scene_boundary", "version": "0.1.0" },
  "input": {
    "artifacts": {
      "shots": "storage://.../shots.json",
      "subtitles": "storage://.../subtitles.json",
      "visual_embeddings": "storage://.../visual_embeddings.npy",
      "audio_embeddings": "storage://.../audio_embeddings.npy"
    }
  }
}
```

**输出 Artifact**：`scene_boundaries.json`

```json
{
  "video_id": "video_001",
  "boundaries": [
    {
      "after_shot_id": "shot_000010",
      "is_scene_boundary": true,
      "confidence": 0.89
    }
  ]
}
```

---

### 4.6 Scene Score — Scene Quality Scoring

**输入**（由 `merge_shots_to_scenes` 步骤生成）：
```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "scene_scorer", "version": "1.0.0" },
  "input": {
    "scenes_uri": "storage://.../scenes/scenes.json",
    "evidence_uri": "storage://.../scenes/scene_evidence.json"
  },
  "parameters": {
    "raw_weights": {
      "location_change": 4,
      "character_set_change": 3,
      "visual_semantic_change": 3,
      "time_jump": 2,
      "main_character_change": 2,
      "shot_transition_strength": 1
    }
  }
}
```

**输出 Artifact**：`scene_scores.json`

```json
{
  "video_id": "video_001",
  "scores": [
    {
      "scene_id": "scene_000001",
      "scene_score": 0.82
    }
  ]
}
```

**禁止**：输出中不得包含 `action_score`、`plot_score` 字段。

---

## 5. 时间坐标规则

- 所有时间为 **整数毫秒**（`timestamp_ms`）
- 时间区间统一为 **`[start_ms, end_ms)`**（含 start，不含 end）
- FPS 保存为分数：`fps_num` / `fps_den`（如 24000/1001 对应 23.976 fps）
- 可额外保存：`start_frame`、`end_frame_exclusive`、可读时间码
- **禁止**将浮点秒作为唯一时间依据

---

## 6. Artifact URI 规范

**格式**：
```text
storage://projects/{project_id}/videos/{video_id}/{category}/{model_name}/{version}/{filename}
```

**示例**：
```text
storage://projects/project_001/videos/video_001/artifacts/omnishotcut/1.0.0/shots.json
storage://projects/project_001/videos/video_001/normalized/video.mp4
storage://projects/project_001/videos/video_001/source/original.mp4
storage://projects/project_001/videos/video_001/final/final_result.json
```

**要求**：
- 路径必须包含 `project_id`、`video_id`、模型名称、模型版本
- 禁止使用无追踪信息的扁平命名（如 `results/output.json`）

---

## 7. Schema 版本管理

- 当前统一版本：**`"1.0"`**
- 每次 Schema 变更必须：
  1. 更新 `schema_version` 字段
  2. 更新所有受影响的 Adapter
  3. 重新运行回归测试
  4. 在 IMPROVEMENTS.md 中记录变更
- 旧版本 Artifact 不可被覆盖
- 若 Schema 变更导致缓存失效，所有下游 Artifact 也必须重新生成

---

## 8. 模型输出校验清单

每个模型 Adapter 在返回结果前必须校验：

- [ ] `schema_version` 正确
- [ ] 所有时间单位为整数毫秒
- [ ] 所有置信度/分数在 [0, 1]
- [ ] 不存在禁止字段（action_score, plot_score 等）
- [ ] artifacts 中每个 key 有对应的 URI
- [ ] URI 格式符合规范
- [ ] 失败时 error.code 使用标准错误码
- [ ] 失败时 error.retryable 正确设置
