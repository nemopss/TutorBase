import type { ThemeConfig as AntdThemeConfig } from "antd";
import { theme } from "antd";
import type { ThemeConfig } from "./types";

/**
 * Generate Ant Design theme configuration from ThemeConfig
 */
export function generateAntdTheme(themeConfig: ThemeConfig): AntdThemeConfig {
  const { colors, colorScheme } = themeConfig;
  const isDark = colorScheme === "dark";

  return {
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: colors.accentPrimary,
      colorSuccess: colors.accentSuccess,
      colorWarning: colors.accentWarning,
      colorError: colors.accentError,
      colorInfo: colors.accentInfo,
      colorTextBase: colors.textPrimary,
      colorBgBase: colors.bgPrimary,
      colorBgContainer: colors.bgSecondary,
      colorBorder: colors.borderPrimary,
      borderRadius: 6,
      fontSize: 14,
      fontFamily:
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, "Apple Color Emoji", Arial, sans-serif, "Segoe UI Emoji", "Segoe UI Symbol"',
    },
    components: {
      Card: {
        borderRadiusLG: 8,
        boxShadowTertiary: isDark ? "none" : "0 1px 2px rgba(0, 0, 0, 0.05)",
      },
      Table: {
        borderRadius: 6,
        headerBg: colors.bgTertiary,
      },
      Menu: {
        itemBg: "transparent",
        itemSelectedBg: isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.04)",
        itemSelectedColor: colors.textPrimary,
        itemColor: colors.textSecondary,
        itemHoverBg: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.03)",
        itemHoverColor: colors.textPrimary,
        iconSize: 18,
        itemHeight: 36,
        itemMarginInline: 4,
        itemBorderRadius: 4,
      },
      Layout: {
        siderBg: "transparent",
        bodyBg: colors.bgSecondary,
      },
      Button: {
        borderRadius: 8,
        controlHeight: 36,
      },
      Input: {
        borderRadius: 8,
        controlHeight: 36,
      },
      Select: {
        borderRadius: 8,
        controlHeight: 36,
      },
    },
  };
}
