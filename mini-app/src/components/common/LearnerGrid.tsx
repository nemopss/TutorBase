import React from 'react';
import { Card, Skeleton } from 'antd';
import { spacing } from '../../theme/tokens';

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
  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: spacing.md,
  };

  if (loading) {
    return (
      <div style={gridStyle}>
        {Array.from({ length: skeletonCount }).map((_, index) => (
          <Card key={index} style={{ minHeight: 180 }}>
            <Skeleton
              active
              avatar
              title={{ width: '54%' }}
              paragraph={{ rows: 3 }}
            />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div style={gridStyle}>{children}</div>
  );
};

export default LearnerGrid;
