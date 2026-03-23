import service from './index'

/**
 * Fetch current LLM provider settings.
 * Returned keys are masked for safety.
 */
export function getLLMSettings() {
  return service({ url: '/api/settings/llm', method: 'get' })
}

/**
 * Update LLM provider settings.
 * @param {Object} data
 * @param {'openai'|'claude'} data.provider
 * @param {string} [data.openai_api_key]
 * @param {string} [data.openai_base_url]
 * @param {string} [data.openai_model]
 * @param {string} [data.claude_api_key]
 * @param {string} [data.claude_model]
 */
export function updateLLMSettings(data) {
  return service({ url: '/api/settings/llm', method: 'post', data })
}

/**
 * Fetch the Anthropic Console URL (where users get a Claude API key).
 */
export function getClaudeConsoleUrl() {
  return service({ url: '/api/settings/claude-console-url', method: 'get' })
}
