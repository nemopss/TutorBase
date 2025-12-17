import type { ThemeConfig } from "../types";

/** Gruvbox dark theme - warm retro colors */
export const gruvboxTheme: ThemeConfig = {
  id: "gruvbox",
  name: "Gruvbox",
  colorScheme: "dark",
  colors: {
    bgPrimary: "#282828",
    bgSecondary: "#3c3836",
    bgTertiary: "#504945",
    textPrimary: "#ebdbb2",
    textSecondary: "#a89984",
    textTertiary: "#665c54",
    accentPrimary: "#fe8019",
    accentSuccess: "#b8bb26",
    accentWarning: "#fabd2f",
    accentError: "#fb4934",
    accentInfo: "#83a598",
    borderPrimary: "#504945",
    borderSecondary: "#3c3836",
  },
  previewColors: ["#fe8019", "#fabd2f", "#b8bb26", "#83a598", "#282828"],
};
