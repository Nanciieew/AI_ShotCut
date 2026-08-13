# 模型输入输出规范

## 1. 适用范围

所有模型必须经 `models/*/adapter.py` 实现统一 Adapter Contract。Adapter 只处理模型输入与输出标准化：不得直接操作 FastAPI、数据库、Storage 根路径或最终结果。

## 2. 统一输入外壳

```json
{
  "schema_version": "1.0",
  "task_id": "<task_id>",
  "video_id": "<video_id>",
  "model": {"name": "<model_name>", "version": "<model_version>"},
  "input": {},
  "parameters": {}
}
```

Workflow 步骤之间只传 ID、URI 或小型 JSON。视频、音频、图像与大数组必须先存为 Artifact，再由下游通过 `storage://` URI 读取。

## 3. 统一输出外壳

成功：

```json
{
  "schema_version": "1.0",
  "task_id": "<task_id>",
  "video_id": "<video_id>",
  "status": "SUCCEEDED",
  "model": {"name": "<model_name>", "version": "<model_version>"},
  "artifacts": {},
  "metrics": {"runtime_ms": 0}
}
```

失败：

```json
{
  "status": "FAILED",
  "error": {"code": "<code>", "message": "<message>", "retryable": false}
}
```

## 4. 当前 Adapter Contract

| Adapter | 输入 | 标准化输出 |
|---|---|---|
| `ffmpeg_normalizer` | source video URI | `video.normalized`、`audio.normalized` |
| `ffmpeg_scene` | normalized video URI | `shots` |
| `ffmpeg_keyframes` | video URI、shots | `shot_keyframes` |
| `doubao_asr` | 已签名的 `audio_url` | `subtitle_segments` |
| `doubao_vision` | shots URI、keyframes URI | `location_character_scores` |
| `subtitle_semantic` | subtitles、shots | `subtitle_continuity` |
| `merge` | shots 与允许的 evidence | `final_scenes` |

豆包 ASR 的公网 Provider URL 由 StorageService 创建；Adapter 不得自行拼接 ngrok URL 或访问本地文件。

## 5. 时间、评分与 Evidence

- 内部时间统一为整数毫秒，区间为 `[start_ms, end_ms)`。
- 所有 confidence、continuity、`scene_score` 必须在 `[0, 1]`。
- 最终只计算 `scene_score`。
- 允许 Evidence：`visual_continuity`、`character_continuity`、`location_continuity`、`subtitle_continuity`、`audio_continuity`、`temporal_gap_ms`。
- 禁止 `action_score`、`plot_score`、`action_evidence`、`plot_evidence`。

## 6. Artifact 与缓存

每个主要 Artifact 必须有 Manifest，数据库 Artifact 记录必须与 Manifest 的 ID 一致。跨任务缓存仅复用已成功且经文件大小、SHA-256 校验的 Artifact；任务级 Shot、Subtitle 和 Scene ID 必须重新生成或映射，禁止跨任务直接复用。
