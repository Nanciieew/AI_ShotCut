# Expected Output Format — OmniShotCut

## 结构

```json
{
  "video": "Hard_Cut_1.mp4",
  "annotated_by": "human",
  "annotation_date": "2026-07-28",
  "tolerance_frames": 2,
  "shots": [
    {
      "index": 0,
      "start_frame_expected": 0,
      "end_frame_expected": 150,
      "boundary_type": "hard_cut",
      "description": "开场 → 第一个镜头"
    },
    {
      "index": 1,
      "start_frame_expected": 150,
      "end_frame_expected": 320,
      "boundary_type": "hard_cut",
      "description": "第二个镜头 → 切黑"
    }
  ]
}
```

## 字段说明

| 字段 | 含义 |
|------|------|
| `tolerance_frames` | 允许的帧偏差（±N 帧算命中） |
| `start_frame_expected` | 预期 shot 起始帧（含） |
| `end_frame_expected` | 预期 shot 结束帧（含），即 OmniShotCut 原始格式 |
| `boundary_type` | 转场类型：hard_cut / dissolve / wipe / none |
| `description` | 人类可读描述 |

## 验收规则

模型 raw output `[start, end]` 与 expected 对比：
- `|start - expected.start| <= tolerance` → OK
- `|end - expected.end| <= tolerance` → OK
- 两个都在容差内 → shot 命中
- 缺失 shot（模型漏检）→ false negative
- 多余 shot（模型多检）→ false positive
