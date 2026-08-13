<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: String,
  progress: Number,
  status: String,
  errorCode: String,
  errorMessage: String,
  networkWarning: String,
})
defineEmits(['reconnect', 'retry-task'])
const steps = [
  { label: '视频转码', detail: 'FFmpeg 标准化 MP4 与音频', stages: ['normalize_video'] },
  { label: '镜头检测', detail: '检测 Shot Boundary', stages: ['detect_shots'] },
  { label: '关键帧提取', detail: '提取镜头代表帧', stages: ['extract_keyframes'] },
  { label: '视觉分析', detail: '地点与人物变化', stages: ['score_vlm'] },
  { label: '情节分析', detail: 'ASR 字幕与语义连续性', stages: ['transcribe', 'score_subtitle_semantics'] },
  { label: '计算结果', detail: '合并 Scene 并计算评分', stages: ['merge_scores', 'complete'] },
]
const activeIndex = computed(() => {
  const found = steps.findIndex(step => step.stages.includes(props.stage))
  if (props.status === 'SUCCEEDED') return steps.length
  return found < 0 ? 0 : found
})
const runningLabel = computed(() => steps[Math.min(activeIndex.value, steps.length - 1)]?.detail || '准备任务')
</script>

<template>
  <section class="progress-card">
    <div class="progress-meta"><div><strong>{{ status === 'SUCCEEDED' ? '分析已完成' : runningLabel }}</strong><span>{{ status === 'FAILED' ? '管线已停止' : `${progress || 0}%` }}</span></div><div class="bar"><i :style="{ width:`${progress || 0}%` }" /></div></div>
    <div class="track">
      <div v-for="(step, index) in steps" :key="step.label" class="step" :class="{ done:index < activeIndex, active:index === activeIndex && status !== 'SUCCEEDED' }">
        <div class="cell"><span v-if="index === activeIndex && status !== 'SUCCEEDED'" class="spider" aria-label="正在前进的蜘蛛">🕷</span><span v-else>{{ index < activeIndex || status === 'SUCCEEDED' ? '✓' : index + 1 }}</span></div>
        <strong>{{ step.label }}</strong><small>{{ step.detail }}</small>
      </div>
    </div>
    <div v-if="networkWarning" class="network-panel">
      <div><strong>后端连接不稳定</strong><p>{{ networkWarning }}。分析任务可能仍在运行。</p></div>
      <button type="button" @click="$emit('reconnect')">立即重连</button>
    </div>
    <div v-if="['FAILED', 'INTERRUPTED', 'CANCELLED'].includes(status)" class="error-panel">
      <div><strong>分析未完成</strong><code v-if="errorCode">{{ errorCode }}</code><p>{{ errorMessage || '任务已中断，请检查服务状态后重试。' }}</p></div>
      <button type="button" @click="$emit('retry-task')">从缓存重试</button>
    </div>
  </section>
</template>

<style scoped>
.progress-card { padding:30px; background:var(--paper); border:1px solid var(--line); border-radius:18px; }.progress-meta { display:grid; gap:12px; }.progress-meta > div:first-child { display:flex; justify-content:space-between; gap:12px; }.progress-meta strong { font-size:1rem; }.progress-meta span { color:var(--blue); font-family:ui-monospace,monospace; font-size:.85rem; }.bar { height:7px; overflow:hidden; border-radius:999px; background:#e8edf5; }.bar i { display:block; height:100%; border-radius:inherit; background:var(--blue); transition:width .55s ease; }.track { display:grid; grid-template-columns:repeat(6,1fr); gap:8px; margin-top:34px; }.step { position:relative; min-width:0; color:#9aa7ba; text-align:center; }.step:not(:last-child)::after { position:absolute; top:18px; left:calc(50% + 22px); width:calc(100% - 44px); height:1px; background:#dce4ee; content:""; }.cell { position:relative; z-index:1; display:grid; place-items:center; width:37px; height:37px; margin:0 auto 10px; border:1px solid #d5deea; border-radius:10px; background:#fff; font-size:.82rem; }.done .cell { border-color:#78c7af; background:#effbf6; color:var(--green); }.active .cell { border-color:var(--blue); box-shadow:0 0 0 5px #2563eb16; color:var(--blue); }.active strong { color:var(--ink); }.step strong { display:block; font-size:.78rem; }.step small { display:block; margin-top:5px; padding:0 3px; font-size:.65rem; line-height:1.35; }.spider { animation:hop .85s ease-in-out infinite alternate; font-size:1.25rem; } @keyframes hop { from { transform:translateY(0) rotate(-7deg); } to { transform:translateY(-10px) rotate(7deg); } }.error-panel { display:flex; align-items:center; justify-content:space-between; gap:18px; margin-top:26px; padding:16px; border-left:3px solid var(--red); border-radius:8px; background:#fff1f1; color:#812b2b; }.error-panel code { margin-left:10px; font-size:.72rem; }.error-panel p { margin:8px 0 0; line-height:1.55; font-size:.86rem; }.error-panel button { flex:none; padding:8px 13px; border:1px solid #dfa8a8; border-radius:8px; background:#fff; color:#812b2b; cursor:pointer; }
.network-panel { display:flex; align-items:center; justify-content:space-between; gap:18px; margin-top:26px; padding:16px; border-left:3px solid #d89a19; border-radius:8px; background:#fff8e8; color:#76520b; }.network-panel p { margin:5px 0 0; font-size:.84rem; }.network-panel button { flex:none; padding:8px 13px; border:1px solid #ddb45c; border-radius:8px; background:#fff; color:#76520b; cursor:pointer; }
@media (max-width:760px) { .progress-card { padding:20px; overflow:auto; }.track { min-width:650px; } }
</style>
