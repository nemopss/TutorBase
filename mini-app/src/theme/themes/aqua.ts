import type { ThemeConfig } from "../types";

/** Aqua - bright teal light theme */
export const aquaTheme: ThemeConfig = {
  id: "aqua",
  name: "Aqua",
  colorScheme: "light",
  colors: {
    bgPrimary: "#ffffff",
    bgSecondary: "#f5f7fa",
    bgTertiary: "#eef1f5",
    textPrimary: "#2d3436",
    textSecondary: "#636e72",
    textTertiary: "#b2bec3",
    accentPrimary: "#00b4d8",
    accentSuccess: "#06d6a0",
    accentWarning: "#ffd166",
    accentError: "#ef476f",
    accentInfo: "#00b4d8",
    borderPrimary: "#dfe6e9",
    borderSecondary: "#eef1f5",
  },
  previewColors: ["#00b4d8", "#06d6a0", "#ffd166", "#ef476f", "#f5f7fa"],
};
