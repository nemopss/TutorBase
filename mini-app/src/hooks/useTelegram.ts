import { useEffect, useMemo, useState } from 'react';

const tg = window.Telegram?.WebApp;

export function useTelegram() {
  const [user, setUser] = useState(tg?.initDataUnsafe?.user || null);
  const [themeParams, setThemeParams] = useState(tg?.themeParams || {});
  const shouldRequestFullscreen = useMemo(() => {
    if (!tg) {
      return false;
    }

    const nav = typeof navigator !== 'undefined' ? navigator : undefined;
    const userAgent = nav?.userAgent?.toLowerCase() || '';
    const isIosUA = /iphone|ipad|ipod/.test(userAgent);
    const isTouchMac = /macintosh/.test(userAgent) && (nav?.maxTouchPoints || 0) > 1;
    const platformHints = tg.platform === 'ios' || tg.platform === 'macos';

    return isIosUA || isTouchMac || platformHints;
  }, []);

  useEffect(() => {
    if (!tg) return;

    const requestFullscreenSafe = () => {
      if (!shouldRequestFullscreen) return;

      try {
        const possiblePromise = tg.requestFullscreen?.();
        if (possiblePromise && typeof possiblePromise === 'object' && 'catch' in possiblePromise) {
          (possiblePromise as Promise<void>).catch(() => undefined);
        }
      } catch {
        // Игнорируем ошибки — на некоторых платформах метод может быть недоступен
      }
    };

    const ensureExpanded = () => {
      if (!tg.isExpanded) {
        tg.expand();
      }
      requestFullscreenSafe();
    };

    const handleThemeChange = () => {
      setThemeParams(tg.themeParams);
    };

    const handleViewportChange = () => {
      // Принудительно разворачиваем при изменении viewport
      ensureExpanded();
    };

    tg.onEvent('themeChanged', handleThemeChange);
    tg.onEvent('viewportChanged', handleViewportChange);

    // Set initial user data
    if (tg.initDataUnsafe?.user) {
      setUser(tg.initDataUnsafe.user);
    }

    ensureExpanded();

    // Дополнительные попытки развернуть приложение помогают на iPad
    const timeouts: ReturnType<typeof setTimeout>[] = [120, 360, 1000].map((delay) =>
      setTimeout(ensureExpanded, delay)
    );

    return () => {
      timeouts.forEach(clearTimeout);
      tg.offEvent('themeChanged', handleThemeChange);
      tg.offEvent('viewportChanged', handleViewportChange);
    };
  }, [shouldRequestFullscreen]);

  return {
    tg,
    user,
    themeParams,
    colorScheme: tg?.colorScheme || 'light',
    shouldRequestFullscreen,
  };
}
