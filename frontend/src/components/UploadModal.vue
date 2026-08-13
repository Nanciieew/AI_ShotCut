<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ uploadConfig: Object })
const emit = defineEmits(['uploaded'])
const input = ref(null)
const file = ref(null)
const dragging = ref(false)
const uploading = ref(false)
const error = ref('')

const extensions = computed(() => props.uploadConfig?.allowed_containers || ['mp4', 'mov', 'mkv', 'avi'])
const accept = computed(() => extensions.value.map(value => `.${value}`).join(','))
const maxLabel = computed(() => `${Math.round((props.uploadConfig?.max_bytes || 2_000_000_000) / 1_000_000_000)} GB`)
const fileSize = computed(() => file.value ? `${(file.value.size / 1_000_000).toFixed(1)} MB` : '')

function choose(candidate) {
  if (!candidate) return
  const extension = candidate.name.split('.').pop().toLowerCase()
  if (!extensions.value.includes(extension)) {
    error.value = `不支持 .${extension}；支持 ${extensions.value.map(value => `.${value}`).join('、')}`
    return
  }
  file.value = candidate
  error.value = ''
}

async function upload() {
  if (!file.value || !props.uploadConfig?.project_id) return
  uploading.value = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('file', file.value)
    const response = await fetch(`/api/v1/projects/${props.uploadConfig.project_id}/videos`, { method: 'POST', body: form })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail || '上传失败')
    emit('uploaded', payload)
  } catch (reason) {
    error.value = reason.message
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <section class="upload-card">
    <div class="upload-copy"><span class="step">01</span><h2>上传视频</h2><p>视频会保存至当前项目的受控存储空间，浏览器不会直接指定服务器文件路径。</p></div>
    <div class="dropzone" :class="{ dragging, selected:file }" @click="input?.click()"
      @dragover.prevent="dragging=true" @dragleave="dragging=false" @drop.prevent="dragging=false; choose($event.dataTransfer.files[0])">
      <div class="upload-icon">↑</div>
      <strong>{{ file ? file.name : '选择或拖入视频文件' }}</strong>
      <span v-if="file">{{ fileSize }}</span>
      <span v-else>支持 {{ extensions.map(value => `.${value}`).join(' / ') }}，最大 {{ maxLabel }}</span>
      <input ref="input" type="file" :accept="accept" hidden @change="choose($event.target.files[0])">
    </div>
    <p class="hint">建议先压缩至 <b>720p 或以下</b> 再上传，可显著缩短处理与上传时间。</p>
    <p v-if="error" class="error">{{ error }}</p>
    <button class="primary" :disabled="!file || uploading || !uploadConfig" @click="upload">{{ uploading ? '正在上传…' : '上传视频并继续' }} <span>→</span></button>
  </section>
</template>

<style scoped>
.upload-card { display:grid; grid-template-columns:1fr 1.4fr; gap:26px; padding:30px; background:var(--paper); border:1px solid var(--line); border-radius:18px; box-shadow:0 18px 40px #15213b0b; }
.step { color:var(--blue); font-size:.78rem; font-weight:800; }.upload-copy h2 { margin:8px 0 12px; font-size:1.5rem; letter-spacing:-.04em; }.upload-copy p,.hint { color:var(--muted); font-size:.88rem; line-height:1.65; }
.dropzone { min-height:185px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; padding:18px; border:1.5px dashed #afbdd0; border-radius:14px; cursor:pointer; text-align:center; transition:.2s; }.dropzone:hover,.dropzone.dragging,.dropzone.selected { border-color:var(--blue); background:#f5f8ff; }.dropzone strong { max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.dropzone span { color:var(--muted); font-size:.78rem; }.upload-icon { display:grid; place-items:center; width:38px; height:38px; border-radius:50%; background:#e7efff; color:var(--blue); font-size:1.3rem; font-weight:700; }
.hint { grid-column:1/-1; margin:0; }.hint b { color:var(--ink); }.error { grid-column:1/-1; margin:0; color:var(--red); font-size:.85rem; }.primary { grid-column:1/-1; display:flex; align-items:center; justify-content:center; gap:12px; min-height:48px; border:0; border-radius:9px; background:var(--blue); color:#fff; cursor:pointer; font-weight:750; transition:.2s; }.primary:hover { background:var(--blue-dark); }.primary:disabled { cursor:not-allowed; opacity:.45; }.primary span { font-size:1.2rem; }
@media (max-width:650px) { .upload-card { grid-template-columns:1fr; padding:20px; } }
</style>
