# IMPROVEMENTS.md — 近期改进记录

> 更新规则：重大功能、架构变化、性能优化写入此文件。临时 bug 和 TODO 保留。

---

## 2026-08-05: Scene Score 计算模式 + 自适应 Batch + 音频分片

### 四种 Scene Score 模式
- location_only: 只看场所变化 (w=1,0,0)
- character_only: 只看人物变化 (w=0,1,0)
- plot_only: 只看情节变化 (w=0,0,1)
- custom: 用户可调 L/C/P 权重 (1-10 -> 归一化)
- CLI: python merge_scores.py --mode plot_only

### VLM 自适应 Batch Size
- 320px proxy -> batch_size=200（大幅减少 API 调用）
- 672px -> batch_size=3
- 自动检测首帧分辨率，无需手动配置

### Doubao ASR 自动分片
- 音频 >15min -> ffmpeg 切段 + ThreadPoolExecutor 并行
- 2h 电影从不可用 -> ~10s 完成全部转录
- 自动合并 chunk 结果 + 时间戳偏移

### 320x180 VLM Proxy 关键帧
- scripts/extract_keyframes.py --vlm-proxy
- 2h 电影 VLM 评分: 57h -> ~3min
- Celery task 自动检测 proxy 目录优先使用

### 关键帧优化
- 每 shot 从 3 帧 -> 2 帧 (25%+75%，去掉无用的 50%)
- 18 个测试全部通过

---

## 2026-08-04: Doubao ASR + Qwen VL + DeepSeek 完整链路

### Doubao ASR 接入
- 取代本地 Whisper 模型，使用火山引擎 OpenSpeech API
- 认证: X-Api-Key + UUID-only key (从 api-key:uuid 格式自动提取)
- 支持中文/英文自动检测

### Qwen VL Location + Character 评分
- scene.score_vlm: 对每个 shot 边界评估场所变化 + 人物群体变化
- 输入: 关键帧对 (shot A 尾帧 + shot B 首帧)
- 输出: location_change (0-100) + character_group_change (0-100)

### DeepSeek 叙事事件 + Plot 评分
- scene.score_plot: 从字幕规划大/中/小三级叙事事件
- Plot 分映射: major=100, medium=60, minor=30
- 事件 -> shot boundary 自动对齐

### Celery Task 注册
- workers/tasks/scene_score_tasks.py: 3 个新 task
- workers/tasks/subtitle_tasks.py: stub -> 完整 Doubao 实现
- core/orchestration/omnishotcut_pipeline.py: group 并行链

### 全流程自动化
- run_complete_pipeline.py: 视频输入 -> 归一化 -> Shot -> 关键帧 -> 字幕 -> VLM -> LLM -> 合并
- 测试通过: Complete_test1 (1.1GB, 15min, 167 shots, 10 场景)

---

## 2026-08-01: PR 拆分 + CI 修复

### OmniShotCut 双 PR 拆分
- PR1: OmniShotCut 基础闭环 (18 commits, 115 files -> master)
- PR2: 关键帧提取 + 编排修正 (2 commits, 19 files -> master)
- CI: ruff lint/format 全通过, MyPy 0 issues, 150/150 tests

### Orchestration 修正
- 所有 chain link -> immutable signature
- 失败传播: return FAILED dict -> raise NonRetryableTaskError
- 仅 final.pipeline_complete 标记 Task SUCCEEDED
- get_artifact_for_task(): task-scoped artifact lookup

### 关键帧提取
- PyAV 单次顺序解码
- 整数帧数学 (无 round(), 无浮点位置)
- PTS 校验 + 672px JPEG 缩放 + SHA-256 + 原子写入

---

## 已知待处理

- [ ] core/media/ffmpeg.py Stream Copy 优化 (未提交, 需独立测试)
- [ ] models/vlm_boundary/ ruff lint 清理 (69 预存错误)
- [ ] Qwen VL 内容审核误拦 (~37% 边界被拒)
- [ ] 字幕无 utterance 级时间戳 (Doubao 极速模式限制)
