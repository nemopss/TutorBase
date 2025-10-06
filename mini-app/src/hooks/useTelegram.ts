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

    tg.onEvent('themeChanged', handleThemeChange);

    // Set initial user data
    if (tg.initDataUnsafe?.user) {
      setUser(tg.initDataUnsafe.user);
    }

    return () => {
      tg.offEvent('themeChanged', handleThemeChange);
    };
  }, []);

  return {
    tg,
    user,
    themeParams,
    colorScheme: tg?.colorScheme || 'light',
  };
}
