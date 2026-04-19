export const appEnv = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  apiTimeoutMs: Number(import.meta.env.VITE_API_TIMEOUT) || 15000,
  isDev: import.meta.env.DEV,
  devMode: import.meta.env.VITE_DEV_MODE === 'true',
  devInitData: import.meta.env.VITE_DEV_INIT_DATA ?? 'dev',
  telegramBotUsername: import.meta.env.VITE_TELEGRAM_BOT_USERNAME ?? '',
  supportContactUrl: import.meta.env.VITE_SUPPORT_CONTACT_URL ?? '',
};
