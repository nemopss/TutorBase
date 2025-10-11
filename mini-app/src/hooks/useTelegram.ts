import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

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
  const autoFullscreenEnabled = useMemo(() => {
    if (!tg) {
      return false;
    }

    const nav = typeof navigator !== 'undefined' ? navigator : undefined;
    const userAgent = nav?.userAgent?.toLowerCase() || '';
    const isIosUA = /iphone|ipad|ipod/.test(userAgent);
    const isIpadUA = /ipad/.test(userAgent);
    const isTouchMac = /macintosh/.test(userAgent) && (nav?.maxTouchPoints || 0) > 1;
    const screenSize = typeof window !== 'undefined' ? Math.max(window.screen.width, window.screen.height) : 0;
    const looksLikeTablet = screenSize >= 1024;
    const isIpadLikeDevice = isIpadUA || (isTouchMac && looksLikeTablet);
    const platformHints = tg.platform === 'macos';

    if (platformHints) {
      return (nav?.maxTouchPoints || 0) > 1 && looksLikeTablet;
    }

    if (isIpadLikeDevice) {
      return true;
    }

    if (isIosUA) {
      return false;
    }

    return false;
  }, []);
  const fullscreenDismissedRef = useRef(false);

  const requestFullscreenSafe = useCallback(() => {
    if (!tg || !autoFullscreenEnabled || fullscreenDismissedRef.current) {
      return;
    }

    try {
      if (!tg.isExpanded) {
        tg.expand();
      }
      const result = tg.requestFullscreen?.() as unknown;
      swallowPromiseRejection(result);
    } catch {
      // Игнорируем ошибки — на некоторых платформах метод может быть недоступен
    }
  }, [autoFullscreenEnabled]);

  const expandViewport = useCallback(() => {
    if (!tg) {
      return;
    }
    try {
      tg.expand();
    } catch {
      // Безопасно игнорируем — expand может быть недоступен на некоторых клиентах
    }
  }, []);

  useEffect(() => {
    if (!tg) return;
    fullscreenDismissedRef.current = false;

    const ensureExpanded = () => {
      expandViewport();
      requestFullscreenSafe();
    };

    const handleThemeChange = () => {
      setThemeParams(tg.themeParams);
    };

    const handleViewportChange = () => {
      expandViewport();
      requestFullscreenSafe();
    };

    const handleFullscreenChanged = (next?: boolean | { isFullscreen?: boolean }) => {
      if (fullscreenDismissedRef.current) {
        return;
      }
      const isFullscreen =
        typeof next === 'boolean'
          ? next
          : typeof next === 'object' && next !== null && 'isFullscreen' in next
            ? Boolean(next.isFullscreen)
            : undefined;
      if (isFullscreen === false) {
        fullscreenDismissedRef.current = true;
      }
    };

    tg.onEvent('themeChanged', handleThemeChange);
    tg.onEvent('viewportChanged', handleViewportChange);
    tg.onEvent('fullscreenChanged', handleFullscreenChanged);

    // Set initial user data
    if (tg.initDataUnsafe?.user) {
      setUser(tg.initDataUnsafe.user);
    }

    ensureExpanded();

    const timeouts: ReturnType<typeof setTimeout>[] = autoFullscreenEnabled
      ? [120, 360, 1000].map((delay) =>
          setTimeout(() => {
            if (!fullscreenDismissedRef.current) {
              ensureExpanded();
            }
          }, delay)
        )
      : [];

    return () => {
      timeouts.forEach(clearTimeout);
      tg.offEvent('themeChanged', handleThemeChange);
      tg.offEvent('viewportChanged', handleViewportChange);
      tg.offEvent('fullscreenChanged', handleFullscreenChanged);
    };
  }, [autoFullscreenEnabled, expandViewport, requestFullscreenSafe]);

  return {
    tg,
    user,
    themeParams,
    colorScheme: tg?.colorScheme || 'light',
    autoFullscreenEnabled,
    requestFullscreen: requestFullscreenSafe,
  };
}
