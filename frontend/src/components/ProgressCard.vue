<script setup>
defineProps({ stage: String, progress: Number, elapsed: Number, status: String })
</script>

<template>
  <div class="card">
    <h2>3. Progress</h2>
    <p class="stage">{{ stage || 'Waiting...' }}
      <span v-if="status === 'SUCCEEDED'" class="badge ok">Done</span>
      <span v-else-if="status === 'FAILED'" class="badge err">Failed</span>
    </p>
    <div class="bar"><div class="fill" :style="{ width: progress + '%' }"></div></div>
    <p class="info">{{ progress }}% · {{ elapsed }}s</p>
  </div>
</template>

<style scoped>
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 24px; margin-top: 20px; }
h2 { font-size: 1.1rem; color: var(--accent); margin-bottom: 16px; }
.stage { text-align: center; color: var(--muted); margin-bottom: 12px; }
.bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.fill { height: 100%; background: linear-gradient(90deg, var(--grad-start), var(--grad-end));
  border-radius: 4px; transition: width .5s; }
.info { color: var(--muted); font-size: 0.8rem; text-align: center; margin-top: 8px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem;
  margin-left: 8px; }
.ok { background: #4ade8020; color: var(--success); }
.err { background: #ff5c5c20; color: var(--danger); }
</style>
