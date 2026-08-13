<script setup>
import { ref } from 'vue'
const props = defineProps({ phase: String, filename: String })
const emit = defineEmits(['uploaded'])
const showModal = ref(true)
const dragging = ref(false)
const file = ref(null)
const uploading = ref(false)
const msg = ref('')

async function upload() {
  if (!file.value) return
  uploading.value = true; msg.value = 'Uploading...'
  const form = new FormData()
  form.append('file', file.value)
  try {
    const r = await fetch('/api/v1/videos', { method: 'POST', body: form })
    const d = await r.json()
    if (d.video_id) { emit('uploaded', d); showModal.value = false }
    else msg.value = 'Failed'
  } catch(e) { msg.value = 'Network error — is the server running?' }
  uploading.value = false
}
function onDrop(e) { e.preventDefault(); dragging.value = false; handle(e.dataTransfer.files[0]) }
function handle(f) { if (!f || !f.name.toLowerCase().endsWith('.mp4')) { msg.value = 'Only .mp4 files'; return } file.value = f; msg.value = '' }
const fmt = (s) => s ? (s/1e6).toFixed(1)+' MB' : ''
</script>

<template>
  <div class="overlay" v-if="showModal">
    <div class="modal">
      <h2>Upload Video</h2>
      <div class="drop" :class="{ drag: dragging }" @dragover.prevent="dragging=true"
           @dragleave="dragging=false" @drop="onDrop" @click="$refs.finput.click()">
        <div class="drop-icon">📁</div>
        <p v-if="!file">Click or drag & drop your video</p>
        <p v-else class="file-name">{{ file.name }}<br><span class="sz">{{ fmt(file.size) }}</span></p>
        <p class="hint">Supports .mp4 up to 2GB</p>
      </div>
      <input ref="finput" type="file" accept="video/mp4" hidden @change="handle($event.target.files[0])" />
      <button class="btn" :disabled="!file || uploading" @click="upload">
        {{ uploading ? 'Uploading...' : 'Confirm Upload' }}
      </button>
      <p class="msg" :class="{err: msg.includes('Failed')||msg.includes('error')}">{{ msg }}</p>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: #00000080; display: flex;
  align-items: center; justify-content: center; z-index: 100; backdrop-filter: blur(4px); }
.modal { background: var(--panel); border: 1px solid var(--border); border-radius: 16px;
  padding: 36px; width: 480px; max-width: 90vw; text-align: center; }
h2 { font-size: 1.2rem; color: var(--accent); margin-bottom: 24px; }
.drop { border: 2px dashed var(--border); border-radius: 12px; padding: 48px 24px;
  cursor: pointer; transition: .2s; margin-bottom: 16px; }
.drop:hover, .drop.drag { border-color: var(--accent); background: #6c8cff08; }
.drop-icon { font-size: 2.5rem; margin-bottom: 12px; }
.drop p { color: var(--muted); }
.file-name { color: var(--text) !important; font-weight: 600; }
.sz { font-weight: 400; font-size: 0.8rem; }
.hint { font-size: 0.75rem; margin-top: 8px; }
.btn { padding: 12px 32px; border: none; border-radius: 8px; font-size: 0.95rem;
  font-weight: 600; cursor: pointer; background: linear-gradient(135deg, #6c8cff, #a78bfa);
  color: #fff; width: 100%; transition: .2s; }
.btn:disabled { opacity: 0.35; cursor: not-allowed; }
.msg { color: var(--muted); margin-top: 12px; font-size: 0.85rem; }
.msg.err { color: var(--danger); }
</style>
