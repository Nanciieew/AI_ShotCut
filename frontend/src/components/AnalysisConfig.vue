<script setup>
const scoreMode = defineModel('scoreMode')
const weights = defineModel('weights')
const cutIntensity = defineModel('cutIntensity')
const minDistance = defineModel('minDistance')
defineProps({ canStart: Boolean })
const emit = defineEmits(['start'])

const modes = [
  { key: 'location_only', title: '按场景', subtitle: '根据地点、画面环境与空间变化分段', token: 'location_only' },
  { key: 'character_only', title: '按人物', subtitle: '根据人物组合与主要角色变化分段', token: 'character_only' },
  { key: 'subtitle_only', title: '按情节', subtitle: '根据字幕语义与故事转折分段', token: 'subtitle_only' },
  { key: 'custom', title: '自定义', subtitle: '按场景、人物、情节三类证据组合评分', token: 'custom' },
]
</script>

<template>
  <div class="config-card">
    <div class="mode-grid">
      <button v-for="(mode, index) in modes" :key="mode.key" class="mode" :class="{ selected:scoreMode === mode.key }" @click="scoreMode = mode.key">
        <span class="mode-index">0{{ index + 1 }}</span><strong>{{ mode.title }}</strong><small>{{ mode.subtitle }}</small><code>{{ mode.token }}</code>
      </button>
    </div>

    <section v-if="scoreMode === 'custom'" class="weights">
      <div><h2>自定义证据权重</h2><p>权重会由后端按总和归一化；三个值不能同时为 0。</p></div>
      <label>场景 <input v-model.number="weights.location" type="range" min="0" max="10"><b>{{ weights.location }}</b></label>
      <label>人物 <input v-model.number="weights.character" type="range" min="0" max="10"><b>{{ weights.character }}</b></label>
      <label>情节 <input v-model.number="weights.subtitle" type="range" min="0" max="10"><b>{{ weights.subtitle }}</b></label>
      <p v-if="!canStart" class="weight-error">请至少保留一个大于 0 的权重。</p>
    </section>

    <section class="advanced">
      <label>切分密度<select v-model="cutIntensity"><option value="low">低 · 更少切点</option><option value="medium">中 · 推荐</option><option value="high">高 · 更多切点</option></select></label>
      <label>最小间隔<select v-model.number="minDistance"><option :value="8">8 秒</option><option :value="12">12 秒</option><option :value="20">20 秒</option></select></label>
    </section>
    <button class="start" :disabled="!canStart" @click="emit('start')">开始分析 <span>→</span></button>
  </div>
</template>

<style scoped>
.config-card { padding:28px; background:var(--paper); border:1px solid var(--line); border-radius:18px; box-shadow:0 18px 40px #15213b0b; }.mode-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }.mode { position:relative; min-height:155px; padding:18px; overflow:hidden; border:1px solid var(--line); border-radius:12px; background:#fff; color:var(--ink); cursor:pointer; text-align:left; transition:.18s; }.mode:hover { border-color:#9db8f4; transform:translateY(-1px); }.mode.selected { border:2px solid var(--blue); background:#f5f8ff; }.mode-index { display:block; margin-bottom:18px; color:var(--blue); font-family:ui-monospace,monospace; font-size:.7rem; font-weight:800; }.mode strong { display:block; font-size:1.05rem; }.mode small { display:block; min-height:32px; margin-top:8px; color:var(--muted); font-size:.78rem; line-height:1.4; }.mode code { position:absolute; right:12px; bottom:10px; color:#8290a7; font-size:.66rem; }
.weights { display:grid; grid-template-columns:1fr; gap:13px; margin-top:22px; padding:20px; border-radius:12px; background:#f7f9fc; }.weights h2 { margin:0 0 4px; font-size:1rem; }.weights p { margin:0; color:var(--muted); font-size:.8rem; }.weights label { display:grid; grid-template-columns:45px 1fr 28px; gap:12px; align-items:center; font-size:.88rem; }.weights input { accent-color:var(--blue); }.weights b { color:var(--blue); text-align:right; }.weight-error { color:var(--red)!important; }
.advanced { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin:22px 0; }.advanced label { display:grid; gap:7px; color:var(--muted); font-size:.78rem; }.advanced select { padding:10px 11px; border:1px solid var(--line); border-radius:8px; background:#fff; color:var(--ink); }.start { width:100%; min-height:50px; border:0; border-radius:9px; background:var(--blue); color:#fff; cursor:pointer; font-weight:750; }.start span { margin-left:10px; font-size:1.2rem; }.start:disabled { cursor:not-allowed; opacity:.45; }
@media (max-width:600px) { .mode-grid,.advanced { grid-template-columns:1fr; } }
</style>
