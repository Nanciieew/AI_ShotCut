# Movie Analysis Platform

多模型视频分析后端 — 电影镜头切分、场景合并、多模态特征分析与 Scene Score 计算。

## 技术栈

- **API**: FastAPI
- **任务队列**: Celery + Redis
- **数据库**: PostgreSQL（生产）/ SQLite（开发）
- **视频处理**: FFmpeg
- **模型运行**: PyTorch / Python
- **容器化**: Docker Compose

## 快速启动

### 1. 克隆并配置环境

```bash
cp .env.example .env
# 编辑 .env 填入实际值（开发环境可使用默认值）
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
# 启动 Redis、PostgreSQL、API、Worker
docker-compose up -d

# 或者本地开发模式（需要本地 Redis）
redis-server &
celery -A workers.celery_app worker --loglevel=info &
uvicorn apps.api.main:app --reload
```

### 4. 初始化数据库

```bash
python scripts/initialize_database.py
```

### 5. 检查环境

```bash
python scripts/check_environment.py
```

### 6. 验证

```bash
curl http://localhost:8000/health
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/v1/videos` | 上传视频 |
| `GET` | `/api/v1/videos/{id}` | 获取视频信息 |
| `POST` | `/api/v1/videos/{id}/analysis` | 启动分析 |
| `GET` | `/api/v1/tasks/{id}` | 查询任务状态 |
| `GET` | `/api/v1/videos/{id}/results` | 获取分析结果 |

## 项目结构

参见 [多模型视频分析后端架构与实施规范](多模型视频分析后端架构与实施规范.md)。

## 开发规范

- 开始任务前阅读 [CLAUDE.md](CLAUDE.md)
- 问题与改进跟踪在 [IMPROVEMENTS.md](IMPROVEMENTS.md)
- 模型接入遵守 [输入输出规范.md](输入输出规范.md)

## License

MIT
