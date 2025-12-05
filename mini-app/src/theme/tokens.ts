/**
 * Design tokens for consistent spacing and responsive values.
 * Based on Ant Design's design system.
 */

/** Spacing scale (in pixels) */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

/** Gap values for flex/grid layouts */
export const gap = {
  small: 8,
  medium: 16,
  large: 24,
} as const;

/** Responsive content padding by device type */
export const contentPadding = {
  mobile: 16,
  tablet: 24,
  desktop: 32,
} as const;

/** Chart heights by device type */
export const chartHeight = {
  mobile: 200,
  desktop: 300,
} as const;

/** Minimum touch target size for accessibility (44x44px per WCAG) */
export const minTouchTarget = 44;

/** Breakpoint values in pixels (aligned with Ant Design) */
export const breakpoints = {
  xs: 576,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1600,
} as const;

/** Responsive values grouped for convenience */
export const responsive = {
  contentPadding,
  chartHeight,
  minTouchTarget,
  breakpoints,
} as const;

/** All tokens exported as single object */
export const tokens = {
  spacing,
  gap,
  responsive,
} as const;

export default tokens;
