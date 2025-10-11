import { useCallback, useEffect, useMemo, useState } from 'react';

const tg = window.Telegram?.WebApp;

function swallowPromiseRejection(result: unknown) {
  if (
    typeof result === 'object' &&
    result !== null &&
    'catch' in result &&
    typeof (result as { catch: unknown }).catch === 'function'
  ) {
    (result as Promise<unknown>).catch(() => undefined);
  }
}

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

  const requestFullscreenSafe = useCallback(() => {
    if (!tg || !shouldRequestFullscreen) {
      return;
    }

    try {
      const result = tg.requestFullscreen?.() as unknown;
      swallowPromiseRejection(result);
    } catch {
      // Игнорируем ошибки — на некоторых платформах метод может быть недоступен
    }
  }, [shouldRequestFullscreen]);

  useEffect(() => {
    if (!tg) return;

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
  }, [requestFullscreenSafe]);

  return {
    tg,
    user,
    themeParams,
    colorScheme: tg?.colorScheme || 'light',
    shouldRequestFullscreen,
    requestFullscreen: requestFullscreenSafe,
  };
}
