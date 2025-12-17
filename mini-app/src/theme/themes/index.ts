import type { ThemeConfig, ThemeId } from "../types";

import { lightTheme } from "./light";
import { darkTheme } from "./dark";
import { aquaTheme } from "./aqua";
import { tokyonightTheme } from "./tokyonight";
import { gruvboxTheme } from "./gruvbox";
import { darkplusTheme } from "./darkplus";

/** All available themes (excluding 'auto' which is resolved dynamically) */
export const themes: Record<Exclude<ThemeId, "auto">, ThemeConfig> = {
  light: lightTheme,
  dark: darkTheme,
  aqua: aquaTheme,
  tokyonight: tokyonightTheme,
  gruvbox: gruvboxTheme,
  darkplus: darkplusTheme,
};

/** Ordered list of all themes for UI display */
export const themeList: ThemeConfig[] = [
  lightTheme,
  darkTheme,
  aquaTheme,
  tokyonightTheme,
  gruvboxTheme,
  darkplusTheme,
];

/** All theme IDs including 'auto' */
export const allThemeIds: ThemeId[] = [
  "auto",
  "light",
  "dark",
  "aqua",
  "tokyonight",
  "gruvbox",
  "darkplus",
];

export {
  lightTheme,
  darkTheme,
  aquaTheme,
  tokyonightTheme,
  gruvboxTheme,
  darkplusTheme,
};
