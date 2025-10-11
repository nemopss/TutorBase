import { useThemeMode } from '../theme/ThemeProvider';

export const useResponsiveStyles = () => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const cardStyle = {
    background: isDark ? '#1f1f1f' : '#ffffff',
    borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
  };

  const textColor = isDark ? '#ffffff' : '#000000';
  const subtitleColor = isDark ? '#a0a0a0' : '#8c8c8c';
  const borderColor = isDark ? '#3a3a3a' : '#e8e8e8';
  const chartGridColor = isDark ? '#3a3a3a' : '#e8e8e8';

  const tooltipStyle = {
    backgroundColor: cardStyle.background,
    borderColor: cardStyle.borderColor,
    color: textColor,
  };

  return {
    cardStyle,
    textColor,
    subtitleColor,
    borderColor,
    chartGridColor,
    tooltipStyle,
    colorScheme: resolvedTheme,
  };
};
