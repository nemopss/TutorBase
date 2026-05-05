import React from 'react';
import { Skeleton } from 'antd';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeProvider';

interface PackageGridProps {
  /** Grid content */
  children: React.ReactNode;
  /** Show skeleton loading state */
  loading?: boolean;
  /** Number of skeleton cards to show (default: 6) */
  skeletonCount?: number;
}

/**
 * Responsive grid container for package cards.
 * - Mobile (< 768px): 2 columns
 * - Tablet (768-1024px): 3 columns
 * - Desktop (> 1024px): 4 columns
 */
const PackageGrid: React.FC<PackageGridProps> = ({
  children,
  loading = false,
  skeletonCount = 6,
}) => {
  const { isMobile, isTablet } = useResponsive();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;

  const getColumns = () => {
    if (isMobile) return 1;
    if (isTablet) return 2;
    return 3;
  };

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: `repeat(${getColumns()}, minmax(0, 1fr))`,
    gap: spacing.md,
    overflow: 'visible',
  };

  if (loading) {
    return (
      <div style={gridStyle}>
        {Array.from({ length: skeletonCount }).map((_, index) => (
          <div
            key={index}
            style={{
              minHeight: 132,
              padding: spacing.md,
              borderRadius: 10,
              background: colors.bgTertiary,
              border: 0,
              boxShadow: 'none',
            }}
          >
            <Skeleton active paragraph={{ rows: 2 }} />
          </div>
        ))}
      </div>
    );
  }

  return <div style={gridStyle}>{children}</div>;
};

export default PackageGrid;
