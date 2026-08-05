<script setup>
const props = defineProps({ results: Object })

function msStr(ms) {
  const m = Math.floor(ms / 60000)
  const s = ((ms % 60000) / 1000).toFixed(1)
  return m + ':' + s.padStart(4, '0')
}

const scenes = () => props.results?.final_scenes || []
const boundaries = () => props.results?.candidate_boundaries || []
</script>

<template>
  <div class="card">
    <h2>4. Results — {{ scenes().length }} scenes</h2>
    <p class="info" v-if="boundaries().length">{{ boundaries().length }} candidate boundaries</p>
    <div class="list">
      <div v-for="(s, i) in scenes()" :key="i" class="item">
        <span class="time">{{ msStr(s.start_ms) }} → {{ msStr(s.end_ms) }}</span>
        <span class="shots">{{ s.start_shot }} → {{ s.end_shot }}</span>
        <span class="score" :class="s.scene_score > 70 ? 'hi' : s.scene_score > 40 ? 'mid' : 'lo'">
          {{ s.scene_score }}
        </span>
      </div>
      <p v-if="scenes().length === 0" class="info">No scenes loaded yet</p>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 24px; margin-top: 20px; }
h2 { font-size: 1.1rem; color: var(--accent); margin-bottom: 16px; }
.info { color: var(--muted); font-size: 0.8rem; margin-bottom: 8px; }
.list { max-height: 400px; overflow-y: auto; }
.item { display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
.item:hover { background: #ffffff06; }
.time { color: var(--accent); font-family: monospace; min-width: 140px; }
.shots { flex: 1; margin: 0 12px; color: var(--muted); }
.score { font-weight: 700; min-width: 40px; text-align: right; }
.hi { color: var(--success); } .mid { color: var(--warn); } .lo { color: var(--muted); }
</style>
