import { useTheme } from "../theme/ThemeProvider";

export const useResponsiveStyles = () => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme.colorScheme === "dark";

  const cardStyle = {
    background: resolvedTheme.colors.bgSecondary,
    borderColor: resolvedTheme.colors.borderPrimary,
  };

  const textColor = resolvedTheme.colors.textPrimary;
  const subtitleColor = resolvedTheme.colors.textSecondary;
  const borderColor = resolvedTheme.colors.borderPrimary;
  const chartGridColor = resolvedTheme.colors.borderPrimary;

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
    colorScheme: resolvedTheme.colorScheme,
    isDark,
  };
};
