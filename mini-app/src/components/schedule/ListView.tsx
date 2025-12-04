import React from 'react';
import { List, Badge, Typography, Empty } from 'antd';
import dayjs from 'dayjs';
import type { Lesson } from './types';
import { STATUS_COLORS, STATUS_LABELS } from './types';

const { Text } = Typography;

interface ListViewProps {
  lessons: Lesson[];
  onLessonClick: (lesson: Lesson) => void;
}

const ListView: React.FC<ListViewProps> = ({ lessons, onLessonClick }) => {
  // Group lessons by date
  const groupedLessons = lessons.reduce((acc, lesson) => {
    const date = dayjs(lesson.scheduled_at).format('YYYY-MM-DD');
    if (!acc[date]) {
      acc[date] = [];
    }
    acc[date].push(lesson);
    return acc;
  }, {} as Record<string, Lesson[]>);

  // Sort dates
  const sortedDates = Object.keys(groupedLessons).sort();

  if (lessons.length === 0) {
    return <Empty description="Нет уроков" />;
  }

  return (
    <div>
      {sortedDates.map((date) => (
        <div key={date} style={{ marginBottom: 24 }}>
          <Typography.Title level={5} style={{ marginBottom: 12 }}>
            {dayjs(date).format('D MMMM YYYY, dddd')}
          </Typography.Title>
          <List
            dataSource={groupedLessons[date]}
            renderItem={(lesson) => {
              const lessonTime = dayjs(lesson.scheduled_at);
              const statusColor = STATUS_COLORS[lesson.status];
              const statusLabel = STATUS_LABELS[lesson.status];

              return (
                <List.Item
                  onClick={() => onLessonClick(lesson)}
                  style={{ cursor: 'pointer', padding: '12px 16px' }}
                >
                  <List.Item.Meta
                    title={
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Text strong>{lessonTime.format('HH:mm')}</Text>
                        <Text type="secondary">({lesson.duration_minutes} мин)</Text>
                      </div>
                    }
                    description={
                      <Badge color={statusColor} text={statusLabel} />
                    }
                  />
                </List.Item>
              );
            }}
          />
        </div>
      ))}
    </div>
  );
};

export default ListView;
