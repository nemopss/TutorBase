import api from '../services/api';
import { appEnv } from '../env';

export interface User {
  id: number;
  display_name: string;
  role: string;
  telegram_id?: number;
  email?: string | null;
  email_verified_at?: string | null;
  tenant_id?: number | null;
  last_login_at?: string;
}

export interface BrowserAuthResponse {
  access_token: string;
  token_type?: string;
  user: User;
  expires_in?: number;
}

export interface EmailPasswordPayload {
  email: string;
  password: string;
}

export interface BrowserTutorRegistrationPayload extends EmailPasswordPayload {
  school_name: string;
  tutor_name?: string;
  offer_accepted: boolean;
  privacy_accepted: boolean;
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

export const loginWithEmail = async (
  payload: EmailPasswordPayload
): Promise<BrowserAuthResponse> => {
  const { data } = await api.post<BrowserAuthResponse>('/auth/browser/login-email', payload, {
    withCredentials: true,
  });
  return data;
};

export const registerTutorWithEmail = async (
  payload: BrowserTutorRegistrationPayload
): Promise<BrowserAuthResponse> => {
  const { data } = await api.post<BrowserAuthResponse>('/auth/browser/register-tutor-email', payload, {
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

export const refreshCookieSession = async (): Promise<BrowserAuthResponse> => {
  const { data } = await api.post<BrowserAuthResponse>('/auth/session/refresh', undefined, {
    withCredentials: true,
  });
  return data;
};

export const logoutBrowserSession = async (): Promise<void> => {
  await api.post('/auth/browser/logout', undefined, {
    withCredentials: true,
  });
};

export const logoutCookieSession = async (): Promise<void> => {
  await api.post('/auth/session/logout', undefined, {
    withCredentials: true,
  });
};
