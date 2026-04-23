import React, { useState } from 'react';
import { Card, Progress, Typography, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface PackageProgress {
  total: number;
  completed: number;
  cancelled: number;
}

interface Package {
  id: number;
  title: string;
  learner_name: string;
  status: 'active' | 'completed' | 'cancelled' | 'draft';
  progress: PackageProgress;
  next_lesson_date?: string | null;
}

interface PackageCardProps {
  package: Package;
  onClick?: () => void;
}

/**
 * Get badge color for package status
 */
export const getStatusBadgeColor = (status: string): string => {
  switch (status) {
    case 'active': return 'green';
    case 'completed': return 'blue';
    case 'draft': return 'orange';
    case 'cancelled': return 'red';
    default: return 'default';
  }
};

/**
 * Package card with new layout:
 * - Title + learner name on the left
 * - Progress ring on the right (no percentage)
 * - Lesson count + status badge
 * - Next lesson date (for active packages)
 */
const PackageCard: React.FC<PackageCardProps> = ({
  package: pkg,
  onClick,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const [isPressed, setIsPressed] = useState(false);

  const progress = pkg.progress || { total: 0, completed: 0, cancelled: 0 };
  const percent = progress.total > 0
    ? Math.round(((progress.completed + progress.cancelled) / progress.total) * 100)
    : 0;

  const isActive = pkg.status === 'active';

  // Format lesson count
  const formatLessonCount = (): string => {
    const done = progress.completed + progress.cancelled;
    return `${done}/${progress.total} ${t('pages.packages.lessons')}`;
  };

  // Format next lesson date
  const formatNextLessonDate = (dateStr?: string | null): string => {
    if (!dateStr) return t('packageCard.noScheduled');
    
    const formattedDate = dayjs(dateStr).format('D MMM');
    
    return t('packageCard.nextLesson', { date: formattedDate });
  };

  return (
    <Card
      hoverable
      style={{
        cursor: 'pointer',
        background: colors.bgSecondary,
        borderColor: colors.borderPrimary,
        transform: isPressed ? 'scale(0.98)' : 'scale(1)',
        transition: 'transform 0.1s ease-out',
      }}
      styles={{
        body: {
          padding: spacing.md,
        },
      }}
      onClick={onClick}
      onMouseDown={() => setIsPressed(true)}
      onMouseUp={() => setIsPressed(false)}
      onMouseLeave={() => setIsPressed(false)}
      onTouchStart={() => setIsPressed(true)}
      onTouchEnd={() => setIsPressed(false)}
    >
      {/* Top row: Title + Progress */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: spacing.sm }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text
            strong
            style={{
              fontSize: 16,
              lineHeight: 1.3,
              display: 'block',
            }}
            ellipsis
          >
            {pkg.title}
          </Text>
          <Text
            type="secondary"
            style={{
              fontSize: 12,
              fontWeight: 300,
              display: 'block',
              marginTop: 2,
            }}
            ellipsis
          >
            {pkg.learner_name}
          </Text>
        </div>
        <Progress
          type="circle"
          percent={percent}
          size={48}
          strokeColor={colors.accentSuccess}
          format={() => null}
        />
      </div>

      {/* Lesson count + Status badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs, marginTop: spacing.sm, flexWrap: 'wrap' }}>
        <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
          {formatLessonCount()}
        </Text>
        <Tag color={getStatusBadgeColor(pkg.status)} style={{ margin: 0, fontSize: 11, flexShrink: 0 }}>
          {t(`pages.packages.status.${pkg.status}`)}
        </Tag>
      </div>

      {/* Next lesson date (active packages only) */}
      {isActive && (
        <Text 
          type="secondary" 
          style={{ fontSize: 12, display: 'block', marginTop: 4 }}
          ellipsis
        >
          {formatNextLessonDate(pkg.next_lesson_date)}
        </Text>
      )}
    </Card>
  );
};

export default PackageCard;
