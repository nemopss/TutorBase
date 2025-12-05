import React from 'react';
import { Card, Tag, Button, Space, Typography } from 'antd';
import { EditOutlined, DeleteOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';
import { formatDateTime } from '../../utils/datetime';

const { Text } = Typography;

interface Lesson {
  id: number;
  package_id: number;
  package_title?: string;
  learner_name?: string;
  scheduled_at: string;
  status: string;
  duration_minutes?: number;
  teacher_notes?: string;
  timezone: string;
}

interface LessonCardProps {
  lesson: Lesson;
  onEdit: (lesson: Lesson) => void;
  onDelete: (id: number) => void;
  onClick?: (lesson: Lesson) => void;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'scheduled': return 'blue';
    case 'completed': return 'green';
    case 'cancelled': return 'red';
    default: return 'default';
  }
};

const LessonCard: React.FC<LessonCardProps> = ({
  lesson,
  onEdit,
  onDelete,
  onClick,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      onClick={() => onClick?.(lesson)}
      actions={[
        <Button
          key="edit"
          type="text"
          icon={<EditOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onEdit(lesson);
          }}
        >
          Edit
        </Button>,
        <Button
          key="delete"
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(lesson.id);
          }}
        >
          Delete
        </Button>,
      ]}
    >
      <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Text strong style={{ fontSize: 14 }}>
            {formatDateTime(lesson.scheduled_at, { timezone: lesson.timezone })}
          </Text>
          <Tag color={getStatusColor(lesson.status)}>{lesson.status.toUpperCase()}</Tag>
        </div>
        
        <div style={{ display: 'flex', gap: spacing.md, flexWrap: 'wrap' }}>
          {lesson.package_title && (
            <Text type="secondary">{lesson.package_title}</Text>
          )}
          {lesson.learner_name && (
            <Text type="secondary">• {lesson.learner_name}</Text>
          )}
        </div>
        
        {lesson.duration_minutes && (
          <Space size={spacing.xs}>
            <ClockCircleOutlined style={{ color: '#8c8c8c' }} />
            <Text type="secondary">{lesson.duration_minutes} min</Text>
          </Space>
        )}
        
        {lesson.teacher_notes && (
          <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
            {lesson.teacher_notes}
          </Text>
        )}
      </Space>
    </Card>
  );
};

export default LessonCard;
