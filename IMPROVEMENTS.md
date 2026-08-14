# IMPROVEMENTS.md

此文件只保留已完成的重大改进记录；不维护独立的待解决问题清单。临时问题应通过 Issue、任务或提交记录追踪。

## 2026-08 当前基线

- 执行架构为 FastAPI + `BackgroundExecutor` + `WorkflowService`，不使用 Celery、Redis 或独立 Worker。
- 上传采用流式落盘、SHA-256、大小限制与 FFprobe 容器校验；原视频只保存一次。
- Workflow 已记录 WorkflowRun、ModelRun、Artifact 输入输出血缘，并支持启动恢复、不可变重试与跨任务 Artifact 缓存。
- 豆包 ASR 通过短期签名 Provider URL 获取音频；豆包 Vision 与 DeepSeek 分别生成视觉和字幕连续性证据。
- Scene、SceneEvidence、CandidateBoundary 和 FinalResult 都会落盘并写入数据库；仅支持四种 `scene_score` 模式。
- 最近一次清理已移除 Whisper、OmniShotCut、Qwen VL、Celery/Worker 残留和失效依赖引用。
