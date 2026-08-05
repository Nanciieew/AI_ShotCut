<script setup>
import { ref, computed, onUnmounted } from 'vue'
import UploadZone from './components/UploadZone.vue'
import PipelineConfig from './components/PipelineConfig.vue'
import ProgressCard from './components/ProgressCard.vue'
import ResultsCard from './components/ResultsCard.vue'

const videoId = ref('')
const taskId = ref('')
const stage = ref('')
const progress = ref(0)
const elapsed = ref(0)
const status = ref('')
const results = ref(null)
const projectId = ref('my_project')
const uploadFilename = ref('')
const uploadSize = ref(0)
const uploadOk = ref(false)

const scoreMode = ref('weighted')
const intensity = ref('medium')
const minDist = ref(12)
const sceneAnalysis = ref(true)
const customWeights = ref({ L: 5, C: 3, P: 2 })

let pollTimer = null

async function onUploaded(data) {
  videoId.value = data.video_id
  projectId.value = data.project_id
  uploadFilename.value = data.filename
  uploadSize.value = data.size_bytes
  uploadOk.value = true
  await submitPipeline()
}

async function submitPipeline() {
  if (!videoId.value) return
  const form = new FormData()
  form.append('project_id', projectId.value)
  form.append('extract_keyframes', 'true')
  form.append('scene_analysis', sceneAnalysis.value ? 'true' : 'false')
  form.append('score_mode', scoreMode.value)
  form.append('cut_intensity', intensity.value)
  form.append('min_distance_s', minDist.value.toString())
  if (scoreMode.value === 'custom') {
    form.append('location_weight', customWeights.value.L.toString())
    form.append('character_weight', customWeights.value.C.toString())
    form.append('plot_weight', customWeights.value.P.toString())
  }
  try {
    const r = await fetch(`/api/v1/videos/${videoId.value}/analyze-shots`, { method: 'POST', body: form })
    const d = await r.json()
    if (d.task_id) {
      taskId.value = d.task_id
      startPolling()
    }
  } catch (e) {
    status.value = 'start_failed'
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
      elapsed.value = Math.round((Date.now() - t0) / 1000)
      if (d.status === 'SUCCEEDED' || d.status === 'FAILED') {
        status.value = d.status
        clearInterval(pollTimer)
        if (d.status === 'SUCCEEDED') loadResults()
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
      <p class="sub">Movie Scene Analysis</p>
    </header>

    <div class="grid">
      <UploadZone :upload-ok="uploadOk" :filename="uploadFilename" :size="uploadSize"
                  @uploaded="onUploaded" />

      <PipelineConfig v-model:score-mode="scoreMode" v-model:intensity="intensity"
                      v-model:min-dist="minDist" v-model:scene-analysis="sceneAnalysis"
                      v-model:custom-weights="customWeights" />
    </div>

    <ProgressCard v-if="taskId" :stage="stage" :progress="progress" :elapsed="elapsed"
                  :status="status" />

    <ResultsCard v-if="results" :results="results" />
  </div>
</template>

<style>
:root {
  --bg: #0f1117; --panel: #1a1d27; --border: #2a2d3a;
  --text: #e1e4ed; --muted: #8b8fa3; --accent: #6c8cff; --danger: #ff5c5c;
  --success: #4ade80; --warn: #fbbf24; --grad-start: #4f46e5; --grad-end: #7c3aed;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text); min-height: 100vh; }
.app { max-width: 1200px; margin: 0 auto; padding: 24px; }
header { text-align: center; padding: 40px 0 30px; }
h1 { font-size: 2rem; background: linear-gradient(135deg, var(--grad-start), var(--grad-end));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 6px; }
.sub { color: var(--muted); font-size: 0.9rem; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
</style>
