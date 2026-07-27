# Model Store

模型权重存储目录。权重文件不提交到 GitHub。

## 目录结构

```text
model_store/
├── omnishotcut/
│   └── 1.0.0/
│       ├── model.pth
│       └── metadata.json
├── whisper/
│   └── large-v3/
├── scene_boundary/
│   └── 0.1.0/
│       ├── model.ckpt
│       └── metadata.json
└── README.md  (this file)
```

## metadata.json 格式

```json
{
  "model_name": "omnishotcut",
  "model_version": "1.0.0",
  "source_repository": "https://github.com/org/repo",
  "source_revision": "<COMMIT_HASH>",
  "weight_file": "model.pth",
  "sha256": "<full-hash>",
  "license": "must-verify",
  "downloaded_at": "2026-07-27"
}
```

## 下载

运行下载脚本获取模型权重：

```bash
python scripts/download_models.py
```

## Git 规则

- GitHub 保存：下载脚本、配置、SHA256、版本说明、License 说明
- GitHub 不保存：模型权重、用户电影、用户数据、大型特征、`.env`、API Key、数据库文件
