/**
 * Nightwatch hook — manages configuration state for the Nightwatch daily digest feature.
 * Loads settings on mount; saves to `/api/settings/nightwatch` PATCH endpoint.
 * Follows the same pattern as useWebhookSettings / useNetworkProfile.
 */
import { useEffect, useState } from "react";
import type {
  NightwatchConfig,
  NightwatchConfigUpdate,
  NightwatchListModelsResult,
  NightwatchLlmType,
  NightwatchPreviewResult,
} from "../types/nightwatch";

export function useNightwatchConfig() {
  const [config, setConfig] = useState<NightwatchConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [modelLoading, setModelLoading] = useState(false);
  const [preview, setPreview] = useState<NightwatchPreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/settings/nightwatch")
      .then((r) => r.json())
      .then((d: NightwatchConfig) => {
        setConfig(d);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = (update: NightwatchConfigUpdate) => {
    setSaving(true);
    setError(null);
    setPreview(null);
    fetch("/api/settings/nightwatch", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: NightwatchConfig) => {
        setConfig(d);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setSaving(false));
  };

  const test = () => {
    setTesting(true);
    setPreview(null);
    fetch("/api/settings/nightwatch/test", { method: "POST" })
      .then((r) => r.json())
      .then((d: NightwatchPreviewResult) => {
        setPreview(d);
      })
      .catch(() => setError("Test request failed"))
      .finally(() => setTesting(false));
  };

  const listModels = () => {
    setModelLoading(true);
    setModels([]);
    fetch("/api/settings/nightwatch/models", { method: "POST" })
      .then((r) => r.json())
      .then((d: NightwatchListModelsResult) => {
        setModels(d.models || []);
      })
      .catch(() => setError("Failed to list models"))
      .finally(() => setModelLoading(false));
  };

  const updateEnabled = (value: boolean) => {
    save({ enabled: value ? "true" : "false" });
  };

  const updateLlmType = (value: NightwatchLlmType) => {
    save({ llm_type: value });
  };

  const updateLlmEndpoint = (value: string) => {
    save({ llm_endpoint: value || null });
  };

  const updateLlmModel = (value: string) => {
    save({ llm_model: value || null });
  };

  const updateLlmApiKey = (value: string) => {
    save({ llm_api_key: value || null });
  };

  const updateTelegramBotToken = (value: string) => {
    save({ telegram_bot_token: value || null });
  };

  const updateTelegramChatId = (value: string) => {
    save({ telegram_chat_id: value || null });
  };

  const updateNtopngUrl = (value: string) => {
    save({ ntopng_url: value || null });
  };

  const updateNtopngUsername = (value: string) => {
    save({ ntopng_username: value || null });
  };

  const updateNtopngPassword = (value: string) => {
    save({ ntopng_password: value || null });
  };

  const updateCrowdsecUrl = (value: string) => {
    save({ crowdsec_url: value || null });
  };

  const updateCrowdsecApiKey = (value: string) => {
    save({ crowdsec_api_key: value || null });
  };

  const llmEndpoint = config?.llm_endpoint || "";
  const llmModel = config?.llm_model || "";
  const telegramBotTokenSet = config?.telegram_bot_token_set || false;
  const telegramChatIdSet = config?.telegram_chat_id_set || false;

  return {
    config,
    loading,
    saving,
    testing,
    models,
    modelLoading,
    preview,
    error,
    llmEndpoint,
    llmModel,
    telegramBotTokenSet,
    telegramChatIdSet,
    updateEnabled,
    updateLlmType,
    updateLlmEndpoint,
    updateLlmModel,
    updateLlmApiKey,
    updateTelegramBotToken,
    updateTelegramChatId,
    updateNtopngUrl,
    updateNtopngUsername,
    updateNtopngPassword,
    updateCrowdsecUrl,
    updateCrowdsecApiKey,
    test,
    listModels,
  };
}
