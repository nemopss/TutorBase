/// <reference types="@types/telegram-web-app" />

declare global {
  interface Window {
    Telegram?: TelegramWebApp.WebApp;
    __tutorbaseTelegramLogin?: (user: {
      id: number | string;
      first_name?: string;
      last_name?: string;
      username?: string;
      photo_url?: string;
      auth_date: number | string;
      hash: string;
    }) => void;
  }
}

export {};
