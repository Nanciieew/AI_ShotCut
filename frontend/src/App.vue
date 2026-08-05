<script setup>
import { ref, onUnmounted } from 'vue'
import UploadModal from './components/UploadModal.vue'
import AnalysisConfig from './components/AnalysisConfig.vue'
import ProgressPipeline from './components/ProgressPipeline.vue'
import ResultsScene from './components/ResultsScene.vue'

const phase = ref('idle')  // idle | uploading | uploaded | configuring | running | done
const videoId = ref('')
const projectId = ref('')
const filename = ref('')
const fileSize = ref(0)
const taskId = ref('')
const status = ref('')
const progress = ref(0)
const stage = ref('')
const results = ref(null)
const analysisPurpose = ref('scene_segmentation')  // scene_segmentation | edit_suggestion | shot_detection
const shotModel = ref('ffmpeg_scene')
const scoreMode = ref('weighted')
const intensity = ref('medium')
const minDist = ref(12)
const customW = ref({ L:5, C:3, P:2 })

let pollTimer = null

async function onUploaded(data) {
  videoId.value = data.video_id
  projectId.value = data.project_id
  filename.value = data.filename
  fileSize.value = data.size_bytes
  phase.value = 'configuring'
}

function getPipelineParams() {
  const isScene = analysisPurpose.value !== 'shot_detection'
  const form = new FormData()
  form.append('project_id', projectId.value)
  form.append('extract_keyframes', 'true')
  form.append('scene_analysis', isScene ? 'true' : 'false')
  form.append('shot_model', shotModel.value)
  if (isScene) {
    form.append('score_mode', scoreMode.value)
    form.append('cut_intensity', intensity.value)
    form.append('min_distance_s', minDist.value.toString())
    if (scoreMode.value === 'custom') {
      form.append('location_weight', customW.value.L.toString())
      form.append('character_weight', customW.value.C.toString())
      form.append('plot_weight', customW.value.P.toString())
    }
  }
  return form
}

async function startPipeline() {
  if (!videoId.value) return
  phase.value = 'running'
  const form = getPipelineParams()
  const r = await fetch(`/api/v1/videos/${videoId.value}/analyze-shots`, { method: 'POST', body: form })
  const d = await r.json()
  if (d.task_id) {
    taskId.value = d.task_id
    startPolling()
  }
}

function startPolling() {
  const t0 = Date.now()
  pollTimer = setInterval(async () => {
    try {
      const r = await fetch(`/api/v1/tasks/${taskId.value}`)
      const d = await r.json()
      progress.value = d.progress || 0
      stage.value = d.stage || ''
      if (d.status === 'SUCCEEDED' || d.status === 'FAILED') {
        status.value = d.status
        clearInterval(pollTimer)
        if (d.status === 'SUCCEEDED') { phase.value = 'done'; loadResults() }
      }
    } catch (_) {}
  }, 2000)
}

async function loadResults() {
  try {
    const r = await fetch(`/api/v1/videos/${videoId.value}/results`)
    results.value = await r.json()
  } catch (_) {}
}

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <div class="app">
    <header>
      <h1>AI ShotCut</h1>
      <p class="sub">Intelligent Movie Scene Analysis</p>
    </header>

    <UploadModal v-if="phase === 'idle' || phase === 'uploading'" :phase="phase"
                 :filename="filename" @uploaded="onUploaded" />

    <div v-if="phase === 'configuring' || phase === 'running' || phase === 'done'" class="main-grid">
      <div class="left-col">
        <div class="file-badge">📁 {{ filename }}</div>
        <AnalysisConfig v-if="phase === 'configuring'" v-model:purpose="analysisPurpose"
          v-model:shot-model="shotModel" v-model:score-mode="scoreMode"
          v-model:intensity="intensity" v-model:min-dist="minDist"
          v-model:custom-w="customW" @start="startPipeline" />
        <ProgressPipeline v-if="phase === 'running'" :stage="stage" :progress="progress"
                          :status="status" :purpose="analysisPurpose" />
      </div>
      <ResultsScene v-if="phase === 'done' && results" :results="results" :video-id="videoId"
                    :purpose="analysisPurpose" />
    </div>
  </div>
</template>

<style>
:root {
  --bg: #0b0d14; --panel: #141722; --border: #232738; --text: #e1e4ed; --muted: #6b7084;
  --accent: #6c8cff; --accent2: #a78bfa; --danger: #ff5c5c; --success: #4ade80; --warn: #fbbf24;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh; overflow-x: hidden; }
.app { max-width: 1100px; margin: 0 auto; padding: 24px; }
header { text-align: center; padding: 48px 0 36px; }
h1 { font-size: 2.4rem; background: linear-gradient(135deg, #6c8cff, #a78bfa, #f472b6);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; letter-spacing: -0.5px; }
.sub { color: var(--muted); font-size: 0.95rem; }
.main-grid { display: grid; grid-template-columns: 420px 1fr; gap: 24px; align-items: start; }
.left-col { display: flex; flex-direction: column; gap: 16px; }
.file-badge { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 12px 18px; font-size: 0.9rem; color: var(--muted); }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
.card h2 { font-size: 1rem; color: var(--accent); margin-bottom: 16px; }
.btn { padding: 12px 28px; border: none; border-radius: 8px; font-size: 0.95rem;
  font-weight: 600; cursor: pointer; transition: all .25s; }
.btn-primary { background: linear-gradient(135deg, #6c8cff, #a78bfa); color: #fff; width: 100%; }
.btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 24px #6c8cff30; }
.btn-primary:disabled { opacity: 0.35; cursor: not-allowed; transform: none; box-shadow: none; }
.btn-primary.ready { animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 #6c8cff40; }
  50% { box-shadow: 0 0 0 12px #6c8cff00; } }
</style>
