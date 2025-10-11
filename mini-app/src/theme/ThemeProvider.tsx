import type { PropsWithChildren } from 'react';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { useTelegram } from '../hooks/useTelegram';

export type ThemeMode = 'auto' | 'light' | 'dark';
export type ResolvedTheme = 'light' | 'dark';

interface ThemeContextValue {
  mode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = 'ksu-theme-mode';

function readStoredMode(): ThemeMode {
    if (typeof window === 'undefined') {
        return 'auto';
    }
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'auto') {
        return stored;
    }
    return 'auto';
}

export const ThemeProvider = ({ children }: PropsWithChildren) => {
  const { colorScheme } = useTelegram();
  const [mode, setModeState] = useState<ThemeMode>(() => readStoredMode());

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, mode);
    }
  }, [mode]);

  const resolvedTheme: ResolvedTheme = mode === 'auto'
    ? (colorScheme === 'dark' ? 'dark' : 'light')
    : mode;

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      resolvedTheme,
      setMode,
    }),
    [mode, resolvedTheme, setMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useThemeMode = (): ThemeContextValue => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemeMode must be used within ThemeProvider');
  }
  return context;
};
