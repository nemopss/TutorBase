import React from 'react';
import { Skeleton } from 'antd';
import { spacing } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeProvider';

interface LearnerGridProps {
  children?: React.ReactNode;
  loading?: boolean;
  skeletonCount?: number;
}

/**
 * Responsive grid layout for learner cards.
 * - 3 columns on desktop (≥992px)
 * - 2 columns on tablet (768-991px)
 * - 1 column on mobile (<768px)
 */
const LearnerGrid: React.FC<LearnerGridProps> = ({
  children,
  loading = false,
  skeletonCount = 6,
}) => {
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: spacing.md,
  };

  if (loading) {
    return (
      <div style={gridStyle}>
        {Array.from({ length: skeletonCount }).map((_, index) => (
          <div
            key={index}
            style={{
              minHeight: 136,
              padding: spacing.md,
              borderRadius: 10,
              background: colors.bgTertiary,
              border: 0,
              boxShadow: 'none',
            }}
          >
            <Skeleton
              active
              avatar
              title={{ width: '54%' }}
              paragraph={{ rows: 3 }}
            />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={gridStyle}>{children}</div>
  );
};

export default LearnerGrid;
