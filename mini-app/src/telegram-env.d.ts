/// <reference types="@types/telegram-web-app" />

declare global {
  interface Window {
    Telegram?: TelegramWebApp.WebApp;
  }
}

export {};
