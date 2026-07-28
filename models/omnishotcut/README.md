# OmniShotCut Integration

## 任务

Shot Boundary Detection — 镜头边界检测。

OmniShotCut 只负责检测自然镜头边界（hard cut、dissolve、wipe 等），输出 Shot 范围、转场类型和置信度。

**不负责**：Scene 合并、Scene Score、情节理解、动作评分。

---

## 输入

遵循 [IO_Rule.md](../../IO_Rule.md) §1 通用输入外壳。

```json
{
  "schema_version": "1.0",
  "task_id": "task_001",
  "video_id": "video_001",
  "model": { "name": "omnishotcut", "version": "1.0.0" },
  "input": {
    "video_uri": "storage://projects/{project_id}/videos/{video_id}/normalized/video.mp4"
  },
  "parameters": {
    "mode": "clean_shot"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `input.video_uri` | string | 标准化后的视频文件 URI |
| `parameters.mode` | string | 检测模式，默认 `clean_shot` |

---

## 输出

遵循 [IO_Rule.md](../../IO_Rule.md) §2 通用成功输出 + §4.1 OmniShotCut Contract。

### shots.json

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

### artifact manifest

伴随文件 `shots.manifest.json`（由 `core/artifacts/writer.py` 自动生成）：

```json
{
  "artifact_type": "shot_boundaries",
  "schema_version": "1.0",
  "artifact_id": "artifact_xxx",
  "video_id": "video_001",
  "run_id": "run_xxx",
  "producer": {
    "model_name": "omnishotcut",
    "model_version": "1.0.0",
    "code_revision": "<git_commit>",
    "weight_revision": "<weight_identifier>"
  },
  "input": { "video_sha256": "<sha256>" },
  "output": {
    "file": "shots.json",
    "sha256": "<sha256>",
    "record_count": 842
  },
  "parameters": { "mode": "clean_shot" },
  "created_at": "ISO-8601"
}
```

### 输出校验清单

执行 [IO_Rule.md](../../IO_Rule.md) §8：

- [ ] `schema_version` = `"1.0"`
- [ ] 所有时间单位为整数毫秒
- [ ] 时间区间为 `[start_ms, end_ms)`
- [ ] 所有 `confidence` 在 `[0, 1]`
- [ ] 不存在 `action_score`、`plot_score` 字段
- [ ] artifacts URI 符合规范
- [ ] 失败时 `error.code` 使用标准错误码
- [ ] 失败时 `error.retryable` 正确设置

### 标准错误码

| 错误码 | retryable | 说明 |
|--------|-----------|------|
| `VIDEO_DECODE_FAILED` | false | FFmpeg 无法解码视频 |
| `UNSUPPORTED_FORMAT` | false | 不支持的视频格式 |
| `MODEL_CODE_ERROR` | false | 模型内部代码错误 |
| `CUDA_ERROR` | false | CUDA 环境错误 |
| `WEIGHT_INCOMPATIBLE` | false | 权重与代码版本不兼容 |
| `NETWORK_ERROR` | true | 临时网络错误 |
| `STORAGE_TIMEOUT` | true | 对象存储超时 |

---

## 时间单位

遵循 [IO_Rule.md](../../IO_Rule.md) §5：

- 所有时间为 **整数毫秒**（`start_ms`、`end_ms`）
- 时间区间：**`[start_ms, end_ms)`** — 含 start，不含 end
- FPS 保存为分数：`fps_num` / `fps_den`（如 24000/1001）
- 可额外保存：`start_frame`、`end_frame_exclusive`、可读时间码
- **禁止**将浮点秒作为唯一时间依据

---

## 区间规则

```text
[start_ms, end_ms)

示例：
  shot_1 = [0, 4280)      — 从 0ms 开始，持续到 4280ms（不含）
  shot_2 = [4280, 7200)    — 下一个 shot 从 4280ms 开始
```

Shot 之间无间隙，前一个 shot 的 `end_ms` 等于后一个 shot 的 `start_ms`。

---

## 第三方代码

| 项目 | 值 |
|------|-----|
| **repository** | `TBD — 待确定仓库地址` |
| **fixed commit** | `TBD — 接入时固定` |
| **integration method** | 按 `third_party/README.md` 方案选择（推荐方案 1：固定 Commit pip install） |
| **code license** | `unknown — 接入前必须核验` |

---

## 权重

| 项目 | 值 |
|------|-----|
| **source** | `TBD — 待确定权重下载地址` |
| **checksum (SHA256)** | `TBD — 下载后生成` |
| **license** | `unknown — 接入前必须核验` |
| **local path** | `model_store/omnishotcut/1.0.0/model.pth` |

权重文件禁止提交到 Git（见 `.gitignore`）。

---

## 当前状态

**NOT_INSTALLED**

```text
NOT_INSTALLED → SPIKE → TESTING → READY
     ↑ 当前
```

| 阶段 | 含义 |
|------|------|
| `NOT_INSTALLED` | 第三方仓库未 clone，权重未下载，Adapter 未编写 |
| `SPIKE` | 仓库已 clone，独立脚本跑通，正在验证 License 和输出格式 |
| `TESTING` | Adapter 已实现，Celery Task 可执行，单元测试编写中 |
| `READY` | 所有验收条件通过，可用于 Pipeline |

---

## 验收条件

- [ ] **能处理固定测试视频**：使用 `no_cut.mp4`、`hard_cut.mp4`、`multiple_cuts.mp4` 验证检测能力
- [ ] **输出通过 Shot Schema 校验**：`shots.json` 中的每条记录符合 `schemas/shot.py` Pydantic 模型
- [ ] **Celery Task 可以执行**：`workers/tasks/shot_tasks.py` 的 `detect_shots` 任务端到端跑通
- [ ] **Artifact 被登记**：
  - [ ] `shots.json` 写入规范路径 `storage://projects/{project_id}/videos/{video_id}/artifacts/omnishotcut/{version}/shots.json`
  - [ ] 伴随 `shots.manifest.json` 生成
  - [ ] 数据库 `artifacts` 表写入索引记录
  - [ ] 数据库 `model_runs` 表写入本次运行记录
