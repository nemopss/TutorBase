import React from 'react';
import { Skeleton, Card } from 'antd';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';

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

  const getColumns = () => {
    if (isMobile) return 2;
    if (isTablet) return 3;
    return 4;
  };

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: `repeat(${getColumns()}, 1fr)`,
    gap: spacing.md,
  };

  if (loading) {
    return (
      <div style={gridStyle}>
        {Array.from({ length: skeletonCount }).map((_, index) => (
          <Card key={index} style={{ minHeight: 140 }}>
            <Skeleton active paragraph={{ rows: 2 }} />
          </Card>
        ))}
      </div>
    );
  }

  return <div style={gridStyle}>{children}</div>;
};

export default PackageGrid;
