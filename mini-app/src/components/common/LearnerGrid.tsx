import React from 'react';
import { Spin } from 'antd';
import { spacing } from '../../theme/tokens';

interface LearnerGridProps {
  children?: React.ReactNode;
  loading?: boolean;
}

/**
 * Responsive grid layout for learner cards.
 * - 3 columns on desktop (≥992px)
 * - 2 columns on tablet (768-991px)
 * - 1 column on mobile (<768px)
 */
const LearnerGrid: React.FC<LearnerGridProps> = ({ children, loading = false }) => {
  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 200,
          padding: spacing.lg,
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: spacing.md,
      }}
    >
      {children}
    </div>
  );
};

export default LearnerGrid;
