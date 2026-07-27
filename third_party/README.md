# 第三方模型管理规则

第三方模型代码与自有业务代码必须分离。采用以下三种方案之一。

## 方案 1：固定 Commit 安装（推荐）

```bash
pip install git+https://github.com/org/repo.git@COMMIT_HASH
```

适合：
- 仓库可作为 Python 包安装
- 不需要修改内部源码
- 官方仓库维护正常

必须固定 Commit，不允许跟踪 `main` 或 `master`。

## 方案 2：Git Submodule

```bash
git submodule add https://github.com/org/repo.git third_party/RepoName
cd third_party/RepoName
git checkout <COMMIT_HASH>
```

适合：
- 仓库不能直接 pip 安装
- 需要读取源码
- 需要保留原仓库版本关系

## 方案 3：复制源码（默认禁止）

仅在所有以下条件同时满足时允许：
- 原仓库无法正常集成
- 必须修改源码
- License 允许
- 修改内容被完整记录
- 保留原始仓库地址
- 保留原始 Commit
- 提供 `PATCHES.md`

## 下载前检查清单

每个模型下载前必须记录：
- 仓库地址 + 固定 Commit
- 模型任务 + 输入 + 输出
- 预训练权重是否可用
- Python/PyTorch/CUDA/FFmpeg 版本要求
- GPU 显存要求
- 输出单位 + 时间单位
- 代码 License + 权重 License + 数据集 License
- 是否允许商用/署名/再分发

## 性能测试

必须记录 1 分钟视频与 10 分钟视频的：
- 耗时
- GPU 显存占用
- CPU 内存占用
- 输出大小
- 失败情况
