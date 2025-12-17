/**
 * Theme system type definitions
 */

/** All available theme identifiers */
export type ThemeId =
  | "auto"
  | "light"
  | "dark"
  | "aqua"
  | "tokyonight"
  | "gruvbox"
  | "darkplus";

/** Base color scheme type */
export type ColorScheme = "light" | "dark";

/** Complete color palette for a theme */
export interface ThemeColors {
  // Backgrounds
  bgPrimary: string; // Main background
  bgSecondary: string; // Card/container background
  bgTertiary: string; // Hover states, subtle backgrounds

  // Text
  textPrimary: string; // Main text color
  textSecondary: string; // Muted text
  textTertiary: string; // Disabled/placeholder text

  // Accents
  accentPrimary: string; // Primary action color (buttons, links)
  accentSuccess: string; // Success states
  accentWarning: string; // Warning states
  accentError: string; // Error states
  accentInfo: string; // Info states

  // Borders
  borderPrimary: string; // Default borders
  borderSecondary: string; // Subtle borders
}

/** Complete theme configuration */
export interface ThemeConfig {
  id: ThemeId;
  name: string;
  colorScheme: ColorScheme;
  colors: ThemeColors;
  previewColors: string[]; // 4-5 colors for card preview
}

/** Theme context value exposed to components */
export interface ThemeContextValue {
  themeId: ThemeId;
  resolvedTheme: ThemeConfig;
  setThemeId: (id: ThemeId) => void;
  availableThemes: ThemeConfig[];
}
