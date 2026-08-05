<script setup>
const purpose = defineModel('purpose', { default: 'scene_segmentation' })
const shotModel = defineModel('shotModel', { default: 'ffmpeg_scene' })
const scoreMode = defineModel('scoreMode', { default: 'weighted' })
const intensity = defineModel('intensity', { default: 'medium' })
const minDist = defineModel('minDist', { default: 12 })
const customW = defineModel('customW', { default: () => ({ L:5, C:3, P:2 }) })
const emit = defineEmits(['start'])

const purposes = [
  { key:'scene_segmentation', label:'Scene Segmentation', desc:'Full pipeline: shot detection + VLM + LLM → scene cuts', icon:'🎬' },
  { key:'edit_suggestion', label:'Edit Suggestion', desc:'Scene segmentation + EEG-ready output for editing', icon:'✂️' },
  { key:'shot_detection', label:'Shot Detection', desc:'Shot boundaries only (no scene scoring)', icon:'🔍' },
]
const isScene = () => purpose.value !== 'shot_detection'
const modes = [
  { key:'location_only', label:'Location' },
  { key:'character_only', label:'Character' }, { key:'plot_only', label:'Plot' }, { key:'custom', label:'Custom' },
]
const intensityLabels = { high:'High', medium:'Medium', low:'Low' }
</script>

<template>
  <div class="card">
    <h2>Analysis Settings</h2>

    <p class="sec-label">Purpose</p>
    <div class="purpose-grid">
      <div v-for="p in purposes" :key="p.key" class="purpose-card"
           :class="{active: purpose===p.key}" @click="purpose=p.key">
        <span class="p-icon">{{ p.icon }}</span>
        <span class="p-label">{{ p.label }}</span>
        <span class="p-desc">{{ p.desc }}</span>
      </div>
    </div>

    <p class="sec-label">Shot Detection Model</p>
    <div class="row">
      <select v-model="shotModel">
        <option value="ffmpeg_scene">FFmpeg Scene Filter (fast, any length)</option>
        <option value="omnishotcut">OmniShotCut (precise, ≤10min video)</option>
      </select>
    </div>

    <div v-if="isScene()">
      <p class="sec-label">Scene Scoring</p>
      <div class="tabs">
        <span v-for="m in modes" :key="m.key" class="tab" :class="{active:scoreMode===m.key}"
              @click="scoreMode=m.key">{{ m.label }}</span>
      </div>
      <div v-if="scoreMode==='custom'" class="sliders">
        <label>Location <input type="range" min="1" max="10" v-model.number="customW.L"><b>{{ customW.L }}</b>/10</label>
        <label>Character <input type="range" min="1" max="10" v-model.number="customW.C"><b>{{ customW.C }}</b>/10</label>
        <label>Plot <input type="range" min="1" max="10" v-model.number="customW.P"><b>{{ customW.P }}</b>/10</label>
      </div>

      <p class="sec-label">Cut Intensity</p>
      <div class="intensity-row">
        <button v-for="(l,k) in intensityLabels" :key="k" class="int-btn"
                :class="{active: intensity===k}" @click="intensity=k">{{ l }}</button>
      </div>
      <p class="hint">Higher intensity → more scene cuts. Low(1% shots) · Medium(4%) · High(6%)</p>
    </div>

    <button class="btn ready" @click="emit('start')">Start Analysis</button>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
h2 { font-size: 1rem; color: var(--accent); margin-bottom: 16px; }
.sec-label { color: var(--muted); font-size: 0.75rem; text-transform: uppercase;
  letter-spacing: 0.5px; margin: 16px 0 8px; }
.purpose-grid { display: grid; gap: 8px; }
.purpose-card { display: grid; grid-template-columns: 32px 1fr; grid-template-rows: auto auto;
  gap: 2px 10px; padding: 12px; border: 1px solid var(--border); border-radius: 8px;
  cursor: pointer; transition: .2s; }
.purpose-card:hover { border-color: var(--accent); }
.purpose-card.active { border-color: var(--accent); background: #6c8cff0d; }
.p-icon { grid-row: 1/3; font-size: 1.3rem; align-self: center; }
.p-label { font-size: 0.9rem; font-weight: 600; }
.p-desc { font-size: 0.75rem; color: var(--muted); }
.row { margin-top: 8px; }
select { width: 100%; background: var(--bg); border: 1px solid var(--border); color: var(--text);
  padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; outline: none; }
.tabs { display: flex; gap: 4px; margin-top: 8px; }
.tab { padding: 5px 12px; border-radius: 6px; cursor: pointer; font-size: 0.8rem;
  color: var(--muted); border: 1px solid transparent; transition: .2s; user-select: none; }
.tab.active { color: var(--accent); border-color: var(--accent); background: #6c8cff0d; }
.sliders { margin-top: 8px; }
.sliders label { display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
  color: var(--muted); font-size: 0.8rem; }
.sliders input[type=range] { flex: 1; accent-color: var(--accent); }
.sliders b { color: var(--accent); min-width: 20px; }
.intensity-row { display: flex; gap: 6px; margin-top: 8px; }
.int-btn { flex: 1; padding: 8px 0; border: 1px solid var(--border); border-radius: 6px;
  background: transparent; color: var(--muted); cursor: pointer; font-size: 0.85rem; transition: .2s; }
.int-btn.active { border-color: var(--accent); color: var(--accent); background: #6c8cff0d; }
.hint { color: var(--muted); font-size: 0.72rem; margin-top: 6px; }
.btn { margin-top: 20px; padding: 12px 28px; border: none; border-radius: 8px; font-size: 0.95rem;
  font-weight: 600; cursor: pointer; background: linear-gradient(135deg, #6c8cff, #a78bfa);
  color: #fff; width: 100%; }
.btn.ready { animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 #6c8cff40; }
  50% { box-shadow: 0 0 0 12px #6c8cff00; } }
</style>
