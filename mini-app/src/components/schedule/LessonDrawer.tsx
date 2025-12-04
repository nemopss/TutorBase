import React from 'react';
import { Drawer, Descriptions, Badge, Typography } from 'antd';
import dayjs from 'dayjs';
import type { Lesson } from './types';
import { STATUS_COLORS, STATUS_LABELS } from './types';
const { Title } = Typography;

interface LessonDrawerProps {
  lesson: Lesson | null;
  open: boolean;
  onClose: () => void;
}

const LessonDrawer: React.FC<LessonDrawerProps> = ({ lesson, open, onClose }) => {
  if (!lesson) return null;

  const lessonDate = dayjs(lesson.scheduled_at);
  const statusColor = STATUS_COLORS[lesson.status];
  const statusLabel = STATUS_LABELS[lesson.status];

  return (
    <Drawer
      title="Детали урока"
      placement="right"
      onClose={onClose}
      open={open}
      width={400}
    >
      <Title level={4}>
        {lessonDate.format('D MMMM YYYY')}
      </Title>
      
      <Descriptions column={1} bordered>
        <Descriptions.Item label="Время">
          {lessonDate.format('HH:mm')}
        </Descriptions.Item>
        
        <Descriptions.Item label="Длительность">
          {lesson.duration_minutes} минут
        </Descriptions.Item>
        
        <Descriptions.Item label="Статус">
          <Badge color={statusColor} text={statusLabel} />
        </Descriptions.Item>
      </Descriptions>
    </Drawer>
  );
};

export default LessonDrawer;
