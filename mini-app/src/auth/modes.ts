export type AuthMode = 'dev' | 'telegram-webapp' | 'browser';

import { appEnv } from '../env';

export const detectAuthMode = (): AuthMode => {
  if (appEnv.devMode) {
    return 'dev';
  }

  const webApp = window.Telegram?.WebApp;
  if (webApp?.initData && webApp.initData.length > 0) {
    return 'telegram-webapp';
  }

  return 'browser';
};

export const prepareTelegramWebApp = () => {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return;
  }

  webApp.ready();
  webApp.expand();
};
