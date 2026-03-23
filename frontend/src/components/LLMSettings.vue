<template>
  <div class="llm-settings-overlay" @click.self="$emit('close')">
    <div class="llm-settings-panel">
      <!-- Header -->
      <div class="panel-header">
        <span class="panel-title">LLM Provider Settings</span>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>

      <!-- Provider toggle -->
      <div class="section">
        <span class="section-label">ACTIVE PROVIDER</span>
        <div class="provider-toggle">
          <button
            class="toggle-btn"
            :class="{ active: form.provider === 'openai' }"
            @click="form.provider = 'openai'"
          >
            OpenAI
          </button>
          <button
            class="toggle-btn"
            :class="{ active: form.provider === 'claude' }"
            @click="form.provider = 'claude'"
          >
            Claude (Anthropic)
          </button>
        </div>
      </div>

      <!-- OpenAI section -->
      <div v-if="form.provider === 'openai'" class="section">
        <span class="section-label">OPENAI SETTINGS</span>
        <label class="field-label">API Key</label>
        <input
          v-model="form.openai_api_key"
          class="text-input"
          type="password"
          :placeholder="settings?.openai?.api_key_preview || 'sk-...'"
          autocomplete="off"
        />
        <label class="field-label">Base URL</label>
        <input
          v-model="form.openai_base_url"
          class="text-input"
          type="text"
          :placeholder="settings?.openai?.base_url || 'https://api.openai.com/v1'"
        />
        <label class="field-label">Model</label>
        <input
          v-model="form.openai_model"
          class="text-input"
          type="text"
          :placeholder="settings?.openai?.model || 'gpt-4o-mini'"
        />
      </div>

      <!-- Claude section -->
      <div v-else class="section">
        <span class="section-label">CLAUDE (ANTHROPIC) SETTINGS</span>

        <!-- Get API Key link -->
        <div class="claude-promo">
          <p class="claude-desc">
            Enter your Anthropic API key below, or open the Anthropic Console
            to create one linked to your account (including Claude Pro).
          </p>
          <a
            :href="claudeConsoleUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="claude-link-btn"
          >
            Open Anthropic Console &nbsp;↗
          </a>
        </div>

        <label class="field-label">API Key</label>
        <input
          v-model="form.claude_api_key"
          class="text-input"
          type="password"
          :placeholder="settings?.claude?.api_key_preview || 'sk-ant-...'"
          autocomplete="off"
        />
        <label class="field-label">Model</label>
        <input
          v-model="form.claude_model"
          class="text-input"
          type="text"
          :placeholder="settings?.claude?.model || 'claude-opus-4-5'"
        />
      </div>

      <!-- Status message -->
      <div v-if="statusMsg" class="status-msg" :class="statusType">
        {{ statusMsg }}
      </div>

      <!-- Actions -->
      <div class="panel-actions">
        <button class="btn-secondary" @click="$emit('close')">Cancel</button>
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save & Apply' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getLLMSettings, updateLLMSettings } from '../api/settings'

defineEmits(['close'])

const settings = ref(null)
const claudeConsoleUrl = ref('https://console.anthropic.com/settings/keys')
const saving = ref(false)
const statusMsg = ref('')
const statusType = ref('info')

const form = ref({
  provider: 'openai',
  openai_api_key: '',
  openai_base_url: '',
  openai_model: '',
  claude_api_key: '',
  claude_model: '',
})

onMounted(async () => {
  try {
    const res = await getLLMSettings()
    if (res?.data) {
      settings.value = res.data
      form.value.provider = res.data.provider || 'openai'
      if (res.data.claude?.console_url) {
        claudeConsoleUrl.value = res.data.claude.console_url
      }
    }
  } catch (e) {
    console.error('Failed to load LLM settings', e)
  }
})

async function save() {
  saving.value = true
  statusMsg.value = ''
  const payload = { provider: form.value.provider }
  if (form.value.openai_api_key)  payload.openai_api_key  = form.value.openai_api_key
  if (form.value.openai_base_url) payload.openai_base_url = form.value.openai_base_url
  if (form.value.openai_model)    payload.openai_model    = form.value.openai_model
  if (form.value.claude_api_key)  payload.claude_api_key  = form.value.claude_api_key
  if (form.value.claude_model)    payload.claude_model    = form.value.claude_model

  try {
    await updateLLMSettings(payload)
    statusMsg.value = `Provider set to "${form.value.provider}". Settings saved.`
    statusType.value = 'success'
  } catch (e) {
    statusMsg.value = e?.message || 'Failed to save settings'
    statusType.value = 'error'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.llm-settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.llm-settings-panel {
  background: #1a1a2e;
  border: 1px solid #2d2d4e;
  border-radius: 12px;
  width: 480px;
  max-width: 95vw;
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 15px;
  font-weight: 700;
  color: #e0e0f0;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 20px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.close-btn:hover { color: #e0e0f0; }

.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: #888;
  text-transform: uppercase;
}

.provider-toggle {
  display: flex;
  gap: 8px;
}

.toggle-btn {
  flex: 1;
  padding: 10px 0;
  border-radius: 8px;
  border: 1px solid #2d2d4e;
  background: #12122a;
  color: #888;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
}
.toggle-btn.active {
  background: #3a3aff20;
  border-color: #5555ff;
  color: #a0a0ff;
}
.toggle-btn:hover:not(.active) {
  border-color: #444466;
  color: #ccc;
}

.field-label {
  font-size: 11px;
  color: #aaa;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.text-input {
  background: #0d0d1a;
  border: 1px solid #2d2d4e;
  border-radius: 6px;
  color: #e0e0f0;
  font-size: 13px;
  padding: 9px 12px;
  outline: none;
  transition: border-color 0.15s;
  font-family: 'Courier New', monospace;
}
.text-input:focus { border-color: #5555ff; }
.text-input::placeholder { color: #444466; }

.claude-promo {
  background: #0d1a2e;
  border: 1px solid #1a3a5e;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.claude-desc {
  font-size: 12px;
  color: #aaa;
  line-height: 1.6;
  margin: 0;
}

.claude-link-btn {
  align-self: flex-start;
  background: #1a3a5e;
  border: 1px solid #2a5a8e;
  border-radius: 6px;
  color: #70b8ff;
  font-size: 12px;
  font-weight: 700;
  padding: 7px 14px;
  text-decoration: none;
  letter-spacing: 0.05em;
  transition: background 0.15s;
}
.claude-link-btn:hover {
  background: #1e4a7e;
  color: #90d0ff;
}

.status-msg {
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 12px;
}
.status-msg.success { background: #0d2e1a; color: #50d080; border: 1px solid #1a5e30; }
.status-msg.error   { background: #2e0d0d; color: #d05050; border: 1px solid #5e1a1a; }
.status-msg.info    { background: #0d1a2e; color: #70b8ff; border: 1px solid #1a3a5e; }

.panel-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.btn-secondary {
  background: none;
  border: 1px solid #2d2d4e;
  color: #888;
  border-radius: 6px;
  padding: 9px 18px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.15s;
}
.btn-secondary:hover { border-color: #444466; color: #ccc; }

.btn-primary {
  background: #3a3aff20;
  border: 1px solid #5555ff;
  color: #a0a0ff;
  border-radius: 6px;
  padding: 9px 18px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-primary:hover:not(:disabled) { background: #5555ff30; color: #c0c0ff; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
