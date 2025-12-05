import { Grid } from "antd";

export type Breakpoint = "xs" | "sm" | "md" | "lg" | "xl" | "xxl";

export interface ResponsiveState {
  /** Viewport < 768px */
  isMobile: boolean;
  /** Viewport 768px - 1024px */
  isTablet: boolean;
  /** Viewport > 1024px */
  isDesktop: boolean;
  /** Current Ant Design breakpoint */
  breakpoint: Breakpoint;
  /** Raw breakpoint object from Ant Design */
  screens: ReturnType<typeof Grid.useBreakpoint>;
}

/**
 * Hook for responsive layout detection using Ant Design breakpoints.
 *
 * Breakpoints:
 * - xs: < 576px (small mobile)
 * - sm: ≥ 576px (mobile)
 * - md: ≥ 768px (tablet)
 * - lg: ≥ 992px (small desktop)
 * - xl: ≥ 1200px (desktop)
 * - xxl: ≥ 1600px (large desktop)
 *
 * @example
 * const { isMobile, isDesktop, breakpoint } = useResponsive();
 *
 * if (isMobile) {
 *   return <CardView />;
 * }
 * return <TableView />;
 */
export function useResponsive(): ResponsiveState {
  const screens = Grid.useBreakpoint();

  // Determine current breakpoint (highest active)
  const breakpoint: Breakpoint = screens.xxl
    ? "xxl"
    : screens.xl
    ? "xl"
    : screens.lg
    ? "lg"
    : screens.md
    ? "md"
    : screens.sm
    ? "sm"
    : "xs";

  // Primary breakpoint is 768px (md)
  const isMobile = !screens.md;
  const isTablet = !!screens.md && !screens.lg;
  const isDesktop = !!screens.lg;

  return {
    isMobile,
    isTablet,
    isDesktop,
    breakpoint,
    screens,
  };
}

export default useResponsive;
