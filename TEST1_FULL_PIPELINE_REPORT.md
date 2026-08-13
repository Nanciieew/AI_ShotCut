# Test1 完整管线实测报告

## 1. 最终结论

- 输入视频：`D:\wnx\AI_ShotCut\Test1.mp4`
- SHA-256：`2ddae87375e3445fdacd6f76642d9f8d963a0494b034536b1f0b33c21cca7030`
- 视频规格：H.264 + AAC，1920×1080，30 FPS，205.148 秒
- Project ID：`c1f82181fd3c4dd7b1318868f550556b`
- Video ID：`6caa806029384b4094e146c329943e0d`
- 最终成功 Task ID：`81088649620b432599a053ee007157a3`
- Workflow 状态：`SUCCEEDED`
- Workflow 输入到最终返回：`147.995 秒`
- 评分模式：`custom`
- 权重：location、character、subtitle 各 `1/3`

最终结果 API JSON：`D:\wnx\AI_ShotCut\Test1_final_result.json`

最终 Scene Artifact：

`D:\wnx\AI_ShotCut\data\projects\c1f82181fd3c4dd7b1318868f550556b\videos\6caa806029384b4094e146c329943e0d\tasks\81088649620b432599a053ee007157a3\merge\1.0.0\custom_final.json`

## 2. 最终结果统计

| 数据 | 数量 |
|---|---:|
| Shots | 63 |
| SubtitleSegments | 36 |
| Scenes | 4 |
| SceneEvidence | 3 |
| CandidateBoundary（全部） | 62 |
| CandidateBoundary（选中） | 3 |

Scene Score 均位于 `[0,1]`，本次选中 Scene 的分数范围为 `0.6667–0.85`。

## 3. 最终成功任务各步骤耗时

这里的耗时定义为数据库 `ModelRun.started_at → ModelRun.finished_at`，即该步骤从取得输入到完成返回和持久化的墙钟时间。

| 模型/步骤 | 状态 | 耗时 | 说明 |
|---|---|---:|---|
| `ffmpeg_normalizer 1.0.0` | SUCCEEDED | 74.762 秒 | 标准化 MP4 并提取 16 kHz 单声道 WAV |
| `ffmpeg_scene 1.0.0` | SUCCEEDED | 8.124 秒 | 生成 63 个 Shot |
| `ffmpeg_keyframes 1.0.0` | SUCCEEDED | 12.805 秒 | 每个 Shot 提取 1/4、1/2、3/4 关键帧 |
| `doubao_vision 1.0.0` | SUCCEEDED | 0.098 秒 | 命中重试祖先的兼容 Artifact 缓存 |
| `doubao_asr 1.0.0` | SUCCEEDED | 51.744 秒 | 经 ngrok 下载音频并返回 36 条字幕 |
| `subtitle_semantic 1.0.0` | SUCCEEDED | 0.122 秒 | 命中重试祖先的兼容 Artifact 缓存 |
| `merge 1.0.0` | SUCCEEDED | 0.116 秒 | 计算分数、选边界、组装并写入 Scene/Evidence |

由于最终任务复用了同一 Test1 重试链上已经成功的云模型结果，云模型首次真实成功调用耗时如下：

| 云模型 | 首次成功 Task | 真实输入到返回耗时 |
|---|---|---:|
| 豆包 Vision | `66f50776f78e4550a3e25fb1aef08db8` | 482.972 秒 |
| DeepSeek 字幕语义 | `005bc080112347189a96e83bd2efe241` | 664.302 秒 |

## 4. 实测发现并修复的问题

1. API 镜像缺少 PyAV/Pillow，关键帧阶段报 `No module named 'av'`。
   - 已加入 API 正式依赖并重建镜像。
2. Vision Prompt 文件乱码，批量返回会漏掉 Shot ID。
   - 重写 Prompt；改为一个边界一个请求；每批立即校验；最多重试 2 次；并发上限 3；JPEG 直接传输，避免转 PNG 放大请求。
3. Task stage 在 Vision/DeepSeek 运行时仍显示前一步，进度还会倒退。
   - 模型开始时立即更新 stage，并改为单调进度。
4. DeepSeek 遇到 timeout/连接错误后没有重试。
   - 只对 timeout、连接错误、429、5xx 做有限重试；4xx 非限流错误立即失败。
5. DeepSeek 局部剧情分析串行执行且所有阶段默认允许 8192 tokens。
   - 摘要/全局/局部限制为 1024 tokens，重评分限制为 2048 tokens；局部区间并发上限 3；加入阶段耗时日志。
6. 重试任务会重复调用已经成功的收费模型。
   - 新增不可变重试祖先 Artifact 复用；只有 Shot 时间线完全一致才复用，并把旧 Shot ID 映射为本任务的新全局 ID；新任务仍创建独立 ModelRun、Artifact、Manifest 和 I/O 血缘。
7. `candidate_boundaries.scene_id` 在 Scene 写入前触发 autoflush，导致外键失败。
   - 事务内先插入并 flush Scene，再写 SceneEvidence 和 CandidateBoundary。
8. 多数成功 ModelRun 没有填写 `runtime_ms`。
   - 后续每个成功步骤都会写入输入到返回墙钟耗时；本次最终任务已回填。
9. Docker 构建上下文会访问 pytest 临时目录并因权限失败。
   - `.dockerignore` 已排除 `.tmp*/`。
10. 豆包 `403 AccountOverdueError` 被错误标记为可重试。
   - Provider 现在把 401/403 等非限流 4xx 标记为不可重试；只有 429、5xx 和临时网络错误允许重试。

## 5. 外部账户状态

本次豆包 Vision 曾真实成功返回全部 62 个边界。之后服务端返回 `403 AccountOverdueError`，表示火山引擎账户当前存在欠费。最终任务通过复用本次重试链中已经成功且时间线完全一致的 Vision Artifact 完成，因此 Test1 的结果有效且可复现。

对于没有兼容缓存的新视频，仍需先在火山引擎侧补足余额，否则豆包 Vision 会被 Provider 拒绝；这不是代码能够解除的账户限制。

## 6. 验证

- FinalResult HTTP：200
- `Test1_final_result.json`：通过 `schemas.result.FinalResult` 校验
- PostgreSQL：63 Shots、36 Subtitles、4 Scenes、3 Evidence、62 CandidateBoundaries
- Unit tests：124 passed
- 最终改动关键回归：21 passed
- Ruff：passed
- MyPy：passed
- `git diff --check`：passed
