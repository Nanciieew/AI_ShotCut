# 豆包 ASR + ngrok 链路修复实施方案

> 适用项目：AI_ShotCut / Movie Analysis Platform
> 目标：打通 `normalize → audio.wav Artifact → HMAC Provider URL → ngrok → FastAPI 下载端点 → 豆包 SeedASR Submit/Query → subtitles.json` 全链路。
> 范围：本方案只处理豆包 ASR 与 ngrok 文件拉取链路，不引入 Celery。

---

## 1. 当前故障结论

当前 `_transcribe()` 的核心逻辑等价于：

```python
audio_key = ".../ffmpeg_normalizer/1.0.0/audio.wav"
artifact_id = audio_key.split("/")[-1].replace(".wav", "")  # 得到 "audio"
audio_url = create_provider_url("audio")
```

最终生成类似：

```text
https://xxxx.ngrok.app/api/v1/artifacts/audio/content?token=...
```

该链路存在三个直接阻断点：

1. normalize 阶段没有生成并登记真正的 `audio.wav` Artifact。
2. `audio` 只是文件名派生字符串，不是数据库中的真实 `artifact_id`。
3. Provider URL 使用 `purpose="provider"` 签名，但下载端点只接受 `expected_purpose="download"`，因此返回 403。

此外还有以下关联问题：

- 标准化 FFmpeg 当前输出 `video.mp4`，没有单独输出豆包需要的 16 kHz 单声道音频。
- ArtifactService 目前主要面向 JSON，缺少二进制文件登记方法。
- 下载端点未根据用途实施差异化校验。
- Provider URL 默认 TTL 只有 300 秒，长音频排队或豆包延迟拉取时可能过期。
- `models/registry.yaml` 仍描述为 StaticFiles 暴露音频，与当前签名下载方案不一致。
- 豆包 Provider 内部外部请求 ID 变量仍叫 `task_id`，容易与平台 `task_id` 混淆。

---

## 2. 修复后的目标链路

```text
源视频
  ↓ normalize Workflow
normalized video.mp4
  ↓ FFmpeg 音频提取
audio.wav（PCM S16LE / 16 kHz / mono）
  ↓ 计算 sha256 + size
创建 audio.normalized Artifact（真实 artifact_id）
  ↓ ModelRunOutput(output_role="audio")
StorageService.create_provider_url(artifact_id)
  ↓ HMAC token: artifact_id + expires_at + purpose=provider + project_id
PUBLIC_BASE_URL（ngrok HTTPS）
  ↓
GET /api/v1/artifacts/{artifact_id}/content?token=...
  ↓ 验签、查 DB、解析 URI、返回 audio/wav
豆包 SeedASR Submit API
  ↓ provider_request_id
豆包 SeedASR Query 轮询
  ↓
subtitle_segments
  ↓
subtitles.json + Manifest + Artifact DB Record
```

全链路必须使用三类不同 ID：

| ID | 生成方 | 用途 |
|---|---|---|
| `task_id` | 平台 TaskService | 一次完整视频分析任务 |
| `artifact_id` | ArtifactService | 唯一标识 `audio.wav` 等 Artifact |
| `provider_request_id` | SeedASRProvider | 火山引擎 Submit/Query 请求关联 |

禁止由文件名、URI 尾部或模型名推导 `artifact_id`。

---

## 3. 数据与文件 Contract

### 3.1 音频文件要求

为豆包生成独立音频：

```text
容器：WAV
编码：PCM signed 16-bit little-endian
采样率：16000 Hz
声道：1（mono）
时间范围：[0, duration_ms)
```

建议 FFmpeg 命令：

```bash
ffmpeg -hide_banner -y -i normalized_video.mp4 \
  -vn -map 0:a:0 -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

没有音轨时应返回不可重试错误：

```text
error_code = AUDIO_STREAM_MISSING
retryable = false
```

### 3.2 文件路径

```text
data/projects/{project_id}/videos/{video_id}/tasks/{task_id}/
└── ffmpeg_normalizer/1.0.0/
    ├── video.mp4
    ├── audio.wav
    ├── probe_before.json
    ├── probe_after.json
    ├── audio.wav.manifest.json
    └── ...
```

音频 URI：

```text
storage://projects/{project_id}/videos/{video_id}/tasks/{task_id}/ffmpeg_normalizer/1.0.0/audio.wav
```

### 3.3 Artifact 记录

```text
artifact_id       = uuid.uuid4().hex
project_id        = 当前项目
video_id          = 当前视频
producer_run_id   = normalize ModelRun.run_id
artifact_type     = audio.normalized
uri               = storage://.../audio.wav
format            = wav
mime_type         = audio/wav
size_bytes        = 实际文件大小
sha256            = 实际文件 SHA-256
schema_version    = 1.0
metadata_json     = {
  sample_rate: 16000,
  channels: 1,
  codec: pcm_s16le,
  duration_ms: ...
}
```

同时写入：

```text
model_run_outputs
├── run_id = normalize_run_id
├── artifact_id = audio_artifact_id
└── output_role = audio
```

---

## 4. 分模块改造方案

## 4.1 FFmpeg：增加音频提取命令

修改：

[core/media/ffmpeg.py](D:/wnx/AI_ShotCut/core/media/ffmpeg.py)

新增：

```python
def build_asr_audio_command(input_path: str, output_path: str) -> list[str]:
    return [
        "ffmpeg", "-hide_banner", "-y",
        "-i", input_path,
        "-vn",
        "-map", "0:a:0",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path,
    ]
```

要求：

- 继续通过 `run_ffmpeg()` 执行，禁止直接使用 shell 字符串。
- 为该命令添加单元测试，核对 `-vn/-ar 16000/-ac 1/pcm_s16le`。
- 音频生成后使用 FFprobe 或 WAV 元数据读取验证采样率、声道、时长和非空文件。

## 4.2 ArtifactService：支持登记已有二进制文件

修改：

[apps/api/services/artifact_service.py](D:/wnx/AI_ShotCut/apps/api/services/artifact_service.py)

新增方法：

```python
register_file_artifact(
    *,
    project_id: str,
    video_id: str,
    task_id: str,
    model_name: str,
    model_version: str,
    run_id: str,
    filename: str,
    artifact_type: str,
    format: str,
    mime_type: str,
    output_role: str,
    metadata: dict,
) -> dict
```

该方法负责：

1. 根据统一路径找到已生成文件。
2. 确认 `run_id` 对应真实 `ModelRun`，且属于当前 `task_id/video_id`。
3. 计算 SHA-256 与文件大小。
4. 生成伴随 Manifest。
5. 创建 Artifact 数据库记录。
6. 创建 `ModelRunOutput`。
7. 返回真实的：

```json
{
  "artifact_id": "32位UUID",
  "uri": "storage://.../audio.wav",
  "sha256": "...",
  "size_bytes": 123
}
```

不得把 `audio`、`audio.wav` 或 URI 尾部当作 Artifact ID。

注意：一个 normalize ModelRun 会输出多个 Artifact，不能在第一次写 `probe_before.json` 后就把 ModelRun 标记为 `SUCCEEDED`。应由 Workflow 在所有 normalize 输出完成后统一更新 ModelRun 状态。现有 `write_artifact()` 中自动标记成功的行为应移出 ArtifactService。

## 4.3 Workflow normalize：真正生成 audio.wav

修改：

[apps/api/services/workflow_service.py](D:/wnx/AI_ShotCut/apps/api/services/workflow_service.py)

`_normalize()` 调整顺序：

```text
创建 normalize ModelRun(run_id)
→ 标准化生成 video.mp4
→ 验证 video.mp4
→ 提取 audio.wav
→ 验证 audio.wav
→ 登记 normalized video Artifact
→ 登记 audio.normalized Artifact
→ 登记 probe Artifacts
→ ModelRun SUCCEEDED
→ 返回 NormalizeOutputs
```

建议返回结构：

```python
@dataclass(frozen=True)
class NormalizeOutputs:
    normalized_video_artifact_id: str
    normalized_video_uri: str
    audio_artifact_id: str
    audio_uri: str
```

`run_pipeline()` 保存该返回值并显式传给 `_transcribe()`：

```python
normalized = self._normalize(pid, tid, vid)
...
self._transcribe(pid, tid, vid, audio_artifact_id=normalized.audio_artifact_id)
```

禁止 `_transcribe()` 再通过固定文件名猜测上游 Artifact。

同时修复 normalize 当前使用未创建 `ModelRun` 的新随机 `run_id` 登记 `normalized_video.json` 的问题；所有 normalize 输出必须使用已创建的 `normalize_run_id`。

## 4.4 Provider URL：必须使用真实 artifact_id

修改：

[core/task_storage.py](D:/wnx/AI_ShotCut/core/task_storage.py)

保持接口：

```python
create_provider_url(
    artifact_id: str,
    project_id: str,
    ttl_s: int = 1800,
) -> str
```

签名载荷：

```text
artifact_id | expires_at | provider | project_id
```

其中：

- `expires_at` 是绝对 Unix 时间戳。
- `purpose` 固定为 `provider`。
- `project_id` 必须绑定，下载时与 Artifact 数据库记录对比。
- 默认 TTL 建议 1800 秒；应覆盖豆包排队与首次拉取时间，但不应无限有效。

生成结果：

```text
{PUBLIC_BASE_URL}/api/v1/artifacts/{真实artifact_id}/content?token={HMAC_TOKEN}
```

`PUBLIC_BASE_URL` 应：

- 使用 `https://`；
- 不带结尾 `/`，或在代码中 `rstrip("/")`；
- 指向当前 FastAPI 的 ngrok Tunnel；
- 不使用 `localhost`、`127.0.0.1` 或浏览器 `blob:` URL。

## 4.5 下载端点：同时接受 download/provider 两种合法用途

修改：

[apps/api/routes/artifacts.py](D:/wnx/AI_ShotCut/apps/api/routes/artifacts.py)

当前代码写死：

```python
verify_token(token, expected_purpose="download")
```

应改为显式支持两种用途，但不能简单跳过 purpose 校验。

推荐接口：

```python
payload = verify_token(token, allowed_purposes={"download", "provider"})
```

或依次解析后按分支校验：

```text
purpose=download
  → 用户下载规则与项目权限

purpose=provider
  → 无登录 Cookie
  → HMAC、绝对过期时间、artifact_id、project_id 全部匹配
  → 仅允许模型可拉取的 Artifact 类型
```

Provider 访问必须额外限制：

```text
允许：audio.normalized
拒绝：eeg.raw、eeg.cleaned、视频原片、任意未知类型
```

共同校验步骤：

1. Token 格式正确。
2. HMAC 使用 `hmac.compare_digest()` 验证。
3. Token 未过期。
4. URL 中的 `artifact_id` 与 Token 一致。
5. Token `project_id` 与数据库 Artifact `project_id` 一致。
6. Artifact URI 来自数据库，不接收客户端文件路径。
7. StorageService 解析后仍位于 Storage Root 内。
8. 文件存在且大小大于 0。
9. 返回正确 `Content-Type: audio/wav`。

对豆包请求不应要求浏览器 Session、Cookie 或 CSRF Token，因为火山引擎只会携带 URL 中的短期 HMAC Token。

## 4.6 Token 工具：扩展 allowed purposes

修改：

[core/security/artifact_tokens.py](D:/wnx/AI_ShotCut/core/security/artifact_tokens.py)

建议将：

```python
verify_token(token, expected_purpose: str)
```

调整为：

```python
verify_token(token, allowed_purposes: set[str])
```

并验证：

- purpose 只能为 `download/provider`。
- Artifact ID 必须符合 32 位十六进制格式。
- `expires_at` 不得超过允许的最大未来时间，例如 Provider 最多 1 小时。
- Production 中 `ARTIFACT_SIGNING_SECRET` 不能为空、不能使用 `change-me-in-production`。

建议签名使用完整 SHA-256 Hex，而不是当前截断到 16 个十六进制字符。虽然 64 bit HMAC 对短期 URL 通常不易暴力破解，但没有必要主动降低签名强度。

## 4.7 Workflow transcribe：按 Artifact 查询而不是猜文件名

修改：

[apps/api/services/workflow_service.py](D:/wnx/AI_ShotCut/apps/api/services/workflow_service.py)

目标接口：

```python
def _transcribe(
    self,
    pid: str,
    tid: str,
    vid: str,
    audio_artifact_id: str,
) -> str:
```

处理步骤：

1. 查询 `Artifact(artifact_id=audio_artifact_id)`。
2. 校验 `project_id/video_id` 一致。
3. 通过 `producer_run_id → ModelRun.task_id` 校验属于当前 Task。
4. 校验 `artifact_type == "audio.normalized"`。
5. 校验物理文件存在、非空、SHA-256 可选复核。
6. 创建 Doubao ASR ModelRun。
7. 写 `ModelRunInput(run_id, audio_artifact_id, input_role="audio")`。
8. 使用真实 `audio_artifact_id` 生成 Provider URL。
9. 调用 `DoubaoASRAdapter.predict({input: {audio_url}})`。
10. 保存 `subtitles.json`、Manifest、Artifact 和 ModelRunOutput。
11. 更新 Doubao ModelRun 为 `SUCCEEDED`。

任何失败都应更新 Doubao ModelRun：

```text
status = FAILED
error_code
error_message
retryable
finished_at
```

## 4.8 SeedASR Provider：区分平台 Task ID 与外部请求 ID

修改：

[models/doubao_asr/providers/seedasr.py](D:/wnx/AI_ShotCut/models/doubao_asr/providers/seedasr.py)

将内部变量：

```python
task_id = uuid.uuid4().hex
```

重命名为：

```python
provider_request_id = uuid.uuid4().hex
```

并用于：

```http
X-Api-Request-Id: {provider_request_id}
```

日志必须同时带平台上下文中的：

```text
task_id
video_id
run_id
provider_request_id
model=doubao_asr
```

不得在错误日志中输出 `VOLC_ACCESS_TOKEN`、完整签名 Token 或完整 Provider URL 查询参数。

---

## 5. 请求与响应细节

## 5.1 ngrok 拉取请求

豆包服务器会发送类似：

```http
GET /api/v1/artifacts/4ac0.../content?token=4ac0...%7C... HTTP/1.1
Host: xxxx.ngrok-free.app
```

FastAPI 成功响应：

```http
HTTP/1.1 200 OK
Content-Type: audio/wav
Content-Length: ...
Accept-Ranges: bytes
```

需要验证火山引擎是否要求 Range；若其下载客户端发送 Range 请求，FastAPI/Starlette `FileResponse` 的当前版本应通过实际测试确认。若不支持，应补 Range 响应实现。

## 5.2 SeedASR Submit

Provider 调用：

```http
POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit
```

关键请求头：

```text
X-Api-App-Key
X-Api-Access-Key
X-Api-Resource-Id
X-Api-Request-Id
X-Api-Sequence: -1
Content-Type: application/json
```

请求体中的音频 URL 必须是上述 ngrok HTTPS URL：

```json
{
  "audio": {
    "url": "https://xxxx.ngrok.app/api/v1/artifacts/{artifact_id}/content?token=...",
    "format": "wav",
    "language": "zh-CN"
  }
}
```

## 5.3 SeedASR Query

使用相同 `provider_request_id` 调用：

```http
POST https://openspeech.bytedance.com/api/v3/auc/bigmodel/query
```

状态处理：

```text
20000000 → 完成
20000001 / 20000002 → 继续轮询
20000003 → 静音音频，返回空字幕
其他 → 失败
```

---

## 6. 配置要求

修改：

- [core/config.py](D:/wnx/AI_ShotCut/core/config.py)
- [.env.example](D:/wnx/AI_ShotCut/.env.example)

配置项：

```env
VOLC_APP_ID=
VOLC_ACCESS_TOKEN=
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
ARTIFACT_SIGNING_SECRET=<至少32字节随机值>
PROVIDER_URL_TTL_SECONDS=1800
SEEDASR_POLL_INTERVAL_SECONDS=2
SEEDASR_MAX_POLLS=600
```

启动校验：

- `PUBLIC_BASE_URL` 必须是 HTTPS，Development 可通过显式开关例外。
- `ARTIFACT_SIGNING_SECRET` 不能使用默认值。
- `VOLC_APP_ID`、`VOLC_ACCESS_TOKEN` 在启用豆包 ASR 时不能为空。
- 日志不得输出 Secret。

更新 [models/registry.yaml](D:/wnx/AI_ShotCut/models/registry.yaml)，把“StaticFiles 暴露音频”改为“受 HMAC 保护的短期 Artifact Provider URL”。

---

## 7. ngrok 启动与验证步骤

### 7.1 启动 FastAPI

```powershell
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

先验证：

```text
GET http://localhost:8000/health/live → 200
GET http://localhost:8000/health/ready → database/storage/ffmpeg 均为 true
```

### 7.2 启动 ngrok

```powershell
ngrok http 8000
```

取得 HTTPS 地址后设置：

```env
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app
```

修改 `.env` 后必须重启 FastAPI，因为当前多个模块在 import/初始化阶段读取环境变量。

### 7.3 在调用豆包前手动验证 Provider URL

使用系统真实生成的 `audio_artifact_id` 生成 URL，随后从另一网络环境请求：

```text
GET {provider_url}
```

验收：

- HTTP 200；
- `Content-Type=audio/wav`；
- Content-Length 与数据库 `size_bytes` 一致；
- 下载文件 SHA-256 与数据库一致；
- VLC/ffprobe 可以读取；
- Token 过期后返回 403；
- 修改 `artifact_id` 或 Token 任一字符后返回 403；
- `purpose=download` 与 `purpose=provider` 按各自规则工作。

不要只在本机用 `localhost` 验证。必须通过 ngrok 公网地址验证，才能证明豆包服务器可访问。

---

## 8. 错误码与重试策略

| error_code | 场景 | retryable |
|---|---|---:|
| `AUDIO_STREAM_MISSING` | 视频没有音轨 | false |
| `AUDIO_EXTRACTION_FAILED` | FFmpeg 音频提取失败 | false/按原因 |
| `AUDIO_ARTIFACT_MISSING` | DB 无真实音频 Artifact | false |
| `AUDIO_FILE_MISSING` | Artifact 存在但文件丢失 | false |
| `PROVIDER_URL_CONFIG_INVALID` | ngrok/PUBLIC_BASE_URL/Secret 配置错误 | false |
| `PROVIDER_URL_EXPIRED` | 豆包拉取时 Token 已过期 | true |
| `PROVIDER_DOWNLOAD_FORBIDDEN` | purpose、项目或类型不匹配 | false |
| `SEEDASR_SUBMIT_FAILED` | Submit API 失败 | 依据状态码 |
| `SEEDASR_QUERY_FAILED` | Query API 失败 | 依据状态码 |
| `SEEDASR_TIMEOUT` | 超过最大轮询时间 | true |
| `SUBTITLE_SCHEMA_INVALID` | 豆包结果无法转换 Schema | false |

重试必须创建新的 Doubao ModelRun 和新的 `provider_request_id`，但可复用同一个未变化的 `audio.normalized` Artifact。不得覆盖旧的字幕 Artifact。

---

## 9. 测试方案

## 9.1 单元测试

### Token

- Provider Token 可以通过 `allowed_purposes={"provider"}` 验证。
- Provider Token 不能冒充 Download Token。
- Artifact ID、Project ID、过期时间或签名被修改时验证失败。
- 默认弱 Secret 在 Production 启动失败。

### Storage/Artifact

- 二进制 Artifact 创建真实 UUID `artifact_id`。
- Artifact URI、文件 SHA-256、数据库 SHA-256、Manifest SHA-256 一致。
- 传入不存在的 `run_id` 时拒绝登记。

### FFmpeg

- 音频命令固定输出 16 kHz、mono、PCM S16LE WAV。
- 无音轨、空文件、超时分别映射正确错误码。

### Adapter/Provider

- Adapter 只接受 `audio_url`。
- Mock Submit/Query 验证使用同一个 `provider_request_id`。
- 豆包 `utterances` 转换成整数毫秒字幕。

## 9.2 API 测试

- 有效 Provider Token 下载音频返回 200。
- Download/Provider purpose 分支分别测试。
- 无 Token、过期 Token、错 Artifact ID 返回 403。
- Artifact 不存在或物理文件丢失返回 404。
- Provider Token 请求 EEG Artifact 返回 403。

## 9.3 PostgreSQL 集成测试

验证完整关系：

```text
Task
→ normalize ModelRun
→ audio.normalized Artifact
→ normalize ModelRunOutput
→ doubao ModelRun
→ doubao ModelRunInput(audio_artifact_id)
→ subtitle Artifact
→ doubao ModelRunOutput
```

## 9.4 公网端到端测试

使用 10–30 秒、包含清晰中文语音的固定 MP4：

1. 上传视频。
2. 创建 Task。
3. 等待 normalize 生成音频 Artifact。
4. 从数据库或 Task Artifact API 获取真实 `audio_artifact_id`。
5. 通过 ngrok URL 下载音频并核对 SHA-256。
6. 执行 SeedASR Submit。
7. 确认 ngrok 请求日志出现来自外部的音频 GET 200。
8. 等待 Query 完成。
9. 检查 `subtitles.json` 的 `start_ms/end_ms/text`。
10. 检查 Task、WorkflowRun、ModelRun 状态全部一致。

---

## 10. 实施顺序

```text
1. FFmpeg 增加 audio.wav 生成与验证
2. ArtifactService 增加二进制文件登记
3. normalize 使用同一真实 run_id 登记 video/audio/probe 输出
4. normalize 返回真实 audio_artifact_id
5. Token 验证支持受控的 provider/download purpose
6. Artifact 下载端点校验 purpose、project、type
7. _transcribe(audio_artifact_id) 查询真实 Artifact 并生成 URL
8. 写 ModelRunInput/Output 与失败状态
9. 重命名 provider_request_id 并完善日志
10. 单元测试 → API 测试 → PostgreSQL 测试 → ngrok 公网 E2E
```

---

## 11. 涉及文件

| 文件 | 改动 |
|---|---|
| `core/media/ffmpeg.py` | 增加 ASR 音频提取命令 |
| `apps/api/services/artifact_service.py` | 增加二进制 Artifact 登记，移除自动结束 ModelRun |
| `apps/api/services/workflow_service.py` | normalize 生成音频并把真实 Artifact ID 传给 transcribe |
| `core/task_storage.py` | 用真实 Artifact ID + Project ID 生成 Provider URL |
| `core/security/artifact_tokens.py` | 支持 allowed purposes、完整 HMAC、有效期上限 |
| `apps/api/routes/artifacts.py` | Provider/Download 分支校验和音频下载 |
| `models/doubao_asr/providers/seedasr.py` | provider_request_id 命名、日志和错误分类 |
| `core/config.py` | 增加签名、TTL 和 ASR 配置校验 |
| `.env.example` | 增加安全配置模板 |
| `models/registry.yaml` | 更新音频访问方式说明 |
| `tests/` | Token、Artifact、FFmpeg、API、DB、E2E 测试 |

---

## 12. 完成定义

- [ ] normalize 实际生成非空 `audio.wav`。
- [ ] `audio.wav` 使用真实 UUID `artifact_id` 写入 PostgreSQL。
- [ ] `audio.normalized` 关联真实 normalize ModelRun 和 ModelRunOutput。
- [ ] `_transcribe()` 接收真实 `audio_artifact_id`，不从文件名推导 ID。
- [ ] Doubao ModelRunInput 记录音频 Artifact 依赖。
- [ ] Provider URL 使用 HTTPS ngrok 地址、绝对过期时间和完整 HMAC。
- [ ] 下载端点正确接受 `purpose=provider`，同时拒绝用途混淆。
- [ ] Token 中 Project ID 与 Artifact 数据库记录一致。
- [ ] Provider URL 只能拉取允许的音频 Artifact，不能拉取 EEG 等私有数据。
- [ ] 通过 ngrok 公网请求音频返回 200 和 `audio/wav`。
- [ ] 豆包 Submit/Query 使用独立 `provider_request_id`。
- [ ] 豆包成功返回后生成标准化 `subtitles.json` 和 Manifest。
- [ ] 字幕时间统一为整数毫秒并满足 `[start_ms, end_ms)`。
- [ ] 失败时 ModelRun、WorkflowRun、Task 状态和错误码一致。
- [ ] Token、API、PostgreSQL 和 ngrok E2E 测试全部通过。

只有以上条件全部满足，才能判定豆包 ASR + ngrok 链路真正跑通；仅能生成 ngrok URL 或仅能在浏览器打开文件都不算完成。
