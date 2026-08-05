<script setup>
const scoreMode = defineModel('scoreMode', { default: 'weighted' })
const intensity = defineModel('intensity', { default: 'medium' })
const minDist = defineModel('minDist', { default: 12 })
const sceneAnalysis = defineModel('sceneAnalysis', { default: true })
const customWeights = defineModel('customWeights', { default: () => ({ L:5, C:3, P:2 }) })

const modes = [
  { key: 'weighted', label: 'Weighted' },
  { key: 'location_only', label: 'Location' },
  { key: 'character_only', label: 'Character' },
  { key: 'plot_only', label: 'Plot' },
  { key: 'custom', label: 'Custom' },
]
</script>

<template>
  <div class="card">
    <h2>2. Pipeline Settings</h2>

    <div class="tabs">
      <span v-for="m in modes" :key="m.key" class="tab"
            :class="{ active: scoreMode === m.key }" @click="scoreMode = m.key">
        {{ m.label }}
      </span>
    </div>

    <div v-if="scoreMode === 'custom'" class="weights">
      <label>Location <input type="range" min="1" max="10" v-model.number="customWeights.L" /> {{ customWeights.L }}/10</label>
      <label>Character <input type="range" min="1" max="10" v-model.number="customWeights.C" /> {{ customWeights.C }}/10</label>
      <label>Plot <input type="range" min="1" max="10" v-model.number="customWeights.P" /> {{ customWeights.P }}/10</label>
    </div>

    <div class="row">
      <label>Intensity</label>
      <select v-model="intensity">
        <option value="high">High (6%)</option>
        <option value="medium">Medium (4%)</option>
        <option value="low">Low (1%)</option>
      </select>
    </div>
    <div class="row">
      <label>Min Gap</label>
      <select v-model.number="minDist">
        <option :value="8">8s</option>
        <option :value="12">12s</option>
        <option :value="20">20s</option>
      </select>
    </div>
    <div class="row">
      <label>Analysis</label>
      <select v-model="sceneAnalysis">
        <option :value="true">Full Scene Scoring</option>
        <option :value="false">Shot Detection Only</option>
      </select>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 24px; }
h2 { font-size: 1.1rem; color: var(--accent); margin-bottom: 16px; }
.tabs { display: flex; gap: 4px; margin-bottom: 16px; }
.tab { padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
  color: var(--muted); border: 1px solid transparent; transition: .2s; user-select: none; }
.tab.active { color: var(--accent); border-color: var(--accent); background: #6c8cff10; }
.weights { margin-bottom: 12px; }
.weights label { display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
  color: var(--muted); font-size: 0.85rem; }
.weights input[type=range] { flex: 1; accent-color: var(--accent); }
.row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.row label { color: var(--muted); min-width: 80px; font-size: 0.85rem; }
select { background: var(--bg); border: 1px solid var(--border); color: var(--text);
  padding: 6px 10px; border-radius: 6px; font-size: 0.85rem; outline: none; flex: 1; }
</style>
