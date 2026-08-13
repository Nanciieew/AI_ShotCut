<script setup>
import { computed } from 'vue'

const props = defineProps({ results: Object, taskId: String })
const emit = defineEmits(['reset'])
const scenes = computed(() => props.results?.scenes || [])
const evidence = computed(() => Object.fromEntries((props.results?.scene_evidence || []).map(item => [item.scene_id, item])))
const downloadUrl = computed(() => `/api/v1/tasks/${props.taskId}/final-result/download`)

function timestamp(value) {
  const total = Math.max(0, Math.floor((value || 0) / 1000))
  return `${Math.floor(total / 3600)}:${String(Math.floor(total % 3600 / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
function score(value) { return value == null ? '—' : `${Math.round(value * 100)}%` }
</script>

<template>
  <section class="result-card">
    <div class="result-head"><div><p class="eyebrow">FINAL RESULT</p><h2>{{ scenes.length }} 个场景片段</h2><p>最终 JSON 由后端为当前任务生成，可直接下载。</p></div><a class="download" :href="downloadUrl" download>下载 FinalResult JSON <span>↓</span></a></div>
    <div class="scene-table"><article v-for="scene in scenes" :key="scene.scene_id" class="scene-row"><div class="scene-number">{{ String(scene.index + 1).padStart(2, '0') }}</div><div><strong>{{ timestamp(scene.start_ms) }} — {{ timestamp(scene.end_ms) }}</strong><small>{{ scene.shot_ids?.length || 0 }} 个镜头 · 场景评分 {{ score(scene.scene_score) }}</small></div><div class="evidence" v-if="evidence[scene.scene_id]"><span>场景连续性 {{ score(evidence[scene.scene_id].location_continuity) }}</span><span>人物连续性 {{ score(evidence[scene.scene_id].character_continuity) }}</span><span>情节连续性 {{ score(evidence[scene.scene_id].subtitle_continuity) }}</span></div></article><p v-if="!scenes.length" class="empty">未找到可展示的场景数据。</p></div>
    <button class="secondary" @click="emit('reset')">分析另一部影片</button>
  </section>
</template>

<style scoped>
.result-card { margin-top:24px; padding:28px; background:var(--paper); border:1px solid var(--line); border-radius:18px; }.result-head { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; }.eyebrow { margin:0 0 6px; color:var(--blue); font-size:.68rem; font-weight:800; letter-spacing:.13em; }.result-head h2 { margin:0; font-size:1.55rem; letter-spacing:-.04em; }.result-head p:last-child { margin:8px 0 0; color:var(--muted); font-size:.84rem; }.download { display:inline-flex; align-items:center; gap:10px; flex-shrink:0; padding:11px 14px; border:1px solid var(--blue); border-radius:8px; color:var(--blue); font-size:.83rem; font-weight:750; text-decoration:none; }.download:hover { background:#f4f7ff; }.download span { font-size:1.1rem; }.scene-table { display:grid; gap:8px; margin:25px 0 20px; }.scene-row { display:grid; grid-template-columns:42px minmax(180px,1fr) minmax(260px,1.15fr); align-items:center; gap:14px; padding:15px; border:1px solid var(--line); border-radius:10px; }.scene-number { color:var(--blue); font-family:ui-monospace,monospace; font-weight:800; }.scene-row strong { display:block; font-family:ui-monospace,monospace; font-size:.85rem; }.scene-row small { display:block; margin-top:5px; color:var(--muted); font-size:.75rem; }.evidence { display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }.evidence span { padding:5px 7px; border-radius:5px; background:#f3f6fa; color:#5d6c84; font-size:.68rem; }.empty { color:var(--muted); }.secondary { padding:10px 14px; border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink); cursor:pointer; font-weight:650; }.secondary:hover { background:#f6f8fb; }
@media (max-width:740px) { .result-head,.scene-row { display:flex; flex-direction:column; align-items:flex-start; }.download { width:100%; justify-content:center; }.evidence { justify-content:flex-start; } }
</style>
