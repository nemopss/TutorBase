import React, { useState } from 'react';
import { Card, Progress, Typography, Tag } from 'antd';
import { useThemeMode } from '../../theme/ThemeProvider';
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
 * Format lesson count as "X/Y уроков"
 */
export const formatLessonCount = (progress: PackageProgress): string => {
  const done = progress.completed + progress.cancelled;
  return `${done}/${progress.total} уроков`;
};

/**
 * Get badge color for package status
 */
export const getStatusBadgeColor = (status: string): string => {
  switch (status) {
    case 'active': return 'green';
    case 'completed': return 'blue';
    default: return 'default';
  }
};

/**
 * Get status label in Russian
 */
const getStatusLabel = (status: string): string => {
  switch (status) {
    case 'active': return 'Активен';
    case 'completed': return 'Завершён';
    case 'cancelled': return 'Отменён';
    case 'draft': return 'Черновик';
    default: return status;
  }
};

/**
 * Format next lesson date as "Следующий: DD MMM" or "Нет запланированных"
 */
export const formatNextLessonDate = (dateStr?: string | null): string => {
  if (!dateStr) return 'Нет запланированных';
  
  const date = new Date(dateStr);
  const day = date.getDate();
  const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const month = months[date.getMonth()];
  
  return `Следующий: ${day} ${month}`;
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
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const [isPressed, setIsPressed] = useState(false);

  const progress = pkg.progress || { total: 0, completed: 0, cancelled: 0 };
  const percent = progress.total > 0
    ? Math.round(((progress.completed + progress.cancelled) / progress.total) * 100)
    : 0;

  const isActive = pkg.status === 'active';

  return (
    <Card
      hoverable
      style={{
        cursor: 'pointer',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
        transform: isPressed ? 'scale(0.98)' : 'scale(1)',
        transition: 'transform 0.1s ease-out',
      }}
      bodyStyle={{
        padding: spacing.md,
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
          strokeColor="#0f7b6c"
          format={() => null}
        />
      </div>

      {/* Lesson count + Status badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs, marginTop: spacing.sm }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {formatLessonCount(progress)}
        </Text>
        <Tag color={getStatusBadgeColor(pkg.status)} style={{ margin: 0, fontSize: 11 }}>
          {getStatusLabel(pkg.status)}
        </Tag>
      </div>

      {/* Next lesson date (active packages only) */}
      {isActive && (
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
          {formatNextLessonDate(pkg.next_lesson_date)}
        </Text>
      )}
    </Card>
  );
};

export default PackageCard;
