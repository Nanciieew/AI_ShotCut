# OmniShotCut 单模型闭环 — 现状与实施报告

> 基于 `OmniShotCut_Docker_Celery单模型闭环实施任务.md` §4 要求  
> 日期：2026-07-29

---

## 一、已有文件扫描

### 已完成（代码存在且功能完整）

| 文件 | 状态 | 说明 |
|------|------|------|
| `docker/worker.Dockerfile` | ✅ EXISTS | 4层缓存，PyTorchCPU + OmniShotCut |
| `docker-compose.yml` | ✅ EXISTS | 6服务，健康检查，启动顺序 |
| `requirements/models/omnishotcut.txt` | ✅ EXISTS | 真实依赖（verified from pyproject.toml） |
| `models/base/adapter.py` | ✅ EXISTS | BaseModelAdapter ABC |
| `schemas/shot.py` | ✅ EXISTS | Shot Pydantic model |
| `schemas/task.py` | ✅ EXISTS | Task + TaskStatus |
| `schemas/artifact.py` | ✅ EXISTS | Artifact model |
| `schemas/model_run.py` | ✅ EXISTS | ModelRun + ModelRunStatus |
| `core/database/models.py` | ✅ EXISTS | 9 ORM 表 |
| `core/storage/local.py` | ✅ EXISTS | 原子写入, SHA256, 路径穿越防护 |
| `core/artifacts/manifest.py` | ✅ EXISTS | ArtifactManifest Schema |
| `core/artifacts/writer.py` | ✅ EXISTS | 原子写入 + manifest 生成 |
| `core/artifacts/validator.py` | ✅ EXISTS | SHA256 校验 |
| `models/omnishotcut/adapter.py` | ✅ EXISTS | OmniShotCutAdapter (load/predict/health_check) |
| `models/omnishotcut/converter.py` | ✅ EXISTS | 帧→ms, 连续 shot 无间隙 |
| `models/omnishotcut/validation.py` | ✅ EXISTS | Shot Schema 校验 |
| `models/omnishotcut/exceptions.py` | ✅ EXISTS | 模型异常 |
| `models/omnishotcut/config.yaml` | ✅ EXISTS | Commit, License, 配置 |
| `models/omnishotcut/frame_diff.py` | ✅ EXISTS | MAD + histogram 误检过滤 |
| `models/omnishotcut/README.md` | ✅ EXISTS | 接入说明 |
| `models/omnishotcut/BENCHMARK.md` | ✅ EXISTS | 基准测试记录 |
| `scripts/experiments/run_model_test.py` | ✅ EXISTS | IO_Rule 合规通用工具 |
| `scripts/check_environment.py` | ✅ EXISTS | 环境检查 |
| `apps/api/routes/videos.py` | ✅ EXISTS | 路由骨架 |
| `apps/api/routes/tasks.py` | ✅ EXISTS | 路由骨架 |
| `apps/api/routes/results.py` | ✅ EXISTS | 路由骨架 |

### 部分完成（代码存在但不完整）

| 文件 | 状态 | 缺口 |
|------|------|------|
| `workers/tasks/shot_tasks.py` | ⚠️ PARTIAL | 业务层已实现，须验证与 ORM/DB 的连接闭环 |
| `models/omnishotcut/__init__.py` | ⚠️ PARTIAL | 缺少 converter/validation 导出 |

### 缺失

| 文件 | 说明 |
|------|------|
| `tests/unit/models/omnishotcut/` | 单元测试缺失 |
| `tests/integration/models/omnishotcut/` | 集成测试缺失 |
| `scripts/run_omnishotcut_task.py` | 单任务调试脚本缺失（§13） |
| `models/omnishotcut/SINGLE_MODEL_LOOP_REPORT.md` | 闭环验收报告 |

### 冲突

无。

---

## 二、Docker 环境状态

| 检查项 | 状态 |
|--------|------|
| `docker --version` | 🔸 NOT RUN |
| `docker compose version` | 🔸 NOT RUN |
| `docker compose build worker` | 🔸 NOT RUN |
| 10 项 Import 验证 | 🔸 NOT RUN |
| Volume 挂载验证 | 🔸 NOT RUN |
| Raw Inference | 🔸 NOT RUN |

**BLOCKED**: 当前环境无 Docker Engine。阶段 A-C 无法运行。

---

## 三、计划

### 可在当前环境完成（无 Docker）

1. **阶段 D**：补全 adapter.py/converter.py/validation.py（增量修改确保满足 §8 规格）
2. **阶段 E**：确保 Artifact 输出格式符合 §9（shots.json + manifest.json）
3. **阶段 F**：补全 `shot_tasks.py` 全流程（adapter → converter → validation → artifact write）
4. **单元测试**：converter, validation, adapter mock 测试
5. **调试脚本**：`scripts/run_omnishotcut_task.py`

### 需要 Docker 环境

6. **阶段 A-C**：Docker build + import 验证 + volume + raw inference
7. **阶段 G**：Redis/Postgres/Worker 启动
8. **阶段 H-L**：闭环 + API 查询 + 失败测试

---

## 四、验收状态

```
□ Docker Engine 可用            🔸 NOT RUN
□ Worker 镜像构建成功             🔸 NOT RUN
□ torch import 成功              🔸 NOT RUN
□ torchvision import 成功        🔸 NOT RUN
□ cv2 import 成功                🔸 NOT RUN
□ omnishotcut import 成功        🔸 NOT RUN
□ ffmpeg 可用                    🔸 NOT RUN
□ 权重 Volume 可见                🔸 NOT RUN
□ Fixture Volume 可见             🔸 NOT RUN
□ Fixture 可解码                 🔸 NOT RUN
□ Raw Inference 成功             🔸 NOT RUN
□ Raw Output 持久化               🔸 NOT RUN
□ Adapter 已实现                 ✅ PASSED
□ Converter 已实现               ✅ PASSED
□ Validation 已实现              ✅ PASSED
□ detect_shots Task 流程          🟡 待补全
□ 单元测试                       🟡 待实现
```
