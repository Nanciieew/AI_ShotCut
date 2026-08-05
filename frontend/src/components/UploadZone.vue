<script setup>
import { ref } from 'vue'

const props = defineProps({ uploadOk: Boolean, filename: String, size: Number })
const emit = defineEmits(['uploaded'])

const dragging = ref(false)
const file = ref(null)
const uploading = ref(false)
const msg = ref('')

async function upload() {
  if (!file.value) return
  uploading.value = true; msg.value = 'Uploading...'
  const form = new FormData()
  form.append('file', file.value)
  form.append('project_id', 'default')
  try {
    const r = await fetch('/api/v1/videos', { method: 'POST', body: form })
    const d = await r.json()
    if (d.video_id) { msg.value = 'OK: ' + d.video_id; emit('uploaded', d) }
    else msg.value = 'Failed: ' + JSON.stringify(d)
  } catch(e) { msg.value = 'Error: ' + e.message }
  uploading.value = false
}

function onDrop(e) { e.preventDefault(); dragging.value = false; handleFile(e.dataTransfer.files[0]) }
function onFile(e) { handleFile(e.target.files[0]) }
function handleFile(f) {
  if (!f) return; file.value = f
}

const fmtSize = (s) => s ? (s/1e6).toFixed(1) + ' MB' : ''
</script>

<template>
  <div class="card">
    <h2>1. Upload Video</h2>
    <div class="drop" :class="{ drag: dragging }" @dragover.prevent="dragging=true"
         @dragleave="dragging=false" @drop="onDrop" @click="$refs.finput.click()">
      <p v-if="!file">📁 Click to upload or drag & drop</p>
      <p v-else>{{ file.name }} ({{ fmtSize(file.size) }})</p>
    </div>
    <input ref="finput" type="file" accept="video/*" hidden @change="onFile" />
    <button class="btn" :disabled="!file || uploading" @click="upload" style="margin-top:12px">
      {{ uploading ? 'Uploading...' : (props.uploadOk ? '✅ Uploaded' : 'Upload & Submit') }}
    </button>
    <p class="info">{{ msg }}</p>
    <p class="info" v-if="uploadOk">{{ filename }} · {{ fmtSize(size) }}</p>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 24px; }
h2 { font-size: 1.1rem; color: var(--accent); margin-bottom: 16px; }
.drop { border: 2px dashed var(--border); border-radius: 10px; padding: 40px; text-align: center;
  cursor: pointer; transition: .2s; }
.drop:hover, .drop.drag { border-color: var(--accent); background: #1a1f3540; }
.drop p { color: var(--muted); }
.btn { padding: 10px 24px; border: none; border-radius: 6px; font-size: 0.9rem; font-weight: 600;
  cursor: pointer; background: linear-gradient(135deg, var(--grad-start), var(--grad-end)); color: #fff;
  width: 100%; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.info { color: var(--muted); font-size: 0.8rem; margin-top: 8px; }
</style>
