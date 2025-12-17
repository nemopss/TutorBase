import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import dayjs from "dayjs";
import "dayjs/locale/ru";
import "dayjs/locale/en";
import "dayjs/locale/ko";

// Translation resources
import ru from "./locales/ru.json";
import en from "./locales/en.json";
import ko from "./locales/ko.json";

export const SUPPORTED_LANGUAGES = ["ru", "en", "ko"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  ru: "Русский",
  en: "English",
  ko: "한국어",
};

export const LANGUAGE_FLAGS: Record<SupportedLanguage, string> = {
  ru: "🇷🇺",
  en: "🇬🇧",
  ko: "🇰🇷",
};

// Custom language detector for Telegram WebApp
const telegramLanguageDetector = {
  name: "telegramDetector",
  lookup(): string | undefined {
    try {
      const tg = window.Telegram?.WebApp;
      const langCode = tg?.initDataUnsafe?.user?.language_code;
      if (
        langCode &&
        SUPPORTED_LANGUAGES.includes(langCode as SupportedLanguage)
      ) {
        return langCode;
      }
      // Map common language codes to supported ones
      if (langCode?.startsWith("ru")) return "ru";
      if (langCode?.startsWith("en")) return "en";
      if (langCode?.startsWith("ko")) return "ko";
    } catch {
      // Telegram WebApp not available
    }
    return undefined;
  },
  cacheUserLanguage(): void {
    // We use localStorage caching from the standard detector
  },
};

const languageDetector = new LanguageDetector();
languageDetector.addDetector(telegramLanguageDetector);

i18n
  .use(languageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      ru: { translation: ru },
      en: { translation: en },
      ko: { translation: ko },
    },
    fallbackLng: "ru",
    supportedLngs: SUPPORTED_LANGUAGES as unknown as string[],
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    detection: {
      order: ["localStorage", "telegramDetector", "navigator"],
      lookupLocalStorage: "language",
      caches: ["localStorage"],
    },
    react: {
      useSuspense: false, // Disable suspense for simpler error handling
    },
  });

// Sync dayjs locale on init and language change
const syncDayjsLocale = (lang: string) => {
  const supportedLang = SUPPORTED_LANGUAGES.includes(lang as SupportedLanguage)
    ? lang
    : "ru";
  dayjs.locale(supportedLang);
};

// Set initial dayjs locale
syncDayjsLocale(i18n.language);

// Listen for language changes
i18n.on("languageChanged", syncDayjsLocale);

export default i18n;

// Helper function to change language
export const changeLanguage = (lang: SupportedLanguage): Promise<void> => {
  return i18n.changeLanguage(lang).then(() => {
    localStorage.setItem("language", lang);
    // Sync dayjs locale
    dayjs.locale(lang);
  });
};

// Helper to get current language
export const getCurrentLanguage = (): SupportedLanguage => {
  const lang = i18n.language;
  if (SUPPORTED_LANGUAGES.includes(lang as SupportedLanguage)) {
    return lang as SupportedLanguage;
  }
  return "ru";
};
