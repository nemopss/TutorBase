import type { ThemeConfig } from "../types";

/** VS Code Dark+ inspired theme */
export const darkplusTheme: ThemeConfig = {
  id: "darkplus",
  name: "Dark+",
  colorScheme: "dark",
  colors: {
    bgPrimary: "#1e1e1e",
    bgSecondary: "#252526",
    bgTertiary: "#2d2d2d",
    textPrimary: "#d4d4d4",
    textSecondary: "#808080",
    textTertiary: "#5a5a5a",
    accentPrimary: "#0078d4",
    accentSuccess: "#4ec9b0",
    accentWarning: "#dcdcaa",
    accentError: "#f14c4c",
    accentInfo: "#569cd6",
    borderPrimary: "#3c3c3c",
    borderSecondary: "#2d2d2d",
  },
  previewColors: ["#0078d4", "#4ec9b0", "#ce9178", "#569cd6", "#1e1e1e"],
};
