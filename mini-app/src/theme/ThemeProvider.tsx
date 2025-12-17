import type { PropsWithChildren } from 'react';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { useTelegram } from '../hooks/useTelegram';
import type { ThemeConfig, ThemeContextValue, ThemeId } from './types';
import { themes, themeList, allThemeIds } from './themes';

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = 'tutorbase-theme-id';

/** Validate and read stored theme ID */
function readStoredThemeId(): ThemeId {
  if (typeof window === 'undefined') {
    return 'auto';
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored && allThemeIds.includes(stored as ThemeId)) {
    return stored as ThemeId;
  }
  return 'auto';
}

/** Save theme ID to localStorage */
function saveThemeId(themeId: ThemeId): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, themeId);
  }
}

export const ThemeProvider = ({ children }: PropsWithChildren) => {
  const { colorScheme } = useTelegram();
  const [themeId, setThemeIdState] = useState<ThemeId>(() => readStoredThemeId());

  // Persist theme selection
  useEffect(() => {
    saveThemeId(themeId);
  }, [themeId]);

  // Resolve the actual theme config based on themeId
  const resolvedTheme: ThemeConfig = useMemo(() => {
    if (themeId === 'auto') {
      // Follow Telegram color scheme
      return colorScheme === 'dark' ? themes.dark : themes.light;
    }
    return themes[themeId];
  }, [themeId, colorScheme]);

  const setThemeId = useCallback((id: ThemeId) => {
    setThemeIdState(id);
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      themeId,
      resolvedTheme,
      setThemeId,
      availableThemes: themeList,
    }),
    [themeId, resolvedTheme, setThemeId],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = (): ThemeContextValue => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

// Legacy export for backward compatibility during migration
export const useThemeMode = useTheme;
