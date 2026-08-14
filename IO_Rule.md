# 模型输入输出规则

## 适用范围

所有模型通过 `models/*/adapter.py` 实现 `BaseModelAdapter`。Adapter 只负责接收已准备的输入、调用模型或 Provider、校验并标准化输出；不得直接操作 FastAPI 路由、数据库会话、存储根目录或 FinalResult。

当前 Adapter：`ffmpeg_scene`、`doubao_asr`、`doubao_vision`、`subtitle_semantic`。FFmpeg 标准化和关键帧提取由 Workflow 的执行层完成。

## 输入与输出外壳

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

成功输出必须能转换为统一 Schema，并关联一个或多个 Artifact 与运行指标；失败输出必须包含：

```json
{"status": "FAILED", "error": {"code": "<code>", "message": "<message>", "retryable": false}}
```

Workflow 步骤间仅传递 ID、URI 或小型 JSON。视频、音频、图像、数组和模型原始响应先写入 Artifact，下游通过 `storage://` URI 读取。

## 当前步骤 Contract

| Step / Adapter | 输入 | 标准化 Artifact |
|---|---|---|
| `video.normalize` | 原视频 URI | `video.normalized`、`audio.normalized`、`video_probe` |
| `ffmpeg_scene` | 标准化视频 URI | `shots` |
| `shot.extract_keyframes` | 视频 URI、Shot JSON | `shot_keyframes` |
| `doubao_asr` | 受 HMAC 保护的公共 `audio_url` | `subtitle_segments` |
| `subtitle_semantic` | 字幕、Shot JSON | `subtitle_continuity` |
| `doubao_vision` | Shot、关键帧摘要 | `location_character_scores` |
| `scene.merge_score` | Shot 与可用连续性证据 | `final_scenes`、Scene/SceneEvidence 记录 |

Provider URL 由存储服务签发；Adapter 不拼接 ngrok 地址、不解析本地存储路径。下载端点校验 HMAC purpose、过期时间、Artifact 类型和项目范围。

## 时间、数值和评分

- 内部时间使用整数毫秒；区间为 `[start_ms, end_ms)`；FPS 用 `fps_num` / `fps_den`。
- confidence、continuity 和 `scene_score` 必须在 `[0, 1]`。
- 系统只输出 `scene_score`。允许模式：`location_only`、`character_only`、`subtitle_only`、`custom`；custom 的非负权重按总和归一化。
- 允许 Evidence：`visual_continuity`、`character_continuity`、`location_continuity`、`subtitle_continuity`、`audio_continuity`、`temporal_gap_ms`。
- 禁止 `action_score`、`plot_score`、`action_evidence`、`plot_evidence`。

## 血缘、缓存与失败

每个 Workflow 步骤创建独立 ModelRun，Artifact 先原子写入并生成 Manifest，再写数据库输出关系。缓存只能复用成功、文件存在且 SHA-256/大小通过验证的 Artifact；新任务必须重建任务级 ID 与数据库血缘。

可重试错误包括临时网络和 Provider 超时；视频损坏、格式不支持、Schema 错误等不可重试。重试创建新的 `task_id` 并通过 `retry_of_task_id` 关联旧任务。
