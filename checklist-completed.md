# AI 影片自动分段项目 Checklist

> 云端更新时间：2026-07-28T09:49:54.029Z
> 给 Claude：请保留每条任务末尾的 `<!-- id:... -->` 标记，只修改 `[ ]` 与 `[x]`。完成分析后输出完整 Markdown。

## 阶段 0：项目管理

### 文档与版本管理

#### 执行清单

- [x] 确认当前项目目标和 MVP 范围 <!-- id:task-阶段-0-项目管理-文档与版本管理-确认当前项目目标和-mvp-范围 -->
- [x] 确认系统最终只保留 `scene_score` <!-- id:task-阶段-0-项目管理-文档与版本管理-确认系统最终只保留-scene-score -->
- [x] 全局搜索并删除 `action_score` <!-- id:task-阶段-0-项目管理-文档与版本管理-全局搜索并删除-action-score -->
- [x] 全局搜索并删除 `plot_score` <!-- id:task-阶段-0-项目管理-文档与版本管理-全局搜索并删除-plot-score -->
- [x] 检查代码中不存在 action evidence <!-- id:task-阶段-0-项目管理-文档与版本管理-检查代码中不存在-action-evidence -->
- [x] 检查代码中不存在 plot evidence <!-- id:task-阶段-0-项目管理-文档与版本管理-检查代码中不存在-plot-evidence -->
- [x] 更新 `README.md` <!-- id:task-阶段-0-项目管理-文档与版本管理-更新-readme-md -->
- [x] 更新 `CLAUDE.md` <!-- id:task-阶段-0-项目管理-文档与版本管理-更新-claude-md -->
- [x] 更新 `IMPROVEMENTS.md` <!-- id:task-阶段-0-项目管理-文档与版本管理-更新-improvements-md -->
- [x] 记录今日开发内容 <!-- id:task-阶段-0-项目管理-文档与版本管理-记录今日开发内容 -->
- [x] 提交一次 Git Commit <!-- id:task-阶段-0-项目管理-文档与版本管理-提交一次-git-commit -->
- [x] 将代码推送至远程仓库 <!-- id:task-阶段-0-项目管理-文档与版本管理-将代码推送至远程仓库 -->
- [x] 给当前稳定版本添加 Git Tag <!-- id:task-阶段-0-项目管理-文档与版本管理-给当前稳定版本添加-git-tag -->

## 阶段 1：基础工程

### 项目结构

#### 执行清单

- [x] 创建完整项目目录 <!-- id:task-阶段-1-基础工程-项目结构-创建完整项目目录 -->
- [x] 创建 `apps/api` <!-- id:task-阶段-1-基础工程-项目结构-创建-apps-api -->
- [x] 创建 `core` <!-- id:task-阶段-1-基础工程-项目结构-创建-core -->
- [x] 创建 `models` <!-- id:task-阶段-1-基础工程-项目结构-创建-models -->
- [x] 创建 `workers` <!-- id:task-阶段-1-基础工程-项目结构-创建-workers -->
- [x] 创建 `pipelines` <!-- id:task-阶段-1-基础工程-项目结构-创建-pipelines -->
- [x] 创建 `schemas` <!-- id:task-阶段-1-基础工程-项目结构-创建-schemas -->
- [x] 创建 `configs` <!-- id:task-阶段-1-基础工程-项目结构-创建-configs -->
- [x] 创建 `tests` <!-- id:task-阶段-1-基础工程-项目结构-创建-tests -->
- [x] 创建 `data/projects` <!-- id:task-阶段-1-基础工程-项目结构-创建-data-projects -->
- [x] 创建 `model_store` <!-- id:task-阶段-1-基础工程-项目结构-创建-model-store -->
- [x] 创建 `third_party` <!-- id:task-阶段-1-基础工程-项目结构-创建-third-party -->

### 基础配置

#### 执行清单

- [x] 配置 `.gitignore` <!-- id:task-阶段-1-基础工程-基础配置-配置-gitignore -->
- [x] 配置 `.env.example` <!-- id:task-阶段-1-基础工程-基础配置-配置-env-example -->
- [x] 配置 `pyproject.toml` <!-- id:task-阶段-1-基础工程-基础配置-配置-pyproject-toml -->
- [x] 配置基础 `requirements.txt` <!-- id:task-阶段-1-基础工程-基础配置-配置基础-requirements-txt -->
- [x] 配置开发环境 YAML <!-- id:task-阶段-1-基础工程-基础配置-配置开发环境-yaml -->
- [x] 配置生产环境 YAML <!-- id:task-阶段-1-基础工程-基础配置-配置生产环境-yaml -->
- [x] 配置模型 YAML <!-- id:task-阶段-1-基础工程-基础配置-配置模型-yaml -->
- [x] 配置 Celery YAML <!-- id:task-阶段-1-基础工程-基础配置-配置-celery-yaml -->
- [x] 禁止使用本机绝对路径 <!-- id:task-阶段-1-基础工程-基础配置-禁止使用本机绝对路径 -->
- [x] 确认 `.env` 不会提交到 Git <!-- id:task-阶段-1-基础工程-基础配置-确认-env-不会提交到-git -->

### Docker 基础设施

#### 执行清单

- [x] 创建 API Dockerfile <!-- id:task-阶段-1-基础工程-docker-基础设施-创建-api-dockerfile -->
- [x] 创建 Worker Dockerfile <!-- id:task-阶段-1-基础工程-docker-基础设施-创建-worker-dockerfile -->
- [x] 配置 FastAPI 服务 <!-- id:task-阶段-1-基础工程-docker-基础设施-配置-fastapi-服务 -->
- [x] 配置 Redis 服务 <!-- id:task-阶段-1-基础工程-docker-基础设施-配置-redis-服务 -->
- [x] 配置 Celery Worker <!-- id:task-阶段-1-基础工程-docker-基础设施-配置-celery-worker -->
- [x] 配置 PostgreSQL <!-- id:task-阶段-1-基础工程-docker-基础设施-配置-postgresql -->
- [x] 完成 `docker-compose.yml` <!-- id:task-阶段-1-基础工程-docker-基础设施-完成-docker-compose-yml -->
- [x] 成功启动全部容器 <!-- id:task-阶段-1-基础工程-docker-基础设施-成功启动全部容器 -->
- [x] 确认 Redis 可以连接 <!-- id:task-阶段-1-基础工程-docker-基础设施-确认-redis-可以连接 -->
- [x] 确认 PostgreSQL 可以连接 <!-- id:task-阶段-1-基础工程-docker-基础设施-确认-postgresql-可以连接 -->
- [x] 确认 Celery Worker 正常注册 <!-- id:task-阶段-1-基础工程-docker-基础设施-确认-celery-worker-正常注册 -->
- [x] 确认 FastAPI 可以访问 <!-- id:task-阶段-1-基础工程-docker-基础设施-确认-fastapi-可以访问 -->

### 健康检查

#### 执行清单

- [x] 实现 `/health` <!-- id:task-阶段-1-基础工程-健康检查-实现-health -->
- [x] 实现 `/health/live` <!-- id:task-阶段-1-基础工程-健康检查-实现-health-live -->
- [x] 实现 `/health/ready` <!-- id:task-阶段-1-基础工程-健康检查-实现-health-ready -->
- [x] 健康检查包含数据库状态 <!-- id:task-阶段-1-基础工程-健康检查-健康检查包含数据库状态 -->
- [x] 健康检查包含 Redis 状态 <!-- id:task-阶段-1-基础工程-健康检查-健康检查包含-redis-状态 -->
- [x] 健康检查包含 Celery 状态 <!-- id:task-阶段-1-基础工程-健康检查-健康检查包含-celery-状态 -->
- [x] 健康检查包含 FFmpeg 状态 <!-- id:task-阶段-1-基础工程-健康检查-健康检查包含-ffmpeg-状态 -->

## 阶段 2：本地运行环境

### 基础软件

#### 执行清单

- [x] 检查 Python 版本 <!-- id:task-阶段-2-本地运行环境-基础软件-检查-python-版本 -->
- [x] 安装 FFmpeg <!-- id:task-阶段-2-本地运行环境-基础软件-安装-ffmpeg -->
- [x] 确认终端可以运行 `ffmpeg` <!-- id:task-阶段-2-本地运行环境-基础软件-确认终端可以运行-ffmpeg -->
- [x] 确认终端可以运行 `ffprobe` <!-- id:task-阶段-2-本地运行环境-基础软件-确认终端可以运行-ffprobe -->
- [x] 安装 PyTorch <!-- id:task-阶段-2-本地运行环境-基础软件-安装-pytorch -->
- [x] 检查 PyTorch 是否可导入 <!-- id:task-阶段-2-本地运行环境-基础软件-检查-pytorch-是否可导入 -->
- [x] 检查是否检测到 CUDA <!-- id:task-阶段-2-本地运行环境-基础软件-检查是否检测到-cuda -->
- [x] 记录 CPU 信息 <!-- id:task-阶段-2-本地运行环境-基础软件-记录-cpu-信息 -->
- [ ] 记录 GPU 信息 <!-- id:task-阶段-2-本地运行环境-基础软件-记录-gpu-信息 -->
- [ ] 记录内存信息 <!-- id:task-阶段-2-本地运行环境-基础软件-记录内存信息 -->
- [x] 记录 FFmpeg 版本 <!-- id:task-阶段-2-本地运行环境-基础软件-记录-ffmpeg-版本 -->
- [x] 记录 PyTorch 版本 <!-- id:task-阶段-2-本地运行环境-基础软件-记录-pytorch-版本 -->

### 环境检测脚本

#### 执行清单

- [x] 完成 `check_environment.py` <!-- id:task-阶段-2-本地运行环境-环境检测脚本-完成-check-environment-py -->
- [x] 检查 Python 环境 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-检查-python-环境 -->
- [x] 检查 PyTorch 环境 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-检查-pytorch-环境 -->
- [x] 检查 CUDA 环境 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-检查-cuda-环境 -->
- [x] 检查 FFmpeg 环境 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-检查-ffmpeg-环境 -->
- [x] 检查 Redis 连接 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-检查-redis-连接 -->
- [x] 检查数据库连接 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-检查数据库连接 -->
- [x] 输出结构化环境检测报告 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-输出结构化环境检测报告 -->
- [x] 缺失环境时输出修复建议 <!-- id:task-阶段-2-本地运行环境-环境检测脚本-缺失环境时输出修复建议 -->

## 阶段 3：Schema 与数据库

### 核心 Schema

#### 执行清单

- [x] 完成 Video Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-video-schema -->
- [x] 完成 Task Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-task-schema -->
- [x] 完成 Model Run Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-model-run-schema -->
- [x] 完成 Artifact Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-artifact-schema -->
- [x] 完成 Shot Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-shot-schema -->
- [x] 完成 Subtitle Segment Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-subtitle-segment-schema -->
- [x] 完成 Scene Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-scene-schema -->
- [x] 完成 Scene Evidence Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-scene-evidence-schema -->
- [x] 完成 Final Result Schema <!-- id:task-阶段-3-schema-与数据库-核心-schema-完成-final-result-schema -->
- [x] 所有时间字段统一为整数毫秒 <!-- id:task-阶段-3-schema-与数据库-核心-schema-所有时间字段统一为整数毫秒 -->
- [x] 所有时间区间统一为 `[start_ms, end_ms)` <!-- id:task-阶段-3-schema-与数据库-核心-schema-所有时间区间统一为-start-ms-end-ms -->
- [x] Schema 中不存在 `action_score` <!-- id:task-阶段-3-schema-与数据库-核心-schema-schema-中不存在-action-score -->
- [x] Schema 中不存在 `plot_score` <!-- id:task-阶段-3-schema-与数据库-核心-schema-schema-中不存在-plot-score -->

### 数据库

#### 执行清单

- [x] 建立 projects 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-projects-表 -->
- [x] 建立 videos 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-videos-表 -->
- [x] 建立 tasks 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-tasks-表 -->
- [x] 建立 model_runs 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-model-runs-表 -->
- [x] 建立 artifacts 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-artifacts-表 -->
- [x] 建立 shots 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-shots-表 -->
- [x] 建立 subtitle_segments 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-subtitle-segments-表 -->
- [x] 建立 scenes 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-scenes-表 -->
- [x] 建立 scene_evidence 表 <!-- id:task-阶段-3-schema-与数据库-数据库-建立-scene-evidence-表 -->
- [x] 为关键字段添加唯一约束 <!-- id:task-阶段-3-schema-与数据库-数据库-为关键字段添加唯一约束 -->
- [x] 为 Task 状态添加合法值限制 <!-- id:task-阶段-3-schema-与数据库-数据库-为-task-状态添加合法值限制 -->
- [x] 实现数据库初始化脚本 <!-- id:task-阶段-3-schema-与数据库-数据库-实现数据库初始化脚本 -->
- [x] 实现数据库 Upsert <!-- id:task-阶段-3-schema-与数据库-数据库-实现数据库-upsert -->
- [x] 配置 Alembic <!-- id:task-阶段-3-schema-与数据库-数据库-配置-alembic -->
- [x] 创建第一次数据库迁移 <!-- id:task-阶段-3-schema-与数据库-数据库-创建第一次数据库迁移 -->
- [x] 成功执行数据库迁移 <!-- id:task-阶段-3-schema-与数据库-数据库-成功执行数据库迁移 -->

## 阶段 4：Artifact 存储系统

### 本地存储

#### 执行清单

- [x] 实现 Storage 抽象接口 <!-- id:task-阶段-4-artifact-存储系统-本地存储-实现-storage-抽象接口 -->
- [x] 实现 Local Storage <!-- id:task-阶段-4-artifact-存储系统-本地存储-实现-local-storage -->
- [x] 预留 S3 Storage 接口 <!-- id:task-阶段-4-artifact-存储系统-本地存储-预留-s3-storage-接口 -->
- [x] 实现 project 路径生成 <!-- id:task-阶段-4-artifact-存储系统-本地存储-实现-project-路径生成 -->
- [x] 实现 video 路径生成 <!-- id:task-阶段-4-artifact-存储系统-本地存储-实现-video-路径生成 -->
- [x] 实现模型 Artifact 路径生成 <!-- id:task-阶段-4-artifact-存储系统-本地存储-实现模型-artifact-路径生成 -->
- [x] 路径包含 `project_id` <!-- id:task-阶段-4-artifact-存储系统-本地存储-路径包含-project-id -->
- [x] 路径包含 `video_id` <!-- id:task-阶段-4-artifact-存储系统-本地存储-路径包含-video-id -->
- [x] 路径包含模型名称 <!-- id:task-阶段-4-artifact-存储系统-本地存储-路径包含模型名称 -->
- [x] 路径包含模型版本 <!-- id:task-阶段-4-artifact-存储系统-本地存储-路径包含模型版本 -->
- [x] 禁止生成无法追踪的 `output.json` <!-- id:task-阶段-4-artifact-存储系统-本地存储-禁止生成无法追踪的-output-json -->

### Artifact 管理

#### 执行清单

- [x] 实现 Artifact Manifest <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-实现-artifact-manifest -->
- [x] 实现文件 SHA256 <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-实现文件-sha256 -->
- [x] 实现 Artifact Writer <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-实现-artifact-writer -->
- [x] 实现 Artifact Validator <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-实现-artifact-validator -->
- [x] 实现临时文件写入 <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-实现临时文件写入 -->
- [x] 实现校验后原子重命名 <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-实现校验后原子重命名 -->
- [x] Artifact 信息写入数据库 <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-artifact-信息写入数据库 -->
- [x] Artifact 可通过 URI 读取 <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-artifact-可通过-uri-读取 -->
- [x] 大型文件不经过 Redis <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-大型文件不经过-redis -->
- [x] 大型数组不写入 PostgreSQL <!-- id:task-阶段-4-artifact-存储系统-artifact-管理-大型数组不写入-postgresql -->

## 阶段 5：FastAPI 接口

### 视频接口

#### 执行清单

- [ ] 实现 `POST /api/v1/videos` <!-- id:task-阶段-5-fastapi-接口-视频接口-实现-post-api-v1-videos -->
- [ ] 支持上传 MP4 <!-- id:task-阶段-5-fastapi-接口-视频接口-支持上传-mp4 -->
- [ ] 校验文件扩展名 <!-- id:task-阶段-5-fastapi-接口-视频接口-校验文件扩展名 -->
- [ ] 校验文件大小 <!-- id:task-阶段-5-fastapi-接口-视频接口-校验文件大小 -->
- [ ] 自动生成 `project_id` <!-- id:task-阶段-5-fastapi-接口-视频接口-自动生成-project-id -->
- [ ] 自动生成 `video_id` <!-- id:task-阶段-5-fastapi-接口-视频接口-自动生成-video-id -->
- [ ] 保存原始视频 <!-- id:task-阶段-5-fastapi-接口-视频接口-保存原始视频 -->
- [ ] 视频信息写入数据库 <!-- id:task-阶段-5-fastapi-接口-视频接口-视频信息写入数据库 -->
- [ ] 返回上传结果 <!-- id:task-阶段-5-fastapi-接口-视频接口-返回上传结果 -->

### 任务接口

#### 执行清单

- [ ] 实现创建分析任务接口 <!-- id:task-阶段-5-fastapi-接口-任务接口-实现创建分析任务接口 -->
- [ ] 自动生成 `task_id` <!-- id:task-阶段-5-fastapi-接口-任务接口-自动生成-task-id -->
- [ ] 返回任务状态 `QUEUED` <!-- id:task-阶段-5-fastapi-接口-任务接口-返回任务状态-queued -->
- [ ] 实现 `GET /api/v1/tasks/{task_id}` <!-- id:task-阶段-5-fastapi-接口-任务接口-实现-get-api-v1-tasks-task-id -->
- [ ] 返回当前 Stage <!-- id:task-阶段-5-fastapi-接口-任务接口-返回当前-stage -->
- [ ] 返回任务进度 <!-- id:task-阶段-5-fastapi-接口-任务接口-返回任务进度 -->
- [ ] 返回错误信息 <!-- id:task-阶段-5-fastapi-接口-任务接口-返回错误信息 -->
- [ ] 返回开始时间和结束时间 <!-- id:task-阶段-5-fastapi-接口-任务接口-返回开始时间和结束时间 -->

### 结果接口

#### 执行清单

- [ ] 实现视频结果查询接口 <!-- id:task-阶段-5-fastapi-接口-结果接口-实现视频结果查询接口 -->
- [ ] 未完成时返回 `PROCESSING` <!-- id:task-阶段-5-fastapi-接口-结果接口-未完成时返回-processing -->
- [ ] 完成时返回 `result_uri` <!-- id:task-阶段-5-fastapi-接口-结果接口-完成时返回-result-uri -->
- [ ] 失败时返回结构化错误 <!-- id:task-阶段-5-fastapi-接口-结果接口-失败时返回结构化错误 -->
- [ ] API Route 中不直接执行模型 <!-- id:task-阶段-5-fastapi-接口-结果接口-api-route-中不直接执行模型 -->
- [ ] API Route 中不直接运行长时间 FFmpeg <!-- id:task-阶段-5-fastapi-接口-结果接口-api-route-中不直接运行长时间-ffmpeg -->

## 阶段 6：Celery 任务系统

### Celery 基础

#### 执行清单

- [x] 创建 `celery_app.py` <!-- id:task-阶段-6-celery-任务系统-celery-基础-创建-celery-app-py -->
- [x] 配置 Redis Broker <!-- id:task-阶段-6-celery-任务系统-celery-基础-配置-redis-broker -->
- [x] 配置 Result Backend <!-- id:task-阶段-6-celery-任务系统-celery-基础-配置-result-backend -->
- [x] 开启 `task_track_started` <!-- id:task-阶段-6-celery-任务系统-celery-基础-开启-task-track-started -->
- [x] 开启 `task_acks_late` <!-- id:task-阶段-6-celery-任务系统-celery-基础-开启-task-acks-late -->
- [x] 设置 `worker_prefetch_multiplier=1` <!-- id:task-阶段-6-celery-任务系统-celery-基础-设置-worker-prefetch-multiplier-1 -->
- [x] 开启 Worker 丢失任务重入队 <!-- id:task-阶段-6-celery-任务系统-celery-基础-开启-worker-丢失任务重入队 -->
- [x] 设置软超时 <!-- id:task-阶段-6-celery-任务系统-celery-基础-设置软超时 -->
- [x] 设置硬超时 <!-- id:task-阶段-6-celery-任务系统-celery-基础-设置硬超时 -->
- [x] 实现 Celery 测试任务 <!-- id:task-阶段-6-celery-任务系统-celery-基础-实现-celery-测试任务 -->
- [ ] 从 API 成功触发测试任务 <!-- id:task-阶段-6-celery-任务系统-celery-基础-从-api-成功触发测试任务 -->

### Task 状态

#### 执行清单

- [x] 创建任务时写入 `PENDING` <!-- id:task-阶段-6-celery-任务系统-task-状态-创建任务时写入-pending -->
- [x] 排队时写入 `QUEUED` <!-- id:task-阶段-6-celery-任务系统-task-状态-排队时写入-queued -->
- [x] 开始执行时写入 `RUNNING` <!-- id:task-阶段-6-celery-任务系统-task-状态-开始执行时写入-running -->
- [x] 成功时写入 `SUCCEEDED` <!-- id:task-阶段-6-celery-任务系统-task-状态-成功时写入-succeeded -->
- [x] 失败时写入 `FAILED` <!-- id:task-阶段-6-celery-任务系统-task-状态-失败时写入-failed -->
- [x] 重试时写入 `RETRYING` <!-- id:task-阶段-6-celery-任务系统-task-状态-重试时写入-retrying -->
- [ ] 缓存命中时写入 `SKIPPED` <!-- id:task-阶段-6-celery-任务系统-task-状态-缓存命中时写入-skipped -->
- [x] 更新任务 Stage <!-- id:task-阶段-6-celery-任务系统-task-状态-更新任务-stage -->
- [x] 更新任务进度 <!-- id:task-阶段-6-celery-任务系统-task-状态-更新任务进度 -->
- [x] 保存错误代码 <!-- id:task-阶段-6-celery-任务系统-task-状态-保存错误代码 -->
- [x] 保存错误消息 <!-- id:task-阶段-6-celery-任务系统-task-状态-保存错误消息 -->
- [x] 保存重试次数 <!-- id:task-阶段-6-celery-任务系统-task-状态-保存重试次数 -->

### 队列划分

#### 执行清单

- [x] 建立 video 队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-建立-video-队列 -->
- [x] 建立 shot 队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-建立-shot-队列 -->
- [x] 建立 subtitle 队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-建立-subtitle-队列 -->
- [x] 建立 feature 队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-建立-feature-队列 -->
- [x] 建立 scene 队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-建立-scene-队列 -->
- [x] 建立 final 队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-建立-final-队列 -->
- [x] 建立 maintenance 队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-建立-maintenance-队列 -->
- [x] 单 Worker 可监听全部队列 <!-- id:task-阶段-6-celery-任务系统-队列划分-单-worker-可监听全部队列 -->
- [x] 支持未来 CPU/GPU Worker 拆分 <!-- id:task-阶段-6-celery-任务系统-队列划分-支持未来-cpu-gpu-worker-拆分 -->

## 阶段 7：视频预处理

### FFmpeg｜核心

#### 执行清单

- [ ] 安装 FFmpeg <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-安装-ffmpeg -->
- [x] 安装 FFprobe <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-安装-ffprobe -->
- [x] 验证命令行可调用 <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-验证命令行可调用 -->
- [x] 读取视频时长 <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-读取视频时长 -->
- [x] 读取 FPS <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-读取-fps -->
- [x] 读取分辨率 <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-读取分辨率 -->
- [x] 读取音频采样率 <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-读取音频采样率 -->
- [x] 生成 `normalized.mp4` <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-生成-normalized-mp4 -->
- [x] 生成 `audio.wav` <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-生成-audio-wav -->
- [x] 生成 `metadata.json` <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-生成-metadata-json -->
- [ ] 按指定时间抽帧 <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-按指定时间抽帧 -->
- [ ] 按最终切点切分视频 <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-按最终切点切分视频 -->
- [ ] 验证切分后视频可播放 <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-验证切分后视频可播放 -->
- [x] 将 FFmpeg 封装为 Celery Task <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-将-ffmpeg-封装为-celery-task -->
- [x] 保存所有输出为 Artifact <!-- id:task-阶段-7-视频预处理-ffmpeg-核心-保存所有输出为-artifact -->

## 阶段 8：Shot Boundary Detection

### OmniShotCut｜核心｜当前最高优先级

#### 执行清单

- [x] 完成仓库调研 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-完成仓库调研 -->
- [x] 固定 Git Commit <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-固定-git-commit -->
- [x] 确认代码 License <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认代码-license -->
- [x] 确认权重 License <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认权重-license -->
- [x] 确认是否允许商用 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认是否允许商用 -->
- [x] 确认 Python 版本 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认-python-版本 -->
- [x] 确认 PyTorch 版本 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认-pytorch-版本 -->
- [x] 确认 CUDA 版本 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认-cuda-版本 -->
- [x] 确认 FFmpeg 要求 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认-ffmpeg-要求 -->
- [x] 确认是否支持 CPU 推理 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认是否支持-cpu-推理 -->
- [x] 确认预训练权重来源 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认预训练权重来源 -->
- [x] Clone 仓库 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-clone-仓库 -->
- [x] Checkout 固定 Commit <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-checkout-固定-commit -->
- [x] 安装依赖 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-安装依赖 -->
- [x] 下载模型权重 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-下载模型权重 -->
- [x] 记录权重来源 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-记录权重来源 -->
- [x] 计算权重 SHA256 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-计算权重-sha256 -->
- [x] 创建环境检查脚本 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-创建环境检查脚本 -->
- [x] 创建独立推理脚本 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-创建独立推理脚本 -->
- [x] 使用固定测试视频推理 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-使用固定测试视频推理 -->
- [x] 保存原始输出 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-保存原始输出 -->
- [x] 确认帧起止定义 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认帧起止定义 -->
- [x] 确认 End Frame 是否包含 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认-end-frame-是否包含 -->
- [x] 确认原始时间单位 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-确认原始时间单位 -->
- [x] 记录运行耗时 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-记录运行耗时 -->
- [x] 记录 CPU 内存占用 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-记录-cpu-内存占用 -->
- [x] 记录 GPU 显存占用 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-记录-gpu-显存占用 -->
- [x] 创建 `OmniShotCutAdapter` <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-创建-omnishotcutadapter -->
- [x] 实现 `load()` <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-实现-load -->
- [x] 实现 `predict()` <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-实现-predict -->
- [x] 实现 `health_check()` <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-实现-health-check -->
- [x] 实现 `unload()` <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-实现-unload -->
- [x] 将帧范围转换为整数毫秒 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-将帧范围转换为整数毫秒 -->
- [x] 输出标准 `shots.json` <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-输出标准-shots-json -->
- [x] 实现 `detect_shots` Celery Task <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-实现-detect-shots-celery-task -->
- [x] 保存 Model Run <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-保存-model-run -->
- [x] 保存 Shot Artifact <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-保存-shot-artifact -->
- [x] 写入 shots 数据表 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-写入-shots-数据表 -->
- [x] 实现 Cache Key <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-实现-cache-key -->
- [x] 完成 Adapter 单元测试 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-完成-adapter-单元测试 -->
- [x] 完成 Celery 集成测试 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-完成-celery-集成测试 -->
- [x] 完成固定视频回归测试 <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-完成固定视频回归测试 -->
- [x] 加入完整 Pipeline <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-加入完整-pipeline -->
- [x] 上传 MP4 后异步得到 `shots.json` <!-- id:task-阶段-8-shot-boundary-detection-omnishotcut-核心-当前最高优先级-上传-mp4-后异步得到-shots-json -->

### TransNet V2｜重点模型

#### 执行清单

- [ ] 调研官方仓库 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-调研官方仓库 -->
- [ ] 固定 Commit <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-固定-commit -->
- [ ] 确认运行依赖 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-确认运行依赖 -->
- [ ] 确认 TensorFlow 版本 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-确认-tensorflow-版本 -->
- [ ] 下载预训练权重 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-下载预训练权重 -->
- [ ] 使用固定视频运行 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-使用固定视频运行 -->
- [ ] 获取逐帧转场概率 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-获取逐帧转场概率 -->
- [ ] 将概率转换为边界 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-将概率转换为边界 -->
- [ ] 统一输出整数毫秒 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-统一输出整数毫秒 -->
- [ ] 创建 `TransNetV2Adapter` <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-创建-transnetv2adapter -->
- [ ] 输出标准 Shot Schema <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-输出标准-shot-schema -->
- [ ] 创建 Celery Task <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-创建-celery-task -->
- [ ] 保存独立检测结果 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-保存独立检测结果 -->
- [ ] 与 OmniShotCut 输出对比 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-与-omnishotcut-输出对比 -->
- [ ] 加入多模型聚类 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-加入多模型聚类 -->
- [ ] 计算 detector support ratio <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-计算-detector-support-ratio -->
- [ ] 完成回归测试 <!-- id:task-阶段-8-shot-boundary-detection-transnet-v2-重点模型-完成回归测试 -->

### PySceneDetect｜重点模型

#### 执行清单

- [ ] 安装 PySceneDetect <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-安装-pyscenedetect -->
- [ ] 测试 ContentDetector <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-测试-contentdetector -->
- [ ] 测试 AdaptiveDetector <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-测试-adaptivedetector -->
- [ ] 确定默认检测器 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-确定默认检测器 -->
- [ ] 确定默认阈值 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-确定默认阈值 -->
- [ ] 使用固定测试视频运行 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-使用固定测试视频运行 -->
- [ ] 输出镜头时间点 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-输出镜头时间点 -->
- [ ] 创建 `PySceneDetectAdapter` <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-创建-pyscenedetectadapter -->
- [ ] 转换为标准 Shot Schema <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-转换为标准-shot-schema -->
- [ ] 创建 Celery Task <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-创建-celery-task -->
- [ ] 保存原始检测结果 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-保存原始检测结果 -->
- [ ] 与 OmniShotCut 输出对比 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-与-omnishotcut-输出对比 -->
- [ ] 加入多模型聚类 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-加入多模型聚类 -->
- [ ] 完成 CPU 回归测试 <!-- id:task-阶段-8-shot-boundary-detection-pyscenedetect-重点模型-完成-cpu-回归测试 -->

### Google Cloud Video Intelligence｜远期备选

#### 执行清单

- [ ] 创建 Google Cloud 项目 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-创建-google-cloud-项目 -->
- [ ] 开通 Video Intelligence API <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-开通-video-intelligence-api -->
- [ ] 配置 API 凭证 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-配置-api-凭证 -->
- [ ] 凭证加入 `.gitignore` <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-凭证加入-gitignore -->
- [ ] 测试视频上传 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-测试视频上传 -->
- [ ] 调用 Shot Change Detection <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-调用-shot-change-detection -->
- [ ] 解析云端异步任务状态 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-解析云端异步任务状态 -->
- [ ] 解析 Shot 时间范围 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-解析-shot-时间范围 -->
- [ ] 创建 Google Video Adapter <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-创建-google-video-adapter -->
- [ ] 创建 Celery Task <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-创建-celery-task -->
- [ ] 处理网络错误 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-处理网络错误 -->
- [ ] 处理 API 超时 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-处理-api-超时 -->
- [ ] 记录调用成本 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-记录调用成本 -->
- [ ] 保存原始云端结果 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-保存原始云端结果 -->
- [ ] 加入多模型聚类 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-加入多模型聚类 -->
- [ ] 完成隐私与商用检查 <!-- id:task-阶段-8-shot-boundary-detection-google-cloud-video-intelligence-远期备选-完成隐私与商用检查 -->

### Shot Boundary 多模型聚类｜核心逻辑

#### 执行清单

- [ ] 支持同时启用多个 Shot 模型 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-支持同时启用多个-shot-模型 -->
- [ ] 分别保存各模型原始输出 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-分别保存各模型原始输出 -->
- [ ] 配置模型启用开关 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-配置模型启用开关 -->
- [ ] 配置边界合并容差 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-配置边界合并容差 -->
- [ ] 默认容差为 200 毫秒 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-默认容差为-200-毫秒 -->
- [ ] 将临近边界聚为一组 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-将临近边界聚为一组 -->
- [ ] 使用加权中位数生成统一时间 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-使用加权中位数生成统一时间 -->
- [ ] 记录每个检测器原始时间 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-记录每个检测器原始时间 -->
- [ ] 计算 `detector_support_ratio` <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-计算-detector-support-ratio -->
- [ ] 输出统一 Shot Boundary <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-输出统一-shot-boundary -->
- [ ] 验证模型数量变化时比例正确 <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-验证模型数量变化时比例正确 -->
- [ ] support ratio 不直接参与 Scene Score <!-- id:task-阶段-8-shot-boundary-detection-shot-boundary-多模型聚类-核心逻辑-support-ratio-不直接参与-scene-score -->

## 阶段 9：字幕与语音识别

### 字幕文件解析器｜核心

#### 执行清单

- [ ] 支持 SRT <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-支持-srt -->
- [ ] 支持 ASS <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-支持-ass -->
- [ ] 支持 WebVTT <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-支持-webvtt -->
- [ ] 支持 MP4 内嵌字幕 <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-支持-mp4-内嵌字幕 -->
- [ ] 实现字幕来源优先级 <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-实现字幕来源优先级 -->
- [ ] 提取开始时间 <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-提取开始时间 -->
- [ ] 提取结束时间 <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-提取结束时间 -->
- [ ] 清洗字幕文本 <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-清洗字幕文本 -->
- [ ] 时间统一为整数毫秒 <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-时间统一为整数毫秒 -->
- [ ] 输出 `subtitles.json` <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-输出-subtitles-json -->
- [ ] 有字幕时跳过 ASR <!-- id:task-阶段-9-字幕与语音识别-字幕文件解析器-核心-有字幕时跳过-asr -->

### Qwen3-ASR-1.7B｜重点模型

#### 执行清单

- [ ] 调研模型与官方地址 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-调研模型与官方地址 -->
- [ ] 确认运行环境 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-确认运行环境 -->
- [ ] 下载模型权重 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-下载模型权重 -->
- [ ] 使用中文测试音频运行 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-使用中文测试音频运行 -->
- [ ] 使用英文测试音频运行 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-使用英文测试音频运行 -->
- [ ] 检查长音频支持方式 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-检查长音频支持方式 -->
- [ ] 确认是否需要切块 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-确认是否需要切块 -->
- [ ] 创建 Qwen ASR Adapter <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-创建-qwen-asr-adapter -->
- [ ] 输出标准 Subtitle Segment <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-输出标准-subtitle-segment -->
- [ ] 保存语言信息 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-保存语言信息 -->
- [ ] 保存文本置信度 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-保存文本置信度 -->
- [ ] 创建 Celery Task <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-创建-celery-task -->
- [ ] 保存字幕 Artifact <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-保存字幕-artifact -->
- [ ] 与已有字幕对齐测试 <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-与已有字幕对齐测试 -->
- [ ] 加入字幕 Pipeline <!-- id:task-阶段-9-字幕与语音识别-qwen3-asr-1-7b-重点模型-加入字幕-pipeline -->

### Qwen3-ForcedAligner-0.6B｜重点配套模型

#### 执行清单

- [ ] 调研输入要求 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-调研输入要求 -->
- [ ] 下载模型权重 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-下载模型权重 -->
- [ ] 使用音频与文本完成测试 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-使用音频与文本完成测试 -->
- [ ] 输出词级时间戳 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-输出词级时间戳 -->
- [ ] 输出句级时间戳 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-输出句级时间戳 -->
- [ ] 检查长视频累计漂移 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-检查长视频累计漂移 -->
- [ ] 创建 Forced Aligner Adapter <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-创建-forced-aligner-adapter -->
- [ ] 转换为 Subtitle Schema <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-转换为-subtitle-schema -->
- [ ] 创建 Celery Task <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-创建-celery-task -->
- [ ] 与 Qwen ASR 串联 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-与-qwen-asr-串联 -->
- [ ] 对齐失败时回退 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-对齐失败时回退 -->
- [ ] 保存对齐前后差异 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-保存对齐前后差异 -->
- [ ] 完成回归测试 <!-- id:task-阶段-9-字幕与语音识别-qwen3-forcedaligner-0-6b-重点配套模型-完成回归测试 -->

### Whisper｜备选模型

#### 执行清单

- [ ] 确定 Whisper 实现版本 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-确定-whisper-实现版本 -->
- [ ] 确定模型大小 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-确定模型大小 -->
- [ ] 下载模型权重 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-下载模型权重 -->
- [ ] 使用固定测试音频运行 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-使用固定测试音频运行 -->
- [ ] 开启 word timestamps <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-开启-word-timestamps -->
- [ ] 测试中文识别 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-测试中文识别 -->
- [ ] 测试英文识别 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-测试英文识别 -->
- [ ] 测试长视频时间漂移 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-测试长视频时间漂移 -->
- [ ] 创建 `WhisperAdapter` <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-创建-whisperadapter -->
- [ ] 输出标准 `subtitles.json` <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-输出标准-subtitles-json -->
- [ ] 创建 Celery Task <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-创建-celery-task -->
- [ ] 保存 Model Run <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-保存-model-run -->
- [ ] 与 Qwen ASR 对比 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-与-qwen-asr-对比 -->
- [ ] 设置 ASR 模型切换配置 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-设置-asr-模型切换配置 -->
- [ ] 完成回归测试 <!-- id:task-阶段-9-字幕与语音识别-whisper-备选模型-完成回归测试 -->

## 阶段 10：音频理解与特征

### DSP 音频特征｜核心

#### 执行清单

- [ ] 提取 RMS <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-提取-rms -->
- [ ] 配置 RMS 窗口 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-配置-rms-窗口 -->
- [ ] 检测静音开始 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-检测静音开始 -->
- [ ] 检测静音结束 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-检测静音结束 -->
- [ ] 检测长停顿 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-检测长停顿 -->
- [ ] 检测音量突变 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-检测音量突变 -->
- [ ] 计算语音占比 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-计算语音占比 -->
- [ ] 标记非语音区间 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-标记非语音区间 -->
- [ ] 时间统一为整数毫秒 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-时间统一为整数毫秒 -->
- [ ] 保存音频特征矩阵 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-保存音频特征矩阵 -->
- [ ] 创建 Feature Manifest <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-创建-feature-manifest -->
- [ ] 创建 Celery Task <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-创建-celery-task -->
- [ ] 加入 Scene 特征构建 <!-- id:task-阶段-10-音频理解与特征-dsp-音频特征-核心-加入-scene-特征构建 -->

### SenseVoiceSmall｜重点模型

#### 执行清单

- [ ] 调研 SenseVoiceSmall <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-调研-sensevoicesmall -->
- [ ] 确认支持的音频事件类别 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-确认支持的音频事件类别 -->
- [ ] 下载模型权重 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-下载模型权重 -->
- [ ] 使用语音测试音频运行 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-使用语音测试音频运行 -->
- [ ] 使用音乐测试音频运行 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-使用音乐测试音频运行 -->
- [ ] 使用环境声测试音频运行 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-使用环境声测试音频运行 -->
- [ ] 测试多人重叠语音 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-测试多人重叠语音 -->
- [ ] 创建 SenseVoice Adapter <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-创建-sensevoice-adapter -->
- [ ] 输出声音类别与时间范围 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-输出声音类别与时间范围 -->
- [ ] 创建 Celery Task <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-创建-celery-task -->
- [ ] 保存 Audio Event Artifact <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-保存-audio-event-artifact -->
- [ ] 对齐 Shot 时间轴 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-对齐-shot-时间轴 -->
- [ ] 将音频变化转为 Scene Evidence <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-将音频变化转为-scene-evidence -->
- [ ] 完成回归测试 <!-- id:task-阶段-10-音频理解与特征-sensevoicesmall-重点模型-完成回归测试 -->

## 阶段 11：视觉特征与多模态理解

### 基础视觉编码器｜核心

#### 执行清单

- [ ] 定义 Visual Encoder 输入 Contract <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-定义-visual-encoder-输入-contract -->
- [ ] 定义 Visual Encoder 输出 Contract <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-定义-visual-encoder-输出-contract -->
- [ ] 实现 Shot 抽帧 <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-实现-shot-抽帧 -->
- [ ] 每个 Shot 抽取 20% 帧 <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-每个-shot-抽取-20-帧 -->
- [ ] 每个 Shot 抽取 50% 帧 <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-每个-shot-抽取-50-帧 -->
- [ ] 每个 Shot 抽取 80% 帧 <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-每个-shot-抽取-80-帧 -->
- [ ] 短 Shot 至少抽一帧 <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-短-shot-至少抽一帧 -->
- [ ] 将帧批量输入视觉编码器 <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-将帧批量输入视觉编码器 -->
- [ ] 输出视觉 Embedding <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-输出视觉-embedding -->
- [ ] 保存 `.npy` 或 `.npz` <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-保存-npy-或-npz -->
- [ ] 生成 Feature Manifest <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-生成-feature-manifest -->
- [ ] 创建 Adapter <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-创建-adapter -->
- [ ] 创建 Celery Task <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-创建-celery-task -->
- [ ] 验证 Embedding 可被 Scene 模型读取 <!-- id:task-阶段-11-视觉特征与多模态理解-基础视觉编码器-核心-验证-embedding-可被-scene-模型读取 -->

### Qwen2.5-VL｜重点模型

#### 执行清单

- [ ] 调研 Qwen2.5-VL <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-调研-qwen2-5-vl -->
- [ ] 确定模型尺寸 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-确定模型尺寸 -->
- [ ] 确定显存要求 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-确定显存要求 -->
- [ ] 下载模型权重 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-下载模型权重 -->
- [ ] 测试单帧输入 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-测试单帧输入 -->
- [ ] 测试多帧输入 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-测试多帧输入 -->
- [ ] 测试短视频窗口输入 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-测试短视频窗口输入 -->
- [ ] 设计固定结构化 Prompt <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-设计固定结构化-prompt -->
- [ ] 输出人物列表 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-输出人物列表 -->
- [ ] 输出地点标签 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-输出地点标签 -->
- [ ] 输出时间环境 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-输出时间环境 -->
- [ ] 输出视觉语义摘要 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-输出视觉语义摘要 -->
- [ ] 输出主角变化判断 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-输出主角变化判断 -->
- [ ] 创建 Qwen VL Adapter <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-创建-qwen-vl-adapter -->
- [ ] 强制输出 JSON <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-强制输出-json -->
- [ ] 校验 JSON Schema <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-校验-json-schema -->
- [ ] 创建 Celery Task <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-创建-celery-task -->
- [ ] 保存语义 Artifact <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-保存语义-artifact -->
- [ ] 接入 Scene Score 特征构建 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-接入-scene-score-特征构建 -->
- [ ] 完成回归测试 <!-- id:task-阶段-11-视觉特征与多模态理解-qwen2-5-vl-重点模型-完成回归测试 -->

### InternVideo2.5｜重点备选

#### 执行清单

- [ ] 调研 InternVideo2.5 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-调研-internvideo2-5 -->
- [ ] 确认输入帧数要求 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-确认输入帧数要求 -->
- [ ] 确认视频窗口长度 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-确认视频窗口长度 -->
- [ ] 确认显存要求 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-确认显存要求 -->
- [ ] 下载预训练权重 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-下载预训练权重 -->
- [ ] 使用固定视频窗口运行 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-使用固定视频窗口运行 -->
- [ ] 输出视频 Embedding <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-输出视频-embedding -->
- [ ] 测试不同 Shot 长度 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-测试不同-shot-长度 -->
- [ ] 创建 InternVideo Adapter <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-创建-internvideo-adapter -->
- [ ] 保存视觉特征 Artifact <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-保存视觉特征-artifact -->
- [ ] 创建 Celery Task <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-创建-celery-task -->
- [ ] 与基础视觉编码器对比 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-与基础视觉编码器对比 -->
- [ ] 验证是否提升 Scene Boundary <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-验证是否提升-scene-boundary -->
- [ ] 完成回归测试 <!-- id:task-阶段-11-视觉特征与多模态理解-internvideo2-5-重点备选-完成回归测试 -->

### VideoLLaMA 2｜备选模型

#### 执行清单

- [ ] 调研 VideoLLaMA 2 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-调研-videollama-2 -->
- [ ] 确认模型权重和 License <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-确认模型权重和-license -->
- [ ] 确认输入视频时长限制 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-确认输入视频时长限制 -->
- [ ] 确认显存需求 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-确认显存需求 -->
- [ ] 使用候选窗口运行测试 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-使用候选窗口运行测试 -->
- [ ] 设计结构化 Prompt <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-设计结构化-prompt -->
- [ ] 输出场景摘要 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-输出场景摘要 -->
- [ ] 输出地点变化 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-输出地点变化 -->
- [ ] 输出人物组合变化 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-输出人物组合变化 -->
- [ ] 输出视觉语义变化 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-输出视觉语义变化 -->
- [ ] 创建 VideoLLaMA Adapter <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-创建-videollama-adapter -->
- [ ] 创建 Celery Task <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-创建-celery-task -->
- [ ] 保存语义 Artifact <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-保存语义-artifact -->
- [ ] 与 Qwen2.5-VL 对比 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-与-qwen2-5-vl-对比 -->
- [ ] 决定是否采用 <!-- id:task-阶段-11-视觉特征与多模态理解-videollama-2-备选模型-决定是否采用 -->

### Claude｜语义分析备选

#### 执行清单

- [ ] 设计 Claude 输入结构 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-设计-claude-输入结构 -->
- [ ] 限制输入为候选点上下文 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-限制输入为候选点上下文 -->
- [ ] 输入候选前后关键帧描述 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输入候选前后关键帧描述 -->
- [ ] 输入前后字幕 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输入前后字幕 -->
- [ ] 输入音频事件摘要 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输入音频事件摘要 -->
- [ ] 设计结构化输出 Schema <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-设计结构化输出-schema -->
- [ ] 输出人物组合变化 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输出人物组合变化 -->
- [ ] 输出地点变化 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输出地点变化 -->
- [ ] 输出时间跳跃 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输出时间跳跃 -->
- [ ] 输出主角变化 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输出主角变化 -->
- [ ] 输出场景摘要 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-输出场景摘要 -->
- [ ] 创建 Claude Adapter <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-创建-claude-adapter -->
- [ ] 创建 Celery Task <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-创建-celery-task -->
- [ ] 处理 API 超时 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-处理-api-超时 -->
- [ ] 处理 API 限流 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-处理-api-限流 -->
- [ ] 记录 Token 使用量 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-记录-token-使用量 -->
- [ ] 记录调用成本 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-记录调用成本 -->
- [ ] Claude 不直接决定最终切点 <!-- id:task-阶段-11-视觉特征与多模态理解-claude-语义分析备选-claude-不直接决定最终切点 -->

## 阶段 12：Scene Boundary Detection

### SceneSeg｜重点模型

#### 执行清单

- [ ] 调研 SceneSeg 仓库 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-调研-sceneseg-仓库 -->
- [ ] 确认是否提供推理代码 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-确认是否提供推理代码 -->
- [ ] 确认是否提供权重 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-确认是否提供权重 -->
- [ ] 确认训练数据和 License <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-确认训练数据和-license -->
- [ ] 确认输入 Shot 特征格式 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-确认输入-shot-特征格式 -->
- [ ] 准备固定 Shot 序列输入 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-准备固定-shot-序列输入 -->
- [ ] 完成独立推理测试 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-完成独立推理测试 -->
- [ ] 输出 Scene Boundary 候选 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-输出-scene-boundary-候选 -->
- [ ] 输出 Shot-to-Scene 映射 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-输出-shot-to-scene-映射 -->
- [ ] 创建 SceneSeg Adapter <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-创建-sceneseg-adapter -->
- [ ] 转换为标准 Boundary Schema <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-转换为标准-boundary-schema -->
- [ ] 创建 Celery Task <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-创建-celery-task -->
- [ ] 保存 Scene Boundary Artifact <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-保存-scene-boundary-artifact -->
- [ ] 与人工边界对比 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-与人工边界对比 -->
- [ ] 完成回归测试 <!-- id:task-阶段-12-scene-boundary-detection-sceneseg-重点模型-完成回归测试 -->

### BaSSL｜重点模型

#### 执行清单

- [ ] 调研 BaSSL 官方仓库 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-调研-bassl-官方仓库 -->
- [ ] 固定代码 Commit <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-固定代码-commit -->
- [ ] 检查旧版 Python 依赖 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-检查旧版-python-依赖 -->
- [ ] 检查 PyTorch 版本冲突 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-检查-pytorch-版本冲突 -->
- [ ] 检查 PyTorch Lightning 版本 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-检查-pytorch-lightning-版本 -->
- [ ] 确认预训练权重 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-确认预训练权重 -->
- [ ] 确认是否只有训练代码 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-确认是否只有训练代码 -->
- [ ] 确认是否提供推理流程 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-确认是否提供推理流程 -->
- [ ] 准备 Shot 特征输入 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-准备-shot-特征输入 -->
- [ ] 运行固定测试 Shot 序列 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-运行固定测试-shot-序列 -->
- [ ] 输出 Scene Boundary 概率 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-输出-scene-boundary-概率 -->
- [ ] 创建 BaSSL Adapter <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-创建-bassl-adapter -->
- [ ] 转换为标准 Boundary Schema <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-转换为标准-boundary-schema -->
- [ ] 创建独立 Worker 环境方案 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-创建独立-worker-环境方案 -->
- [ ] 创建 Celery Task <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-创建-celery-task -->
- [ ] 保存 Artifact <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-保存-artifact -->
- [ ] 与 SceneSeg 对比 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-与-sceneseg-对比 -->
- [ ] 完成回归测试 <!-- id:task-阶段-12-scene-boundary-detection-bassl-重点模型-完成回归测试 -->

### CRCSD｜研究或备选

#### 执行清单

- [ ] 确认 CRCSD 完整名称和论文 <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-确认-crcsd-完整名称和论文 -->
- [ ] 确认是否有官方代码 <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-确认是否有官方代码 -->
- [ ] 确认是否有预训练权重 <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-确认是否有预训练权重 -->
- [ ] 确认任务是否匹配 Scene Boundary <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-确认任务是否匹配-scene-boundary -->
- [ ] 确认输入数据要求 <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-确认输入数据要求 -->
- [ ] 评估接入成本 <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-评估接入成本 -->
- [ ] 评估是否优于 SceneSeg 或 BaSSL <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-评估是否优于-sceneseg-或-bassl -->
- [ ] 决定接入或不采用 <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-决定接入或不采用 -->
- [ ] 记录决策理由 <!-- id:task-阶段-12-scene-boundary-detection-crcsd-研究或备选-记录决策理由 -->

### MovieBench｜评估参考

#### 执行清单

- [ ] 调研 MovieBench 数据定义 <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-调研-moviebench-数据定义 -->
- [ ] 确认包含哪些任务 <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-确认包含哪些任务 -->
- [ ] 确认是否适合 Scene Boundary 评估 <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-确认是否适合-scene-boundary-评估 -->
- [ ] 确认数据 License <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-确认数据-license -->
- [ ] 选择可使用的评估指标 <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-选择可使用的评估指标 -->
- [ ] 建立内部测试集映射 <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-建立内部测试集映射 -->
- [ ] 决定是否用于模型对比 <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-决定是否用于模型对比 -->
- [ ] 记录评估方案 <!-- id:task-阶段-12-scene-boundary-detection-moviebench-评估参考-记录评估方案 -->

### MovieNet｜训练与评估参考

#### 执行清单

- [ ] 调研 MovieNet 数据集 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-调研-movienet-数据集 -->
- [ ] 确认数据集 License <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-确认数据集-license -->
- [ ] 确认 Scene 标签格式 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-确认-scene-标签格式 -->
- [ ] 确认人物标签格式 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-确认人物标签格式 -->
- [ ] 确认地点标签格式 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-确认地点标签格式 -->
- [ ] 确认 Shot-to-Scene 标注 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-确认-shot-to-scene-标注 -->
- [ ] 研究训练集构建方式 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-研究训练集构建方式 -->
- [ ] 研究评价指标 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-研究评价指标 -->
- [ ] 建立自身 Schema 映射 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-建立自身-schema-映射 -->
- [ ] 决定是否用于模型微调 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-决定是否用于模型微调 -->
- [ ] 决定是否用于离线评估 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-决定是否用于离线评估 -->
- [ ] 记录不直接用于线上推理 <!-- id:task-阶段-12-scene-boundary-detection-movienet-训练与评估参考-记录不直接用于线上推理 -->

## 阶段 13：多模型 Scene Boundary 融合

### 阶段任务

#### 执行清单

- [ ] 同时读取 SceneSeg 候选 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-同时读取-sceneseg-候选 -->
- [ ] 同时读取 BaSSL 候选 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-同时读取-bassl-候选 -->
- [ ] 支持读取其他 Scene 模型候选 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-支持读取其他-scene-模型候选 -->
- [ ] 保留每个模型原始置信度 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-保留每个模型原始置信度 -->
- [ ] 保留每个模型原始时间 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-保留每个模型原始时间 -->
- [ ] 时间统一为整数毫秒 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-时间统一为整数毫秒 -->
- [ ] 候选吸附到最近 Shot Boundary <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-候选吸附到最近-shot-boundary -->
- [ ] 超过 2.5 秒时保留独立候选 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-超过-2-5-秒时保留独立候选 -->
- [ ] 合并同一 Shot Boundary 上的候选 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-合并同一-shot-boundary-上的候选 -->
- [ ] 合并时间相近的独立候选 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-合并时间相近的独立候选 -->
- [ ] 保留全部来源模型 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-保留全部来源模型 -->
- [ ] 生成统一 Candidate Schema <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-生成统一-candidate-schema -->
- [ ] 不允许单一模型直接决定最终切点 <!-- id:task-阶段-13-多模型-scene-boundary-融合-阶段任务-不允许单一模型直接决定最终切点 -->

## 阶段 14：Scene Score

### Location Change

#### 执行清单

- [ ] 定义地点标签 Schema <!-- id:task-阶段-14-scene-score-location-change-定义地点标签-schema -->
- [ ] 提取候选前地点 <!-- id:task-阶段-14-scene-score-location-change-提取候选前地点 -->
- [ ] 提取候选后地点 <!-- id:task-阶段-14-scene-score-location-change-提取候选后地点 -->
- [ ] 计算地点变化值 <!-- id:task-阶段-14-scene-score-location-change-计算地点变化值 -->
- [ ] 归一化到 `[0,1]` <!-- id:task-阶段-14-scene-score-location-change-归一化到-0-1 -->
- [ ] 保存模型来源 <!-- id:task-阶段-14-scene-score-location-change-保存模型来源 -->
- [ ] 保存置信度 <!-- id:task-阶段-14-scene-score-location-change-保存置信度 -->

### Character Set Change

#### 执行清单

- [ ] 定义人物列表 Schema <!-- id:task-阶段-14-scene-score-character-set-change-定义人物列表-schema -->
- [ ] 提取候选前人物组合 <!-- id:task-阶段-14-scene-score-character-set-change-提取候选前人物组合 -->
- [ ] 提取候选后人物组合 <!-- id:task-阶段-14-scene-score-character-set-change-提取候选后人物组合 -->
- [ ] 处理未知人物 ID <!-- id:task-阶段-14-scene-score-character-set-change-处理未知人物-id -->
- [ ] 计算人物集合差异 <!-- id:task-阶段-14-scene-score-character-set-change-计算人物集合差异 -->
- [ ] 归一化到 `[0,1]` <!-- id:task-阶段-14-scene-score-character-set-change-归一化到-0-1 -->
- [ ] 保存模型来源 <!-- id:task-阶段-14-scene-score-character-set-change-保存模型来源 -->
- [ ] 保存置信度 <!-- id:task-阶段-14-scene-score-character-set-change-保存置信度 -->

### Visual Semantic Change

#### 执行清单

- [ ] 提取候选前视觉表示 <!-- id:task-阶段-14-scene-score-visual-semantic-change-提取候选前视觉表示 -->
- [ ] 提取候选后视觉表示 <!-- id:task-阶段-14-scene-score-visual-semantic-change-提取候选后视觉表示 -->
- [ ] 计算 Embedding 距离 <!-- id:task-阶段-14-scene-score-visual-semantic-change-计算-embedding-距离 -->
- [ ] 获取多模态模型语义判断 <!-- id:task-阶段-14-scene-score-visual-semantic-change-获取多模态模型语义判断 -->
- [ ] 合并数值特征与语义判断 <!-- id:task-阶段-14-scene-score-visual-semantic-change-合并数值特征与语义判断 -->
- [ ] 归一化到 `[0,1]` <!-- id:task-阶段-14-scene-score-visual-semantic-change-归一化到-0-1 -->

### Time Jump

#### 执行清单

- [ ] 检测明确时间词 <!-- id:task-阶段-14-scene-score-time-jump-检测明确时间词 -->
- [ ] 检测字幕时间跳转 <!-- id:task-阶段-14-scene-score-time-jump-检测字幕时间跳转 -->
- [ ] 检测昼夜环境变化 <!-- id:task-阶段-14-scene-score-time-jump-检测昼夜环境变化 -->
- [ ] 获取模型时间跳跃判断 <!-- id:task-阶段-14-scene-score-time-jump-获取模型时间跳跃判断 -->
- [ ] 输出 `time_jump` <!-- id:task-阶段-14-scene-score-time-jump-输出-time-jump -->
- [ ] 归一化到 `[0,1]` <!-- id:task-阶段-14-scene-score-time-jump-归一化到-0-1 -->

### Main Character Change

#### 执行清单

- [ ] 定义主角判断规则 <!-- id:task-阶段-14-scene-score-main-character-change-定义主角判断规则 -->
- [ ] 识别候选前主要人物 <!-- id:task-阶段-14-scene-score-main-character-change-识别候选前主要人物 -->
- [ ] 识别候选后主要人物 <!-- id:task-阶段-14-scene-score-main-character-change-识别候选后主要人物 -->
- [ ] 判断叙事中心是否变化 <!-- id:task-阶段-14-scene-score-main-character-change-判断叙事中心是否变化 -->
- [ ] 输出 `main_character_change` <!-- id:task-阶段-14-scene-score-main-character-change-输出-main-character-change -->
- [ ] 归一化到 `[0,1]` <!-- id:task-阶段-14-scene-score-main-character-change-归一化到-0-1 -->

### Shot Transition Strength

#### 执行清单

- [ ] 获取转场类型 <!-- id:task-阶段-14-scene-score-shot-transition-strength-获取转场类型 -->
- [ ] 获取模型置信度 <!-- id:task-阶段-14-scene-score-shot-transition-strength-获取模型置信度 -->
- [ ] 获取 TransNet 帧概率 <!-- id:task-阶段-14-scene-score-shot-transition-strength-获取-transnet-帧概率 -->
- [ ] 获取检测器支持比例 <!-- id:task-阶段-14-scene-score-shot-transition-strength-获取检测器支持比例 -->
- [ ] 计算统一转场强度 <!-- id:task-阶段-14-scene-score-shot-transition-strength-计算统一转场强度 -->
- [ ] 归一化到 `[0,1]` <!-- id:task-阶段-14-scene-score-shot-transition-strength-归一化到-0-1 -->
- [ ] 不单独决定 Scene Boundary <!-- id:task-阶段-14-scene-score-shot-transition-strength-不单独决定-scene-boundary -->

### Scene Score 计算

#### 执行清单

- [ ] 默认读取候选点前 15 秒 <!-- id:task-阶段-14-scene-score-scene-score-计算-默认读取候选点前-15-秒 -->
- [ ] 默认读取候选点后 15 秒 <!-- id:task-阶段-14-scene-score-scene-score-计算-默认读取候选点后-15-秒 -->
- [ ] 接近开头时缩短前窗口 <!-- id:task-阶段-14-scene-score-scene-score-计算-接近开头时缩短前窗口 -->
- [ ] 接近结尾时缩短后窗口 <!-- id:task-阶段-14-scene-score-scene-score-计算-接近结尾时缩短后窗口 -->
- [ ] 记录有效上下文长度 <!-- id:task-阶段-14-scene-score-scene-score-计算-记录有效上下文长度 -->
- [ ] 不补零 <!-- id:task-阶段-14-scene-score-scene-score-计算-不补零 -->
- [ ] 不复制帧 <!-- id:task-阶段-14-scene-score-scene-score-计算-不复制帧 -->
- [ ] 权重限制在 0–10 <!-- id:task-阶段-14-scene-score-scene-score-计算-权重限制在-0-10 -->
- [ ] 检查权重总和大于 0 <!-- id:task-阶段-14-scene-score-scene-score-计算-检查权重总和大于-0 -->
- [ ] 实现权重归一化 <!-- id:task-阶段-14-scene-score-scene-score-计算-实现权重归一化 -->
- [ ] 实现加权求和 <!-- id:task-阶段-14-scene-score-scene-score-计算-实现加权求和 -->
- [ ] 最终分数限制在 `[0,1]` <!-- id:task-阶段-14-scene-score-scene-score-计算-最终分数限制在-0-1 -->
- [ ] 输出 `scene_scores.json` <!-- id:task-阶段-14-scene-score-scene-score-计算-输出-scene-scores-json -->
- [ ] 只在 Scene 层计算 Scene Score <!-- id:task-阶段-14-scene-score-scene-score-计算-只在-scene-层计算-scene-score -->

## 阶段 15：最终切点选择

### 参数

#### 执行清单

- [ ] 配置最短片段长度 <!-- id:task-阶段-15-最终切点选择-参数-配置最短片段长度 -->
- [ ] 验证最短片段长度必须大于 12 秒 <!-- id:task-阶段-15-最终切点选择-参数-验证最短片段长度必须大于-12-秒 -->
- [ ] 支持精细切分 <!-- id:task-阶段-15-最终切点选择-参数-支持精细切分 -->
- [ ] 支持标准切分 <!-- id:task-阶段-15-最终切点选择-参数-支持标准切分 -->
- [ ] 支持粗略切分 <!-- id:task-阶段-15-最终切点选择-参数-支持粗略切分 -->
- [ ] 支持目标平均片段长度 <!-- id:task-阶段-15-最终切点选择-参数-支持目标平均片段长度 -->
- [ ] 目标平均长度必须大于最短片段长度 <!-- id:task-阶段-15-最终切点选择-参数-目标平均长度必须大于最短片段长度 -->

### 目标数量

#### 执行清单

- [ ] 删除距离影片开头过近的候选 <!-- id:task-阶段-15-最终切点选择-目标数量-删除距离影片开头过近的候选 -->
- [ ] 删除距离影片结尾过近的候选 <!-- id:task-阶段-15-最终切点选择-目标数量-删除距离影片结尾过近的候选 -->
- [ ] 计算 `valid_candidate_count` <!-- id:task-阶段-15-最终切点选择-目标数量-计算-valid-candidate-count -->
- [ ] 精细切分比例设为 60% <!-- id:task-阶段-15-最终切点选择-目标数量-精细切分比例设为-60 -->
- [ ] 标准切分比例设为 30% <!-- id:task-阶段-15-最终切点选择-目标数量-标准切分比例设为-30 -->
- [ ] 粗略切分比例设为 10% <!-- id:task-阶段-15-最终切点选择-目标数量-粗略切分比例设为-10 -->
- [ ] 计算目标切点数量 <!-- id:task-阶段-15-最终切点选择-目标数量-计算目标切点数量 -->
- [ ] 允许实际数量低于目标数量 <!-- id:task-阶段-15-最终切点选择-目标数量-允许实际数量低于目标数量 -->

### 贪心选择

#### 执行清单

- [ ] 按 `scene_score` 从高到低排序 <!-- id:task-阶段-15-最终切点选择-贪心选择-按-scene-score-从高到低排序 -->
- [ ] 选择当前最高分候选 <!-- id:task-阶段-15-最终切点选择-贪心选择-选择当前最高分候选 -->
- [ ] 删除最短片段范围内冲突候选 <!-- id:task-阶段-15-最终切点选择-贪心选择-删除最短片段范围内冲突候选 -->
- [ ] 每个冲突区间只保留最高分 <!-- id:task-阶段-15-最终切点选择-贪心选择-每个冲突区间只保留最高分 -->
- [ ] 达到目标数量后停止 <!-- id:task-阶段-15-最终切点选择-贪心选择-达到目标数量后停止 -->
- [ ] 无可用候选时停止 <!-- id:task-阶段-15-最终切点选择-贪心选择-无可用候选时停止 -->
- [ ] 最终切点按时间排序 <!-- id:task-阶段-15-最终切点选择-贪心选择-最终切点按时间排序 -->
- [ ] 验证首段满足最短长度 <!-- id:task-阶段-15-最终切点选择-贪心选择-验证首段满足最短长度 -->
- [ ] 验证尾段满足最短长度 <!-- id:task-阶段-15-最终切点选择-贪心选择-验证尾段满足最短长度 -->
- [ ] 验证中间片段满足最短长度 <!-- id:task-阶段-15-最终切点选择-贪心选择-验证中间片段满足最短长度 -->

## 阶段 16：最终结果与视频导出

### Final Result

#### 执行清单

- [ ] 组装视频基础信息 <!-- id:task-阶段-16-最终结果与视频导出-final-result-组装视频基础信息 -->
- [ ] 组装 Shot 数据 <!-- id:task-阶段-16-最终结果与视频导出-final-result-组装-shot-数据 -->
- [ ] 组装 Scene 数据 <!-- id:task-阶段-16-最终结果与视频导出-final-result-组装-scene-数据 -->
- [ ] 组装 Scene Evidence <!-- id:task-阶段-16-最终结果与视频导出-final-result-组装-scene-evidence -->
- [ ] 组装 Scene Score <!-- id:task-阶段-16-最终结果与视频导出-final-result-组装-scene-score -->
- [ ] 组装最终切点 <!-- id:task-阶段-16-最终结果与视频导出-final-result-组装最终切点 -->
- [ ] 组装 Segment 列表 <!-- id:task-阶段-16-最终结果与视频导出-final-result-组装-segment-列表 -->
- [ ] 输出 `final_result.json` <!-- id:task-阶段-16-最终结果与视频导出-final-result-输出-final-result-json -->
- [ ] 保存 Final Result Artifact <!-- id:task-阶段-16-最终结果与视频导出-final-result-保存-final-result-artifact -->
- [ ] 最终结果可通过 API 查询 <!-- id:task-阶段-16-最终结果与视频导出-final-result-最终结果可通过-api-查询 -->

### FFmpeg 切片

#### 执行清单

- [ ] 使用 `adjusted_cut_timestamp_ms` <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-使用-adjusted-cut-timestamp-ms -->
- [ ] 将毫秒转换为 FFmpeg 时间参数 <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-将毫秒转换为-ffmpeg-时间参数 -->
- [ ] 按最终切点生成视频片段 <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-按最终切点生成视频片段 -->
- [ ] 片段命名包含顺序编号 <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-片段命名包含顺序编号 -->
- [ ] 片段命名包含起止时间 <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-片段命名包含起止时间 -->
- [ ] 验证输出片段数量 <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-验证输出片段数量 -->
- [ ] 验证输出片段总时长 <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-验证输出片段总时长 -->
- [ ] 验证输出视频可正常播放 <!-- id:task-阶段-16-最终结果与视频导出-ffmpeg-切片-验证输出视频可正常播放 -->

## 阶段 17：Pipeline 编排

### 阶段任务

#### 执行清单

- [ ] 实现 `normalize_video` <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现-normalize-video -->
- [ ] 并行执行 Shot Detection <!-- id:task-阶段-17-pipeline-编排-阶段任务-并行执行-shot-detection -->
- [ ] 并行执行字幕处理 <!-- id:task-阶段-17-pipeline-编排-阶段任务-并行执行字幕处理 -->
- [ ] 并行执行音频特征 <!-- id:task-阶段-17-pipeline-编排-阶段任务-并行执行音频特征 -->
- [ ] 实现视觉特征处理 <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现视觉特征处理 -->
- [ ] 实现场景特征组装 <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现场景特征组装 -->
- [ ] 实现 Scene Boundary Detection <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现-scene-boundary-detection -->
- [ ] 实现 Shot 合并为 Scene <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现-shot-合并为-scene -->
- [ ] 实现 Scene Score <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现-scene-score -->
- [ ] 实现最终切点选择 <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现最终切点选择 -->
- [ ] 实现 Final Result Assembly <!-- id:task-阶段-17-pipeline-编排-阶段任务-实现-final-result-assembly -->
- [ ] 使用 Celery `chain` <!-- id:task-阶段-17-pipeline-编排-阶段任务-使用-celery-chain -->
- [ ] 使用 Celery `group` <!-- id:task-阶段-17-pipeline-编排-阶段任务-使用-celery-group -->
- [ ] 使用 Celery `chord` <!-- id:task-阶段-17-pipeline-编排-阶段任务-使用-celery-chord -->
- [ ] 已完成步骤可以跳过 <!-- id:task-阶段-17-pipeline-编排-阶段任务-已完成步骤可以跳过 -->
- [ ] 失败时可定位具体 Stage <!-- id:task-阶段-17-pipeline-编排-阶段任务-失败时可定位具体-stage -->
- [ ] 失败步骤可单独重跑 <!-- id:task-阶段-17-pipeline-编排-阶段任务-失败步骤可单独重跑 -->

## 阶段 18：日志与错误处理

### 结构化日志

#### 执行清单

- [x] 日志包含 timestamp <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-timestamp -->
- [x] 日志包含 level <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-level -->
- [x] 日志包含 request_id <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-request-id -->
- [x] 日志包含 task_id <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-task-id -->
- [x] 日志包含 video_id <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-video-id -->
- [x] 日志包含 run_id <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-run-id -->
- [x] 日志包含 model <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-model -->
- [x] 日志包含 event <!-- id:task-阶段-18-日志与错误处理-结构化日志-日志包含-event -->
- [x] 完成日志记录 runtime <!-- id:task-阶段-18-日志与错误处理-结构化日志-完成日志记录-runtime -->
- [x] 完成日志记录输出数量 <!-- id:task-阶段-18-日志与错误处理-结构化日志-完成日志记录输出数量 -->
- [x] 失败日志记录 error code <!-- id:task-阶段-18-日志与错误处理-结构化日志-失败日志记录-error-code -->
- [x] 失败日志记录 retryable <!-- id:task-阶段-18-日志与错误处理-结构化日志-失败日志记录-retryable -->
- [x] 删除正式运行中的普通 `print()` <!-- id:task-阶段-18-日志与错误处理-结构化日志-删除正式运行中的普通-print -->

### 错误处理

#### 执行清单

- [ ] 定义视频解码失败错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义视频解码失败错误 -->
- [ ] 定义格式不支持错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义格式不支持错误 -->
- [ ] 定义 Schema 校验错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义-schema-校验错误 -->
- [ ] 定义模型权重错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义模型权重错误 -->
- [ ] 定义 CUDA 不可用错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义-cuda-不可用错误 -->
- [ ] 定义显存不足错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义显存不足错误 -->
- [ ] 定义磁盘空间不足错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义磁盘空间不足错误 -->
- [ ] 定义 Redis 连接错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义-redis-连接错误 -->
- [ ] 定义数据库连接错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-定义数据库连接错误 -->
- [ ] 明确允许重试的错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-明确允许重试的错误 -->
- [ ] 明确禁止重试的错误 <!-- id:task-阶段-18-日志与错误处理-错误处理-明确禁止重试的错误 -->
- [ ] 禁止无限重试 <!-- id:task-阶段-18-日志与错误处理-错误处理-禁止无限重试 -->

## 阶段 19：测试

### 单元测试

#### 执行清单

- [ ] 测试秒转毫秒 <!-- id:task-阶段-19-测试-单元测试-测试秒转毫秒 -->
- [ ] 测试帧数转毫秒 <!-- id:task-阶段-19-测试-单元测试-测试帧数转毫秒 -->
- [ ] 测试 `[start_ms, end_ms)` 规则 <!-- id:task-阶段-19-测试-单元测试-测试-start-ms-end-ms-规则 -->
- [ ] 测试 Schema 校验 <!-- id:task-阶段-19-测试-单元测试-测试-schema-校验 -->
- [ ] 测试路径生成 <!-- id:task-阶段-19-测试-单元测试-测试路径生成 -->
- [ ] 测试 Cache Key <!-- id:task-阶段-19-测试-单元测试-测试-cache-key -->
- [ ] 测试权重归一化 <!-- id:task-阶段-19-测试-单元测试-测试权重归一化 -->
- [ ] 测试 Scene Score <!-- id:task-阶段-19-测试-单元测试-测试-scene-score -->
- [ ] 测试候选点吸附 <!-- id:task-阶段-19-测试-单元测试-测试候选点吸附 -->
- [ ] 测试候选点合并 <!-- id:task-阶段-19-测试-单元测试-测试候选点合并 -->
- [ ] 测试目标切点数量 <!-- id:task-阶段-19-测试-单元测试-测试目标切点数量 -->
- [ ] 测试最短片段约束 <!-- id:task-阶段-19-测试-单元测试-测试最短片段约束 -->
- [ ] 测试错误映射 <!-- id:task-阶段-19-测试-单元测试-测试错误映射 -->

### 集成测试

#### 执行清单

- [ ] 上传固定测试视频 <!-- id:task-阶段-19-测试-集成测试-上传固定测试视频 -->
- [ ] API 成功创建任务 <!-- id:task-阶段-19-测试-集成测试-api-成功创建任务 -->
- [ ] Celery 成功接收任务 <!-- id:task-阶段-19-测试-集成测试-celery-成功接收任务 -->
- [ ] Worker 成功执行任务 <!-- id:task-阶段-19-测试-集成测试-worker-成功执行任务 -->
- [ ] Artifact 成功落盘 <!-- id:task-阶段-19-测试-集成测试-artifact-成功落盘 -->
- [ ] 数据库状态正确更新 <!-- id:task-阶段-19-测试-集成测试-数据库状态正确更新 -->
- [ ] API 可查询任务进度 <!-- id:task-阶段-19-测试-集成测试-api-可查询任务进度 -->
- [ ] API 可查询最终结果 <!-- id:task-阶段-19-测试-集成测试-api-可查询最终结果 -->
- [ ] OmniShotCut 单模型闭环通过 <!-- id:task-阶段-19-测试-集成测试-omnishotcut-单模型闭环通过 -->
- [ ] 完整 Pipeline 闭环通过 <!-- id:task-阶段-19-测试-集成测试-完整-pipeline-闭环通过 -->

### 回归测试

#### 执行清单

- [ ] 保存固定测试视频 <!-- id:task-阶段-19-测试-回归测试-保存固定测试视频 -->
- [ ] 保存预期 Shot 数量范围 <!-- id:task-阶段-19-测试-回归测试-保存预期-shot-数量范围 -->
- [ ] 保存预期 Shot 时间范围 <!-- id:task-阶段-19-测试-回归测试-保存预期-shot-时间范围 -->
- [ ] 保存预期运行状态 <!-- id:task-阶段-19-测试-回归测试-保存预期运行状态 -->
- [ ] 模型升级后重新测试 <!-- id:task-阶段-19-测试-回归测试-模型升级后重新测试 -->
- [ ] PyTorch 升级后重新测试 <!-- id:task-阶段-19-测试-回归测试-pytorch-升级后重新测试 -->
- [ ] FFmpeg 升级后重新测试 <!-- id:task-阶段-19-测试-回归测试-ffmpeg-升级后重新测试 -->
- [ ] Schema 升级后重新测试 <!-- id:task-阶段-19-测试-回归测试-schema-升级后重新测试 -->
- [ ] 对比新旧输出差异 <!-- id:task-阶段-19-测试-回归测试-对比新旧输出差异 -->
- [ ] 记录回归测试结果 <!-- id:task-阶段-19-测试-回归测试-记录回归测试结果 -->

## 阶段 20：稳定性与代码质量

### 阶段任务

#### 执行清单

- [x] 配置 Ruff <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-配置-ruff -->
- [x] 配置 MyPy <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-配置-mypy -->
- [x] 配置 pre-commit <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-配置-pre-commit -->
- [x] 配置 GitHub Actions <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-配置-github-actions -->
- [x] CI 执行 lint <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-ci-执行-lint -->
- [x] CI 执行类型检查 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-ci-执行类型检查 -->
- [x] CI 执行单元测试 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-ci-执行单元测试 -->
- [x] CI 检查数据库迁移 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-ci-检查数据库迁移 -->
- [x] CI 构建 Docker Image <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-ci-构建-docker-image -->
- [x] 实现任务取消 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-实现任务取消 -->
- [x] 实现临时文件清理 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-实现临时文件清理 -->
- [x] 实现磁盘空间检查 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-实现磁盘空间检查 -->
- [x] 实现 Worker 超时处理 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-实现-worker-超时处理 -->
- [x] 实现 GPU 显存错误处理 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-实现-gpu-显存错误处理 -->
- [x] 实现旧 Artifact 清理策略 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-实现旧-artifact-清理策略 -->
- [x] 实现模型启动健康检查 <!-- id:task-阶段-20-稳定性与代码质量-阶段任务-实现模型启动健康检查 -->

## 阶段 21：模型注册表

### Checklist

#### 执行清单

- [ ] 创建 `models/registry.yaml` <!-- id:task-阶段-21-模型注册表-checklist-创建-models-registry-yaml -->
- [ ] 注册 OmniShotCut <!-- id:task-阶段-21-模型注册表-checklist-注册-omnishotcut -->
- [ ] 注册 TransNet V2 <!-- id:task-阶段-21-模型注册表-checklist-注册-transnet-v2 -->
- [ ] 注册 PySceneDetect <!-- id:task-阶段-21-模型注册表-checklist-注册-pyscenedetect -->
- [ ] 注册 Google Video Intelligence <!-- id:task-阶段-21-模型注册表-checklist-注册-google-video-intelligence -->
- [ ] 注册 Qwen3-ASR <!-- id:task-阶段-21-模型注册表-checklist-注册-qwen3-asr -->
- [ ] 注册 Qwen3 Forced Aligner <!-- id:task-阶段-21-模型注册表-checklist-注册-qwen3-forced-aligner -->
- [ ] 注册 Whisper <!-- id:task-阶段-21-模型注册表-checklist-注册-whisper -->
- [ ] 注册 SenseVoiceSmall <!-- id:task-阶段-21-模型注册表-checklist-注册-sensevoicesmall -->
- [ ] 注册 Qwen2.5-VL <!-- id:task-阶段-21-模型注册表-checklist-注册-qwen2-5-vl -->
- [ ] 注册 InternVideo2.5 <!-- id:task-阶段-21-模型注册表-checklist-注册-internvideo2-5 -->
- [ ] 注册 VideoLLaMA 2 <!-- id:task-阶段-21-模型注册表-checklist-注册-videollama-2 -->
- [ ] 注册 Claude <!-- id:task-阶段-21-模型注册表-checklist-注册-claude -->
- [ ] 注册 SceneSeg <!-- id:task-阶段-21-模型注册表-checklist-注册-sceneseg -->
- [ ] 注册 BaSSL <!-- id:task-阶段-21-模型注册表-checklist-注册-bassl -->
- [ ] 注册 CRCSD <!-- id:task-阶段-21-模型注册表-checklist-注册-crcsd -->
- [ ] 注册 MovieNet <!-- id:task-阶段-21-模型注册表-checklist-注册-movienet -->
- [ ] 注册 MovieBench <!-- id:task-阶段-21-模型注册表-checklist-注册-moviebench -->
- [ ] 每个模型记录来源仓库 <!-- id:task-阶段-21-模型注册表-checklist-每个模型记录来源仓库 -->
- [ ] 每个模型记录固定 Commit <!-- id:task-阶段-21-模型注册表-checklist-每个模型记录固定-commit -->
- [ ] 每个模型记录代码 License <!-- id:task-阶段-21-模型注册表-checklist-每个模型记录代码-license -->
- [ ] 每个模型记录权重 License <!-- id:task-阶段-21-模型注册表-checklist-每个模型记录权重-license -->
- [ ] 每个模型记录运行状态 <!-- id:task-阶段-21-模型注册表-checklist-每个模型记录运行状态 -->

---

## 附录：Claude 补充分析（2026-07-28）

> 以下内容不在原 Checklist 中，由 Claude 根据项目实际状态补充。

### 已完成主要里程碑

| 里程碑 | 状态 |
|--------|------|
| 基础工程骨架（25 目录 / 44 文件） | ✅ |
| Alembic 数据库迁移 | ✅ |
| 分层依赖管理（base/api/worker/dev/models） | ✅ |
| Docker Compose（4 服务 + 健康检查 + migrate） | ✅ |
| 统一 Schema（8 个 Pydantic 模型） | ✅ |
| Celery 7 队列路由 | ✅ |
| Artifact Manifest 系统 | ✅ |
| 日志链路（structlog + request_id） | ✅ |
| CI（6 job） | ✅ |
| OmniShotCut SPIKE + Adapter | ✅ |
| Frame-diff 误检过滤（MAD < 5） | ✅ |
| IO_Rule 合规校验工具（run_model_test.py） | ✅ |

### 与项目计划不符的项（建议调整）

以下模型/模块存在于 Checklist 但超出 MVP 范围：

- **TransNet V2 / PySceneDetect** — OmniShotCut 替代，建议标记 Optional
- **Google Cloud Video Intelligence** — 云端依赖，建议标记 Future
- **Qwen3-ASR / Qwen3-ForcedAligner** — Whisper 为主模型，建议标记 Alternative
- **SenseVoiceSmall** — 音频辅助，建议标记 Optional
- **Qwen2.5-VL / InternVideo2.5 / VideoLLaMA2** — 视觉模型过多，建议按优先级排序
- **Claude 语义分析** — API 成本+依赖，建议标记 Phase 2
- **CRCSD / MovieBench / MovieNet** — 研究/评估用，非运行时模型，建议标记 Reference

### 已知模型限制

- OmniShotCut dissolve/wipes 盲区（128×96 分辨率）
- 无 GPU 环境，CPU 推理 22s/short_clip
- 未实际验证 Docker Compose 启动

### 下一步建议

IMP-003: Celery Task 闭环实现（API → Celery → DB → 查询）
