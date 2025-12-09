import React from 'react';
import { Card, Tag, Typography, Dropdown, Button } from 'antd';
import type { MenuProps } from 'antd';
import {
  MoreOutlined,
  ClockCircleOutlined,
  CalendarOutlined,
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';
import { formatDateTime } from '../../utils/datetime';

const { Text } = Typography;

type LessonStatus = 'scheduled' | 'rescheduled' | 'completed' | 'cancelled';

interface Lesson {
  id: number;
  scheduled_at: string;
  status: LessonStatus;
  duration_minutes?: number;
}

interface LessonCardProps {
  lesson: Lesson;
  timezone: string;
  onReschedule: (lessonId: number) => void;
  onComplete: (lessonId: number) => void;
  onCancel: (lessonId: number) => void;
  onDelete: (lessonId: number) => void;
}

/** Status to color mapping */
const getStatusColor = (status: LessonStatus): string => {
  switch (status) {
    case 'scheduled':
      return '#1890ff'; // blue
    case 'rescheduled':
      return '#faad14'; // gold
    case 'completed':
      return '#52c41a'; // green
    case 'cancelled':
      return '#ff4d4f'; // red
    default:
      return '#d9d9d9';
  }
};

/** Status to tag color mapping for Ant Design Tag */
const getTagColor = (status: LessonStatus): string => {
  switch (status) {
    case 'scheduled':
      return 'blue';
    case 'rescheduled':
      return 'gold';
    case 'completed':
      return 'green';
    case 'cancelled':
      return 'red';
    default:
      return 'default';
  }
};

/**
 * Lesson card with colored left border and action menu.
 */
const LessonCard: React.FC<LessonCardProps> = ({
  lesson,
  timezone,
  onReschedule,
  onComplete,
  onCancel,
  onDelete,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const menuItems: MenuProps['items'] = [
    {
      key: 'reschedule',
      icon: <CalendarOutlined />,
      label: 'Reschedule',
      onClick: () => onReschedule(lesson.id),
    },
    {
      key: 'complete',
      icon: <CheckOutlined />,
      label: 'Mark as Completed',
      onClick: () => onComplete(lesson.id),
    },
    {
      key: 'cancel',
      icon: <CloseOutlined />,
      label: 'Cancel',
      onClick: () => onCancel(lesson.id),
    },
    { type: 'divider' },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: 'Delete',
      danger: true,
      onClick: () => onDelete(lesson.id),
    },
  ];

  const borderColor = getStatusColor(lesson.status);

  return (
    <Card
      size="small"
      style={{
        borderLeft: `4px solid ${borderColor}`,
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      bodyStyle={{
        padding: spacing.sm,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div style={{ flex: 1 }}>
          <Text strong style={{ fontSize: 14, display: 'block' }}>
            {formatDateTime(lesson.scheduled_at, { timezone })}
          </Text>
          {lesson.duration_minutes && (
            <Text
              type="secondary"
              style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4, marginTop: 4 }}
            >
              <ClockCircleOutlined />
              {lesson.duration_minutes} min
            </Text>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
          <Tag color={getTagColor(lesson.status)}>
            {lesson.status.toUpperCase()}
          </Tag>
          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button
              type="text"
              icon={<MoreOutlined />}
              size="small"
              onClick={(e) => e.stopPropagation()}
            />
          </Dropdown>
        </div>
      </div>
    </Card>
  );
};

export default LessonCard;
