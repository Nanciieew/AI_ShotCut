# VLM 场景边界检测 — 最终方案

## Shot → Boundary 索引规则

```
shots.json:  [shot_000001, shot_000002, ..., shot_00000N]

shot_000001 → 边界 #1  = shot_000001 之后的那个切换点 (001→002)
shot_000002 → 边界 #2  = shot_000002 之后的那个切换点 (002→003)
...
shot_00000N → 无边界 (最后一 shot, 不参与计算)

所以 N 个 shot → N-1 个边界需要打分。
边界 ID = 它前面的 shot 的 shot_id。
```

**VLM / LLM 全部使用 shot_id 作为边界标识符，保证全链路一致。**

## 完整流水线

```
原始视频
  → video.normalize → normalized.mp4                         (FFmpeg stream copy, 本地)
  → shot.detect → shots.json (N shots)                       (OmniShotCut, 本地)
  → subtitle.transcribe → subtitles.json                     (Whisper base, 本地)
  → scene.detect_boundaries → scene_boundaries.json           (VLM + LLM, API)
       ├── Step A: VLM 打 location 分 + character 分 (按 shot_id)
       ├── Step B: LLM 事件分割 → plot 分 (按 shot_id)
       ├── Step C: 加权 → scene_score (按 shot_id)
       └── Step D: Greedy 选点 → 最终分段
  → 输出分段时间戳
```

**本地步骤全部 $0。仅 Step A (VLM) + Step B (LLM) 有 API 成本。**

---

## Step A: VLM — Location + Character 打分

### 输入

| 字段 | 说明 | 格式 |
|------|------|------|
| 边界帧对 | 每个 shot_id 对应边界两侧的帧 (end-of-A + start-of-B) | 320×180 JPEG |
| 批次数 | N-1 个边界 → 每批 200 个 | 约 10 批 (2h 电影) |
| 声纹参考 | 每个边界两侧的声纹 cos 值 | float [0,1] |
| shot 索引 | `shot_id → 该 shot 之后的那个边界` | 例: shot_000001 → 边界 001→002 |

### 运算任务

VLM 对每个 shot 边界同时输出两维分数：

```
维度 1: location 变化 (0-100)
  0  = 完全同一场所
  100 = 完全不同场所
  
  判断标准: 室内/室外, 房间类型, 光照环境, 空间布局

维度 2: character GROUP 变化 (0-100)
  0  = 同一组人物 (只是镜头角度变化)
  100 = 完全换了另一组人
  
  判断标准:
    ✅ 两个人在讲话 → 一个人走路             = character group 变化
    ✅ 三个人开会 → 完全换成另三个人          = character group 变化
    ✅ 有人 → 无人                           = character group 变化
    ❌ 两个人在讲话, 切到其中一人的特写 → 再切回双人     = 不算变化
    ❌ 同一群人, 换了一个机位                = 不算变化
```

### 输出

```json
{
  "video_id": "video_001",
  "scores": [
    {
      "shot_id": "shot_000105",
      "location_change": 92,
      "character_group_change": 15,
      "reason": "shot_000105→shot_000106: 室内办公室→户外街道。同一组人物未变。"
    }
  ]
}
```

**注意**: `shot_id` = 边界前面的 shot。`shot_000105` 表示 "shot_000105 和 shot_000106 之间的边界"。最后一 shot 不出现在输出中。

### Prompt 模板

```
"你是电影分析助手。以下是同一部电影的 {N} 个镜头边界。
 逐一比较每个边界的两个画面，输出两个分数 (0-100):

 LOCATION_CHANGE (场所变化):
   0 = 同一场所。100 = 完全不同场所。
   考虑: 室内/室外, 房间类型, 光照, 空间布局。

 CHARACTER_GROUP_CHANGE (人物群体变化):
   0 = 同一组人 (只是机位切换或特写交替)。
   100 = 完全换了另一组人 (或从有人变无人)。
   ⚠️ 重要: 两个人在讲话 → 切到其中一人特写 → 不算变化。
            多人在同一场景 → 换个角度拍 → 不算变化。

 同时参考声纹相似度 (cos): {cos_values}
 cos接近1 = 同一个人说话。cos接近0 = 不同人说话。

 输出 JSON 数组, 每个边界一个对象。
 确保所有分数跨边界可比。"
```

### 后处理

```python
for b in vlm_output["scores"]:
    b["location_change"] = (b["location_change"] - min_loc) / (max_loc - min_loc) * 100
    b["character_group_change"] = (b["character_group_change"] - min_char) / (max_char - min_char) * 100
```

---

## Step B: LLM — Plot 事件分割打分

### 输入

| 字段 | 说明 | 格式 |
|------|------|------|
| 字幕 | Whisper 转录的完整字幕 | `[{start_ms, end_ms, text}, ...]` |
| shot 时间戳 | 每个 shot 的起止时间 | `[{shot_id, start_ms, end_ms}, ...]` |

### 运算任务

LLM 分两步完成：

**步骤 B1: 事件规划**

```
"以下是电影字幕, 带时间戳。请规划叙事事件 (大/中/小三层):

 大事件 (major): 类似剧本的'幕' (Act)
     例: 踩点、准备武器、抢劫行动、逃脱

 中事件 (medium): 大事件内的阶段
     例: 大事件'准备武器' 包含 → 决定动手、购买武器、测试武器、集合队伍

 小事件 (minor): 中事件内的节拍
     例: 中事件'购买武器' 包含 → 到达黑市、讨价还价、验货、成交

 输出每个事件的: label, level (major/medium/minor), time_range (起止时间)"
```

**步骤 B2: 对每个 shot 边界打 plot 分**

```
"以下是同一部电影的 {N} 个 shot 边界。
 结合刚才规划的事件树, 为每个边界输出 plot_change 分数 (0-100):

  0   = 事件内部 (同一个 minor 事件进行中)
  30  = 小事件切换 (minor → minor, 比如讨价还价→验货)
  60  = 中事件切换 (medium → medium, 比如购买武器→测试武器)
  100 = 大事件切换 (major → major, 比如准备→行动)

 提示: 同时参考 shot 时间戳, 每个边界落在哪个事件区间是已知的。
        不需要重新推理, 只需输出分数。"
```

### 输出

```json
{
  "events": [
    {"label": "抢劫行动", "level": "major", "time_range": {"start_ms": 0, "end_ms": 600000}},
    {"label": "闯入银行", "level": "medium", "time_range": {"start_ms": 300000, "end_ms": 480000}}
  ],
  "plot_scores": [
    {"shot_id": "shot_000105", "plot_change": 85},
    {"shot_id": "shot_000200", "plot_change": 10}
  ]
}
```

**注意**: `shot_id` = 边界前面的 shot, 与 VLM 输出一致。LLM 也使用相同规则。

---

## Step C: 加权 → scene_score

VLM 的 location/character 分数和 LLM 的 plot 分数按 `shot_id` 合并：

```python
# 可调权重
W_LOCATION  = 0.40
W_CHARACTER = 0.25
W_PLOT      = 0.35

# 按 shot_id 合并 VLM + LLM 输出
boundaries = {}  # key = shot_id
for s in vlm_scores:
    boundaries[s["shot_id"]] = {"location": s["location_change"],
                                 "character": s["character_group_change"]}
for s in plot_scores:
    if s["shot_id"] in boundaries:
        boundaries[s["shot_id"]]["plot"] = s["plot_change"]

# 加权计算
for shot_id, dims in boundaries.items():
    scene_score = (
        W_LOCATION  * dims.get("location", 0) +
        W_CHARACTER * dims.get("character", 0) +
        W_PLOT      * dims.get("plot", 0)
    ) / 100.0  # → [0, 1]
    dims["scene_score"] = scene_score
    dims["shot_id"] = shot_id

# 转为列表, 按分数降序
ranked = sorted(boundaries.values(), key=lambda b: b["scene_score"], reverse=True)
```

---

## Step D: Greedy 选点

```python
# 参数
target_count = K          # 目标分段数
min_distance_sec = 12     # 相邻断点最小间隔

# ranked 按 scene_score 降序, 每个元素含 shot_id + timestamp
selected = []

for b in ranked:
    # 离已选点太近, 跳过
    if any(abs(b["timestamp_ms"] - s["timestamp_ms"]) < min_distance_sec * 1000
           for s in selected):
        continue
    selected.append(b)
    if len(selected) >= target_count:
        break

# 按时间排序输出分段时间戳
selected.sort(key=lambda b: b["timestamp_ms"])
```

---

## 输出：分段时间戳

```json
{
  "video_id": "video_001",
  "segments": [
    {"start_ms": 0,        "end_ms": 163000,  "boundary_shot_id": "shot_000083", "scene_score": 0.92},
    {"start_ms": 163000,   "end_ms": 440000,  "boundary_shot_id": "shot_000105", "scene_score": 0.78},
    {"start_ms": 440000,   "end_ms": 6583000, "boundary_shot_id": "shot_000130", "scene_score": 0.85}
  ],
  "parameters": {
    "weights": {"location": 0.40, "character": 0.25, "plot": 0.35},
    "min_distance_sec": 12,
    "target_count": 8
  }
}
```

每个 segment 的 `boundary_shot_id` = 触发该分段点的 shot_id（即该 shot 之后的边界被选中）。可直接追溯到 VLM/LLM 的原始打分。

---

## 代价 (2h 电影)

| 步骤 | 模型 | 调用 | 成本 |
|------|------|:---:|:---:|
| detect_shots | OmniShotCut | 本地 | $0 |
| transcribe | Whisper base | 本地 | $0 |
| Step A (location + character) | VLM (Kimi-K3) | 10 批 | ~$24 |
| Step B1 (事件规划) | LLM | 1 次 | ~$1 |
| Step B2 (plot 打分) | LLM | 1 次 | ~$1 |
| Step C+D (加权+选点) | — | 本地 | $0 |
| **总计** | | | **~$26** |

---

## 与方案 2 的对比

| | 方案 1 (shot 边界) | 方案 2 (0.2s 密集) |
|---|:---:|:---:|
| 点数 | 1,999 | 36,000 |
| 精度 | 精确在边界 | 需吸附回边界 |
| 上下文 | 可带字幕+多帧 | 36K 点无上下文 |
| 成本 | **~$26** | ~$500+ |
| 复杂度 | 简单 | 需吸附逻辑+距离阈值 |
