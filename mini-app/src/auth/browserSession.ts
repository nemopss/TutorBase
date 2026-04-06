import api from '../services/api';
import { appEnv } from '../env';

export interface User {
  id: number;
  display_name: string;
  role: string;
  telegram_id?: number;
  tenant_id?: number | null;
  last_login_at?: string;
}

export interface BrowserAuthResponse {
  access_token: string;
  token_type?: string;
  user: User;
  expires_in?: number;
}

export interface TelegramLoginWidgetPayload {
  id: number | string;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number | string;
  hash: string;
}

export const getTelegramBotUsername = () =>
  appEnv.telegramBotUsername.trim();

export const loginWithTelegramWidget = async (
  payload: TelegramLoginWidgetPayload
): Promise<BrowserAuthResponse> => {
  const { data } = await api.post<BrowserAuthResponse>('/auth/browser/telegram', payload, {
    withCredentials: true,
  });
  return data;
};

export const refreshBrowserSession = async (): Promise<BrowserAuthResponse> => {
  const { data } = await api.post<BrowserAuthResponse>('/auth/browser/refresh', undefined, {
    withCredentials: true,
  });
  return data;
};

export const logoutBrowserSession = async (): Promise<void> => {
  await api.post('/auth/browser/logout', undefined, {
    withCredentials: true,
  });
};
