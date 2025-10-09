import { useEffect, useState } from 'react';

const tg = window.Telegram?.WebApp;

export function useTelegram() {
  const [user, setUser] = useState(tg?.initDataUnsafe?.user || null);
  const [themeParams, setThemeParams] = useState(tg?.themeParams || {});

  useEffect(() => {
    if (!tg) return;

    const handleThemeChange = () => {
      setThemeParams(tg.themeParams);
    };

    const handleViewportChange = () => {
      // Принудительно разворачиваем при изменении viewport
      if (!tg.isExpanded) {
        tg.expand();
      }
    };

    tg.onEvent('themeChanged', handleThemeChange);
    tg.onEvent('viewportChanged', handleViewportChange);

    // Set initial user data
    if (tg.initDataUnsafe?.user) {
      setUser(tg.initDataUnsafe.user);
    }

    // Дополнительная попытка развернуть через небольшую задержку
    // Помогает на iPad где первый вызов может не сработать
    const expandTimer = setTimeout(() => {
      if (!tg.isExpanded) {
        tg.expand();
      }
    }, 100);

    return () => {
      clearTimeout(expandTimer);
      tg.offEvent('themeChanged', handleThemeChange);
      tg.offEvent('viewportChanged', handleViewportChange);
    };
  }, []);

  return {
    tg,
    user,
    themeParams,
    colorScheme: tg?.colorScheme || 'light',
  };
}
