<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import UploadModal from './components/UploadModal.vue'
import AnalysisConfig from './components/AnalysisConfig.vue'
import ProgressPipeline from './components/ProgressPipeline.vue'
import ResultsScene from './components/ResultsScene.vue'

const page = ref('upload')
const uploadConfig = ref(null)
const uploadError = ref('')
const video = ref(null)
const taskId = ref('')
const task = ref({ status: 'PENDING', stage: 'created', progress: 0 })
const results = ref(null)
const requestError = ref('')
const networkWarning = ref('')
const scoreMode = ref('location_only')
const weights = ref({ location: 5, character: 3, subtitle: 2 })
const cutIntensity = ref('medium')
const minDistance = ref(12)

let pollTimer = null
let pollFailures = 0
let pollInFlight = false

const canStart = computed(() => scoreMode.value !== 'custom' ||
  Object.values(weights.value).some(value => value > 0))

async function readJson(response) {
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail || payload.error_message || `Request failed (${response.status})`)
  }
  return payload
}

onMounted(async () => {
  try {
    uploadConfig.value = await readJson(await fetch('/api/v1/upload-config'))
  } catch (error) {
    uploadError.value = `无法读取上传配置：${error.message}`
  }
})

function onUploaded(payload) {
  video.value = payload
  page.value = 'configure'
}

function analysisPayload() {
  return {
    scene_analysis: true,
    score_mode: scoreMode.value,
    cut_intensity: cutIntensity.value,
    min_distance_s: minDistance.value,
    location_weight: scoreMode.value === 'custom' ? weights.value.location : 1,
    character_weight: scoreMode.value === 'custom' ? weights.value.character : 1,
    subtitle_weight: scoreMode.value === 'custom' ? weights.value.subtitle : 1,
  }
}

async function startPipeline() {
  if (!video.value || !canStart.value) return
  requestError.value = ''
  networkWarning.value = ''
  page.value = 'progress'
  try {
    const payload = await readJson(await fetch(`/api/v1/videos/${video.value.video_id}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(analysisPayload()),
    }))
    taskId.value = payload.task_id
    task.value = payload
    startPolling()
  } catch (error) {
    requestError.value = error.message
    task.value = { status: 'FAILED', stage: 'created', progress: 0, error_message: error.message }
  }
}

function startPolling() {
  clearTimeout(pollTimer)
  const poll = async () => {
    if (pollInFlight || !taskId.value) return
    pollInFlight = true
    try {
      const payload = await readJson(await fetch(`/api/v1/tasks/${taskId.value}`))
      task.value = payload
      pollFailures = 0
      networkWarning.value = ''
      if (payload.status === 'SUCCEEDED') {
        await loadResults()
        return
      } else if (['FAILED', 'INTERRUPTED', 'CANCELLED'].includes(payload.status)) {
        return
      }
    } catch (error) {
      pollFailures += 1
      networkWarning.value = `暂时无法连接后端，正在自动重连（第 ${pollFailures} 次）`
    } finally {
      pollInFlight = false
      if (!['SUCCEEDED', 'FAILED', 'INTERRUPTED', 'CANCELLED'].includes(task.value.status)) {
        const delay = Math.min(1500 * Math.max(pollFailures, 1), 10000)
        pollTimer = setTimeout(poll, delay)
      }
    }
  }
  poll()
}

async function loadResults() {
  try {
    results.value = await readJson(await fetch(
      `/api/v1/videos/${video.value.video_id}/results?task_id=${taskId.value}`,
    ))
    page.value = 'result'
  } catch (error) {
    requestError.value = `结果读取失败：${error.message}`
  }
}

async function retryPipeline() {
  if (!taskId.value) return
  requestError.value = ''
  networkWarning.value = ''
  try {
    const payload = await readJson(await fetch(`/api/v1/tasks/${taskId.value}/retry`, {
      method: 'POST',
    }))
    taskId.value = payload.task_id
    task.value = { status: payload.status || 'QUEUED', stage: 'created', progress: 0 }
    startPolling()
  } catch (error) {
    networkWarning.value = `无法提交重试：${error.message}`
  }
}

function reset() {
  clearTimeout(pollTimer)
  page.value = 'upload'
  video.value = null
  taskId.value = ''
  results.value = null
  requestError.value = ''
  networkWarning.value = ''
  pollFailures = 0
}

onUnmounted(() => clearTimeout(pollTimer))
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <button class="brand" @click="reset"><span>◒</span> SceneThread</button>
      <span class="tagline">电影智能分段</span>
      <span v-if="taskId" class="task-chip">任务 {{ taskId.slice(0, 8) }}</span>
    </header>

    <section class="hero" v-if="page === 'upload'">
      <p class="eyebrow">MOVIE ANALYSIS PLATFORM</p>
      <h1>让电影分段，<em>从理解开始。</em></h1>
      <p>上传视频，选择分段方式，获得可下载、可追溯的场景分析结果。</p>
    </section>

    <p v-if="uploadError" class="global-error">{{ uploadError }}</p>

    <UploadModal v-if="page === 'upload'" :upload-config="uploadConfig" @uploaded="onUploaded" />

    <section v-if="page === 'configure'" class="page-panel">
      <div class="page-heading">
        <p class="eyebrow">STEP 02</p>
        <h1>选择分段逻辑</h1>
        <p>{{ video?.filename }} · 已保存到受控项目存储</p>
      </div>
      <AnalysisConfig v-model:score-mode="scoreMode" v-model:weights="weights"
        v-model:cut-intensity="cutIntensity" v-model:min-distance="minDistance"
        :can-start="canStart" @start="startPipeline" />
    </section>

    <section v-if="page === 'progress' || page === 'result'" class="page-panel wide">
      <div class="page-heading compact">
        <p class="eyebrow">STEP 03</p>
        <h1>{{ page === 'result' ? '分析完成' : '正在分析影片' }}</h1>
        <p>{{ video?.filename }}</p>
      </div>
      <ProgressPipeline :stage="task.stage" :progress="task.progress" :status="task.status"
        :error-code="task.error_code" :error-message="requestError || task.error_message"
        :network-warning="networkWarning" @reconnect="startPolling" @retry-task="retryPipeline" />
      <ResultsScene v-if="page === 'result' && results" :results="results" :task-id="taskId" @reset="reset" />
    </section>
  </main>
</template>

<style>
:root { --ink:#1b2740; --muted:#71809a; --line:#dde5ee; --paper:#ffffff; --wash:#f4f7fb; --blue:#2563eb; --blue-dark:#1d4ed8; --red:#c24142; --green:#16805f; }
* { box-sizing:border-box; }
body { margin:0; min-width:320px; background:var(--wash); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
button, input { font:inherit; }
.app-shell { min-height:100vh; max-width:1180px; margin:0 auto; padding:0 28px 70px; }
.topbar { height:80px; display:flex; align-items:center; gap:16px; border-bottom:1px solid var(--line); }
.brand { border:0; background:transparent; color:var(--ink); cursor:pointer; font-size:1.08rem; font-weight:800; letter-spacing:-.03em; padding:0; }
.brand span { display:inline-grid; place-items:center; width:26px; height:26px; margin-right:7px; border-radius:50%; background:var(--blue); color:#fff; }
.tagline { color:var(--muted); font-size:.85rem; }
.task-chip { margin-left:auto; padding:7px 10px; color:var(--muted); border:1px solid var(--line); border-radius:999px; font-family:ui-monospace, monospace; font-size:.72rem; }
.hero { max-width:750px; padding:110px 0 42px; }
.eyebrow { margin:0 0 12px; color:var(--blue); font-size:.72rem; font-weight:800; letter-spacing:.14em; }
h1 { margin:0; letter-spacing:-.05em; font-size:clamp(2.25rem,6vw,4.85rem); line-height:1.02; }
h1 em { color:var(--blue); font-style:normal; }
.hero > p:last-child, .page-heading > p:last-child { max-width:570px; margin:22px 0 0; color:var(--muted); line-height:1.7; }
.page-panel { max-width:830px; margin:72px auto 0; }
.page-panel.wide { max-width:1100px; }
.page-heading { margin-bottom:28px; }
.page-heading h1 { font-size:clamp(2rem,4vw,3.4rem); }
.page-heading.compact { margin-top:64px; }
.global-error { margin:20px 0; padding:13px 16px; border-left:3px solid var(--red); background:#fff0f0; color:#8d2525; border-radius:8px; }
@media (max-width:650px) { .app-shell { padding:0 18px 48px; } .tagline { display:none; } .hero { padding-top:70px; } .page-panel { margin-top:44px; } }
</style>
