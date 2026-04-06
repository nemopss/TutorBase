import type { PropsWithChildren } from 'react';

const resolvedTheme = {
  id: 'light',
  name: 'Light',
  colorScheme: 'light',
  colors: {
    bgPrimary: '#ffffff',
    bgSecondary: '#f7f7f5',
    bgTertiary: '#f0f0ee',
    textPrimary: '#37352f',
    textSecondary: '#6b6b6b',
    textTertiary: '#9b9b9b',
    accentPrimary: '#2383e2',
    accentSuccess: '#0f7b6c',
    accentWarning: '#e16259',
    accentError: '#eb5757',
    accentInfo: '#2383e2',
    borderPrimary: '#e8e8e8',
    borderSecondary: '#f0f0f0',
  },
  previewColors: ['#2383e2', '#0f7b6c', '#37352f', '#f7f7f5', '#ffffff'],
};

export const ThemeProvider = ({ children }: PropsWithChildren) => <>{children}</>;

export const useTheme = () => ({
  themeId: 'light',
  resolvedTheme,
  setThemeId: () => undefined,
  availableThemes: [],
});

export const useThemeMode = useTheme;
