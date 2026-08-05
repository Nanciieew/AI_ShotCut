<script setup>
import { computed } from 'vue'
const props = defineProps({ results: Object, videoId: String, purpose: String })

const scenes = computed(() => props.results?.final_scenes || [])
const boundaries = computed(() => props.results?.candidate_boundaries || [])

function msStr(ms) {
  const h = Math.floor(ms / 3600000); const m = Math.floor((ms % 3600000) / 60000)
  const s = Math.floor((ms % 60000) / 1000); const ms2 = ms % 1000
  return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms2).padStart(3,'0')}`
}

function imgUrl(shotId) {
  return `/api/v1/videos/${props.videoId}/keyframes/${shotId}/img_2`
}

function exportJSON() {
  const blob = new Blob([JSON.stringify({ final_scenes: scenes.value, candidate_boundaries: boundaries.value }, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = 'scene_segmentation.json'; a.click()
  URL.revokeObjectURL(url)
}

const showEEG = computed(() => props.purpose === 'edit_suggestion')
</script>

<template>
  <div class="card full">
    <div style="display:flex; justify-content:space-between; align-items:center">
      <h2>Scene Segmentation — {{ scenes.length }} scenes</h2>
      <div style="display:flex; gap:8px">
        <button class="btn-export" @click="exportJSON">📥 Export JSON</button>
        <button v-if="showEEG" class="btn-eeg">🧠 EEG Analysis</button>
      </div>
    </div>

    <p class="info" v-if="boundaries.length">{{ boundaries.length }} candidate boundaries selected</p>

    <div class="scene-list">
      <div v-for="(s,i) in scenes" :key="i" class="scene-card">
        <div class="scene-img">
          <img :src="imgUrl(s.start_shot)" :alt="s.start_shot" @error="$event.target.style.display='none'" />
        </div>
        <div class="scene-info">
          <div class="scene-time">{{ msStr(s.start_ms) }} → {{ msStr(s.end_ms) }}</div>
          <div class="scene-shots">{{ s.start_shot }} → {{ s.end_shot }}</div>
          <div class="scene-desc" v-if="s.summary">{{ s.summary }}</div>
          <div v-else class="scene-desc muted">Scene {{ i+1 }} · Score {{ s.scene_score }}</div>
        </div>
        <div class="scene-score" :class="s.scene_score>70?'hi':s.scene_score>40?'mid':'lo'">
          {{ s.scene_score }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
h2 { font-size: 1rem; color: var(--accent); }
.info { color: var(--muted); font-size: 0.8rem; margin-bottom: 12px; }
.btn-export, .btn-eeg { padding: 8px 16px; border-radius: 8px; font-size: 0.85rem;
  font-weight: 600; cursor: pointer; transition: .2s; }
.btn-export { background: #6c8cff15; color: var(--accent); border: 1px solid var(--accent); }
.btn-export:hover { background: #6c8cff25; }
.btn-eeg { background: #a78bfa15; color: var(--accent2); border: 1px solid var(--accent2); }
.scene-list { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.scene-card { display: flex; align-items: center; gap: 14px; padding: 14px;
  border: 1px solid var(--border); border-radius: 10px; transition: .2s; }
.scene-card:hover { border-color: var(--accent); background: #6c8cff05; }
.scene-img { width: 100px; height: 56px; border-radius: 6px; overflow: hidden;
  background: var(--border); flex-shrink: 0; }
.scene-img img { width: 100%; height: 100%; object-fit: cover; }
.scene-info { flex: 1; min-width: 0; }
.scene-time { font-family: monospace; color: var(--accent); font-size: 0.85rem; margin-bottom: 3px; }
.scene-shots { color: var(--muted); font-size: 0.7rem; margin-bottom: 4px; }
.scene-desc { font-size: 0.8rem; color: var(--text); }
.scene-desc.muted { color: var(--muted); }
.scene-score { font-weight: 700; font-size: 1.2rem; min-width: 36px; text-align: center; }
.hi { color: var(--success); } .mid { color: var(--warn); } .lo { color: var(--muted); }
</style>
