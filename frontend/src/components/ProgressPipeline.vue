<script setup>
import { computed } from 'vue'
const props = defineProps({ stage: String, progress: Number, status: String, purpose: String })

const steps = computed(() => {
  if (props.purpose === 'shot_detection') return [
    { id:'normalize', label:'Video Transcoding', icon:'🔄' },
    { id:'detect_shots', label:'Shot Detection', icon:'🔍' },
    { id:'complete', label:'Complete', icon:'✅' },
  ]
  return [
    { id:'normalize', label:'Video Transcoding', icon:'🔄' },
    { id:'detect_shots', label:'Shot Detection', icon:'🔍' },
    { id:'extract_keyframes', label:'Keyframe Extraction', icon:'🖼️' },
    { id:'transcribe', label:'Subtitle Extraction', icon:'🎙️' },
    { id:'score', label:'Scene Scoring', icon:'🧠' },
    { id:'merge_scores', label:'Scene Segmentation', icon:'✂️' },
  ]
})

const activeIdx = computed(() => {
  const s = props.stage || ''
  if (s.includes('normalize')) return 0
  if (s.includes('detect_shots')||s.includes('shot')) return 1
  if (s.includes('keyframe')||s.includes('extract')) return 2
  if (s.includes('transcribe')||s.includes('subtitle')) return 3
  if (s.includes('vlm')||s.includes('subtitle_semantic')||s.includes('score')) return 4
  if (s.includes('merge')||s.includes('complete')) return steps.value.length - 1
  return props.progress >= 100 ? steps.value.length : 0
})
</script>

<template>
  <div class="card">
    <div class="pipeline">
      <div v-for="(s,i) in steps" :key="s.id" class="step"
           :class="{ done: i < activeIdx, active: i === activeIdx }">
        <div class="dot"><span>{{ s.icon }}</span></div>
        <span class="label">{{ s.label }}</span>
      </div>
      <div class="flow-line">
        <div class="flow-fill" :style="{ width: (activeIdx / (steps.length-1) * 100) + '%' }"></div>
      </div>
    </div>
    <p class="status">
      <span v-if="status==='SUCCEEDED'" class="badge ok">Analysis Complete</span>
      <span v-else-if="status==='FAILED'" class="badge err">Failed</span>
      <span v-else>{{ progress }}%</span>
    </p>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 28px 20px; }
.pipeline { position: relative; display: flex; justify-content: space-between; padding: 0 4px; }
.step { position: relative; z-index: 2; display: flex; flex-direction: column;
  align-items: center; gap: 8px; width: 60px; }
.dot { width: 36px; height: 36px; border-radius: 50%; background: var(--border);
  display: flex; align-items: center; justify-content: center; font-size: 0.9rem;
  transition: all .4s; border: 2px solid transparent; }
.step.done .dot { background: #4ade8015; border-color: var(--success); }
.step.active .dot { background: var(--accent); border-color: var(--accent);
  animation: glow 1.5s infinite; box-shadow: 0 0 16px #6c8cff40; }
@keyframes glow { 0%,100% { box-shadow: 0 0 8px #6c8cff30; }
  50% { box-shadow: 0 0 20px #6c8cff60; } }
.label { font-size: 0.6rem; color: var(--muted); text-align: center; max-width: 60px;
  transition: .3s; line-height: 1.3; }
.step.active .label, .step.done .label { color: var(--text); }
.flow-line { position: absolute; top: 18px; left: 30px; right: 30px; height: 2px;
  background: var(--border); z-index: 1; }
.flow-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2));
  transition: width .8s cubic-bezier(.4,0,.2,1); }
.status { text-align: center; margin-top: 20px; font-size: 0.85rem; }
.badge { display: inline-block; padding: 4px 14px; border-radius: 10px; font-size: 0.8rem; }
.ok { background: #4ade8015; color: var(--success); }
.err { background: #ff5c5c15; color: var(--danger); }
</style>
