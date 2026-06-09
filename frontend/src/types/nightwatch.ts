/**
 * Nightwatch shared TypeScript types.
 */

export type NightwatchLlmType = "ollama" | "openai_compatible";

export interface NightwatchConfig {
  enabled: string | null;
  llm_type: NightwatchLlmType | null;
  llm_endpoint: string | null;
  llm_model: string | null;
  telegram_bot_token_set: boolean;
  telegram_chat_id_set: boolean;
  ntopng_url: string | null;
  ntopng_username_set: boolean;
  crowdsec_url: string | null;
  crowdsec_api_key_set: boolean;
}

export interface NightwatchConfigUpdate {
  enabled?: string | null;
  llm_type?: NightwatchLlmType | null;
  llm_endpoint?: string | null;
  llm_model?: string | null;
  llm_api_key?: string | null;
  telegram_bot_token?: string | null;
  telegram_chat_id?: string | null;
  ntopng_url?: string | null;
  ntopng_username?: string | null;
  ntopng_password?: string | null;
  crowdsec_url?: string | null;
  crowdsec_api_key?: string | null;
}

export interface NightwatchPreviewResult {
  success: boolean;
  text?: string | null;
  error: string | null;
  findings_count?: number;
  actions_count?: number;
  message?: string;
  status_code?: number;
}

export interface NightwatchListModelsResult {
  models: string[];
  error?: string | null;
}
